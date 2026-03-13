"""Research Swarm — 14-agent AI research orchestrator.

Usage:
    python3 orchestrator.py "topic"
    python3 orchestrator.py "topic" --dry-run
    python3 orchestrator.py "topic" --codebase ~/path/to/code
    python3 orchestrator.py "topic" --phases scout,research
    python3 orchestrator.py "topic" --no-gate
"""

import asyncio
import json
import re
import subprocess
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

from agents import ResearchAgent, build_agents, get_agents_by_phase, CAPABILITY_REGISTRY
from consensus import evaluate_critic, evaluate_judge, format_gate_report
from memory import ResearchMemory
from metrics import MetricsCollector, load_all_metrics, format_metrics_report

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.toml"
PROGRAM_PATH = Path(__file__).parent / "program.md"
LOG_PATH = Path(__file__).parent / "research-log.tsv"
OUTPUT_DIR = Path(__file__).parent / "output"
# Token budgeting: reserve 40% of context window for reasoning + output.
# Budget expressed in chars (~4 chars/token). Applied in _build_prompt().
MODEL_CONTEXT_BUDGET = {
    "haiku": 30_000,   # ~7.5K tokens — keeps scouts fast
    "sonnet": 50_000,  # ~12.5K tokens — balanced for researchers/applied
    "opus": 80_000,    # ~20K tokens — generous for synthesis/judge
}
DEFAULT_CONTEXT_BUDGET = 50_000

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Load config from config.toml."""
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def load_program() -> str:
    """Load the research program markdown."""
    if not PROGRAM_PATH.exists():
        return ""
    return PROGRAM_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Agent invocation
# ---------------------------------------------------------------------------


def invoke_agent(agent: ResearchAgent, context: str, task: str,
                  max_retries: int = 1) -> dict:
    """Invoke a single agent via claude CLI subprocess.

    Retries once on parse failure (PARSE research: 92% error reduction
    within first retry).
    """
    label = f"{agent.role}({agent.id})"

    for attempt in range(1 + max_retries):
        prompt = _build_prompt(agent, context, task)

        cmd = [
            "claude", "-p", prompt,
            "--system-prompt", agent.system_prompt,
            "--output-format", "json",
            "--model", agent.model,
            "--dangerously-skip-permissions",
        ]

        start = time.monotonic()

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=agent.timeout,
            )
            elapsed = time.monotonic() - start

            if result.returncode != 0:
                stderr = (result.stderr or "")[:200]
                print(f"  {label} ERROR: exit {result.returncode}")
                if stderr:
                    print(f"    {stderr}")
                return _error_output(agent, f"Exit code {result.returncode}")

            output = _parse_output(agent, result.stdout)

            # Check if output is usable (not raw text, not error)
            if output.get("_raw") and attempt < max_retries:
                print(f"  {label} malformed output, retrying [{elapsed:.1f}s]")
                # Strengthen the task prompt for retry
                task = (
                    f"{task}\n\n"
                    f"IMPORTANT: Your previous response was not valid JSON. "
                    f"Respond with ONLY a JSON object, no other text."
                )
                continue

            if not output.get("_error"):
                print(f"  {label} done [{elapsed:.1f}s]"
                      + (f" (retry {attempt})" if attempt > 0 else ""))
            return output

        except subprocess.TimeoutExpired as e:
            elapsed = time.monotonic() - start
            # Try to recover partial output from the timed-out process
            partial_stdout = ""
            if e.stdout:
                partial_stdout = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="replace")
            if partial_stdout.strip():
                output = _parse_output(agent, partial_stdout)
                if not output.get("_raw") and not output.get("_error"):
                    output["_partial"] = True
                    print(f"  {label} TIMEOUT [{elapsed:.1f}s] (recovered partial output)")
                    return output
            print(f"  {label} TIMEOUT [{elapsed:.1f}s]")
            return _error_output(agent, f"Timed out after {agent.timeout}s")
        except Exception as e:
            print(f"  {label} EXCEPTION: {e}")
            return _error_output(agent, str(e))

    return _error_output(agent, "All retries exhausted")


def _build_prompt(agent: ResearchAgent, context: str, task: str) -> str:
    """Build the user prompt for an agent.

    Token budget: each model tier gets a different context cap.
    Haiku scouts get less context (speed), Opus gets more (quality).
    """
    sections = [f"## Task\n{task}"]

    if context:
        budget = MODEL_CONTEXT_BUDGET.get(agent.model, DEFAULT_CONTEXT_BUDGET)
        if len(context) > budget:
            context = context[:budget] + "\n\n[Context trimmed to fit token budget]"
        sections.append(f"## Context\n{context}")

    sections.append(
        "## Output\nRespond with a JSON object. Be concise and specific."
    )
    return "\n\n".join(sections)


def _parse_output(agent: ResearchAgent, stdout: str) -> dict:
    """Parse agent stdout into a dict."""
    stdout = stdout.strip()
    if not stdout:
        return _error_output(agent, "Empty output")

    # --output-format json wraps response in a CLI envelope.
    # Unwrap the "result" field first.
    try:
        envelope = json.loads(stdout)
        if isinstance(envelope, dict) and "result" in envelope:
            stdout = envelope["result"]
            if isinstance(stdout, dict):
                stdout["_agent_id"] = agent.id
                stdout["_role"] = agent.role
                stdout["_phase"] = agent.phase
                return stdout
            # result is a string — continue parsing below
            stdout = str(stdout).strip()
    except (json.JSONDecodeError, TypeError):
        pass

    if not stdout:
        return _error_output(agent, "Empty result after envelope unwrap")

    # Try direct JSON parse
    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            data["_agent_id"] = agent.id
            data["_role"] = agent.role
            data["_phase"] = agent.phase
            return data
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", stdout, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict):
                data["_agent_id"] = agent.id
                data["_role"] = agent.role
                data["_phase"] = agent.phase
                return data
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object
    brace_match = re.search(r"\{.*\}", stdout, re.DOTALL)
    if brace_match:
        try:
            data = json.loads(brace_match.group(0))
            if isinstance(data, dict):
                data["_agent_id"] = agent.id
                data["_role"] = agent.role
                data["_phase"] = agent.phase
                return data
        except json.JSONDecodeError:
            pass

    # Last resort: wrap raw text
    return {
        "_agent_id": agent.id,
        "_role": agent.role,
        "_phase": agent.phase,
        "findings": stdout[:2000],
        "_raw": True,
    }


def _error_output(agent: ResearchAgent, msg: str) -> dict:
    """Standardized error output."""
    return {
        "_agent_id": agent.id,
        "_role": agent.role,
        "_phase": agent.phase,
        "_error": True,
        "_error_msg": msg,
    }


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------


async def blast_agents(agents: list[ResearchAgent], context: str,
                       task: str) -> list[dict]:
    """Invoke all agents in parallel."""
    coros = [
        asyncio.to_thread(invoke_agent, agent, context, task)
        for agent in agents
    ]
    return list(await asyncio.gather(*coros))


def validate_phase_output(phase_name: str, outputs: list[dict],
                          required_keys: list[str]) -> tuple[int, int]:
    """Validate phase outputs and log warnings.

    Returns (ok_count, total_count). Logs warnings if >50% failed.
    Checks for required keys and flags raw/error outputs.
    """
    total = len(outputs)
    ok = 0
    for o in outputs:
        if o.get("_error") or o.get("_raw"):
            continue
        # Check at least one required key has non-empty content
        has_content = any(
            o.get(k) and (
                (isinstance(o[k], str) and len(o[k]) > 10) or
                (isinstance(o[k], list) and len(o[k]) > 0) or
                (isinstance(o[k], (int, float)) and o[k] > 0)
            )
            for k in required_keys
        )
        if has_content:
            ok += 1

    if total > 0 and ok / total < 0.5:
        print(f"  WARNING: {phase_name} quality low — "
              f"only {ok}/{total} agents produced usable output")

    return ok, total


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------


def build_scout_context(scout_outputs: list[dict]) -> str:
    """Build context string from scout findings.

    Agents don't always follow the output schema exactly, so we
    extract whatever we can from the returned keys.
    """
    sections = []
    for o in scout_outputs:
        if o.get("_error"):
            continue
        agent_id = o.get("_agent_id", "scout")

        sections.append(f"### {agent_id}")

        # Extract summary from any plausible key
        summary = o.get("summary", "")
        if not summary:
            for k in ("research_topic", "overview", "description"):
                if k in o and isinstance(o[k], str):
                    summary = o[k]
                    break

        if summary:
            sections.append(str(summary)[:500])

        # Extract list of sources/findings from any plausible key
        sources = o.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        if not sources:
            for k in ("papers", "scout_findings", "benchmarks_and_evaluations",
                       "implementations", "findings", "results",
                       "key_research_directions"):
                val = o.get(k)
                if isinstance(val, list) and val:
                    sources = val
                    break
                elif isinstance(val, dict):
                    sources = [val]
                    break

        for s in sources[:5]:
            if isinstance(s, dict):
                title = s.get("title", s.get("name", ""))
                s_summary = s.get("summary", s.get("description", ""))[:100]
                sections.append(f"- **{title}**: {s_summary}")
            elif isinstance(s, str):
                sections.append(f"- {s[:150]}")
        sections.append("")

    return "\n".join(sections)


def build_research_context(researcher_outputs: list[dict]) -> str:
    """Build context string from researcher findings."""
    sections = []
    for o in researcher_outputs:
        if o.get("_error"):
            continue
        agent_id = o.get("_agent_id", "researcher")

        # Extract findings from any plausible key
        findings = ""
        for k in ("findings", "analysis", "research_findings", "summary", "overview"):
            val = o.get(k)
            if isinstance(val, str) and val:
                findings = val[:600]
                break

        # If findings is still empty, grab the longest string value
        if not findings:
            for k, v in o.items():
                if not k.startswith("_") and isinstance(v, str) and len(v) > len(findings):
                    findings = v[:600]

        key_points = o.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = []

        techniques = o.get("techniques", [])
        if not isinstance(techniques, list):
            techniques = []

        sections.append(f"### {agent_id}")
        if findings:
            sections.append(findings)
        if key_points:
            sections.append("Key points: " + "; ".join(str(k) for k in key_points[:5]))
        if techniques:
            for t in techniques[:3]:
                name = t.get("name", "") if isinstance(t, dict) else str(t)
                desc = t.get("description", "")[:80] if isinstance(t, dict) else ""
                sections.append(f"- Technique: **{name}** — {desc}")
        sections.append("")

    return "\n".join(sections)


def build_applied_context(applied_outputs: list[dict]) -> str:
    """Build context string from applied agent findings."""
    sections = []
    for o in applied_outputs:
        if o.get("_error"):
            continue
        agent_id = o.get("_agent_id", "applied")

        # Extract analysis from any plausible key
        analysis = ""
        for k in ("analysis", "findings", "summary", "overview", "audit"):
            val = o.get(k)
            if isinstance(val, str) and val:
                analysis = val[:500]
                break

        if not analysis:
            for k, v in o.items():
                if not k.startswith("_") and isinstance(v, str) and len(v) > len(analysis):
                    analysis = v[:500]

        recs = o.get("recommendations", [])
        if not isinstance(recs, list):
            recs = []
        # Also try alternate keys
        if not recs:
            for k in ("experiments", "suggestions", "actions", "gaps"):
                val = o.get(k)
                if isinstance(val, list) and val:
                    recs = val
                    break

        sections.append(f"### {agent_id}")
        if analysis:
            sections.append(analysis)
        for r in recs[:5]:
            if isinstance(r, dict):
                action = r.get("action", r.get("description", r.get("name", "")))[:80]
                priority = r.get("priority", "?")
                sections.append(f"- [{priority}] {action}")
            elif isinstance(r, str):
                sections.append(f"- {r[:100]}")
        sections.append("")

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Narrative casting — frame handoffs as story continuation, not data dumps.
# Research finding: LLMs comprehend narrative context better than structured
# state dumps, improving downstream accuracy by 3%+ (EXP-2 threshold).
# ---------------------------------------------------------------------------


def narrative_cast_scouts(scout_outputs: list[dict], topic: str) -> str:
    """Cast scout findings as narrative for researchers."""
    valid = [o for o in scout_outputs if not o.get("_error")]
    if not valid:
        return (f"The scout team found no results for '{topic}'. "
                f"Analyze based on your domain knowledge.")

    all_sources = []
    summaries = []

    for o in valid:
        agent_id = o.get("_agent_id", "scout")
        summary = o.get("summary", "")
        if summary:
            summaries.append(summary)

        sources = o.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        if not sources:
            for k in ("papers", "scout_findings", "benchmarks_and_evaluations",
                       "implementations", "findings", "results",
                       "key_research_directions"):
                val = o.get(k)
                if isinstance(val, list) and val:
                    sources = val
                    break
                elif isinstance(val, dict):
                    sources = [val]
                    break

        for s in sources:
            if isinstance(s, dict):
                all_sources.append({
                    "title": s.get("title", s.get("name", "untitled")),
                    "summary": s.get("summary", s.get("description", ""))[:150],
                    "relevance": s.get("relevance", 0.5),
                    "scout": agent_id,
                })

    all_sources.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    lines = [
        f"The scout team investigated \"{topic}\" across {len(valid)} scouts "
        f"and identified {len(all_sources)} relevant sources.",
        "",
    ]

    if summaries:
        lines.append("Scout assessments:")
        for s in summaries:
            lines.append(f"- {str(s)[:300]}")
        lines.append("")

    if all_sources:
        lines.append("Most relevant sources (ranked by relevance):")
        for s in all_sources[:10]:
            rel = s.get("relevance", "?")
            lines.append(
                f"- **{s['title']}** (relevance: {rel}, via {s['scout']}): "
                f"{s['summary']}"
            )
        lines.append("")

    lines.append(
        "Analyze these findings through your specific domain lens. "
        "Extract named techniques with concrete descriptions and trade-offs."
    )
    return "\n".join(lines)


def narrative_cast_research(research_outputs: list[dict], topic: str) -> str:
    """Cast research findings as narrative for applied agents."""
    valid = [o for o in research_outputs if not o.get("_error")]
    if not valid:
        return f"No researcher findings available for '{topic}'."

    lines = [
        f"{len(valid)} domain researchers analyzed \"{topic}\" and produced "
        f"these findings:",
        "",
    ]

    all_techniques = []

    for o in valid:
        agent_id = o.get("_agent_id", "researcher")
        domain = agent_id.replace("-researcher", "").replace("-", " ").title()

        findings = ""
        for k in ("findings", "analysis", "research_findings", "summary"):
            val = o.get(k)
            if isinstance(val, str) and val:
                findings = val[:400]
                break
        if not findings:
            for k, v in o.items():
                if (not k.startswith("_") and isinstance(v, str)
                        and len(v) > len(findings)):
                    findings = v[:400]

        key_points = o.get("key_points", [])
        if not isinstance(key_points, list):
            key_points = []

        techniques = o.get("techniques", [])
        if not isinstance(techniques, list):
            techniques = []

        lines.append(f"**{domain} perspective** ({agent_id}):")
        if findings:
            lines.append(findings)
        if key_points:
            lines.append(
                "Key takeaways: "
                + "; ".join(str(k)[:80] for k in key_points[:3])
            )
        lines.append("")

        for t in techniques:
            if isinstance(t, dict):
                all_techniques.append({
                    "name": t.get("name", ""),
                    "description": t.get("description", "")[:100],
                    "from": agent_id,
                })
            elif isinstance(t, str):
                all_techniques.append({
                    "name": t, "description": "", "from": agent_id,
                })

    # Deduplicate techniques by name prefix (research finding: researchers
    # echo-chamber the same techniques — 38 with massive overlap in run #4)
    if all_techniques:
        seen_prefixes = set()
        deduped = []
        for t in all_techniques:
            prefix = " ".join(t["name"].lower().split()[:3])
            if prefix and prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                deduped.append(t)
        all_techniques = deduped

        lines.append(f"Techniques discovered across all researchers ({len(all_techniques)} unique):")
        for t in all_techniques:
            desc = f" — {t['description']}" if t["description"] else ""
            lines.append(f"- **{t['name']}**{desc} (via {t['from']})")
        lines.append("")

    # Inject capability registry so applied agents know who covers what
    lines.append("Researcher capability registry:")
    for agent_id, caps in CAPABILITY_REGISTRY.items():
        covers = ", ".join(caps["covers"])
        lines.append(f"- {agent_id}: {covers}")
    lines.append("")

    lines.append(
        "Map these findings to the codebase. Produce concrete, actionable "
        "recommendations ordered by impact/effort ratio. Attribute findings "
        "to the correct researcher using the registry above."
    )
    return "\n".join(lines)


def build_conflicts_section(all_outputs: dict) -> str:
    """Build explicit conflicts section for synthesizer.

    Research finding: synthesizer should receive an explicit "conflicts"
    section listing disagreements between upstream agents.
    """
    conflicts = []

    # Check for researcher confidence divergence
    researchers = all_outputs.get("research", [])
    valid_researchers = [o for o in researchers if not o.get("_error")]

    confidences = {}
    for o in valid_researchers:
        agent_id = o.get("_agent_id", "?")
        conf = o.get("confidence", 0)
        if isinstance(conf, (int, float)) and conf > 0:
            confidences[agent_id] = conf

    if confidences:
        high_conf = {k: v for k, v in confidences.items() if v >= 0.7}
        low_conf = {k: v for k, v in confidences.items() if v < 0.5}
        if high_conf and low_conf:
            conflicts.append(
                f"Confidence divergence: {list(high_conf.keys())} report high "
                f"confidence while {list(low_conf.keys())} are uncertain — "
                f"investigate why."
            )

    # Check for critic high-severity flags
    quality = all_outputs.get("quality", [])
    for o in quality:
        if o.get("_agent_id") == "critic" and not o.get("_error"):
            issues = o.get("issues", [])
            high_issues = [i for i in issues if isinstance(i, dict)
                          and i.get("severity") == "high"]
            if high_issues:
                for issue in high_issues[:3]:
                    claim = issue.get("claim", "")[:80]
                    problem = issue.get("problem", "")[:80]
                    conflicts.append(f"Critic flags: \"{claim}\" — {problem}")

    if not conflicts:
        return ""

    lines = ["## Conflicts and Disagreements", ""]
    for c in conflicts:
        lines.append(f"- {c}")
    lines.append("")
    lines.append(
        "Address each conflict explicitly in the brief. Do not merge "
        "conflicting findings without noting the disagreement."
    )
    return "\n".join(lines)


def build_full_context(all_outputs: dict, topic: str = "") -> str:
    """Build full narrative context from all phases for quality gate and synthesis.

    Uses narrative format for each section and appends an explicit
    conflicts section so the synthesizer addresses disagreements.
    """
    sections = []

    if "scout" in all_outputs:
        sections.append("## Scout Findings")
        if topic:
            sections.append(narrative_cast_scouts(all_outputs["scout"], topic))
        else:
            sections.append(build_scout_context(all_outputs["scout"]))

    if "research" in all_outputs:
        sections.append("## Research Findings")
        if topic:
            sections.append(narrative_cast_research(all_outputs["research"], topic))
        else:
            sections.append(build_research_context(all_outputs["research"]))

    if "applied" in all_outputs:
        sections.append("## Applied Analysis")
        sections.append(build_applied_context(all_outputs["applied"]))

    if "quality" in all_outputs:
        for o in all_outputs["quality"]:
            if o.get("_agent_id") == "critic" and not o.get("_error"):
                sections.append("## Critic Assessment")
                verdict = o.get("verdict", "?")
                issues = o.get("issues", [])
                sections.append(f"Verdict: {verdict}")
                for issue in issues[:5]:
                    if isinstance(issue, dict):
                        sections.append(
                            f"- [{issue.get('severity', '?')}] "
                            f"{issue.get('claim', '')[:60]}: "
                            f"{issue.get('problem', '')[:80]}"
                        )
                sections.append("")

    # Explicit conflicts section (research finding: helps synthesizer
    # address disagreements instead of silently merging conflicting data)
    conflicts = build_conflicts_section(all_outputs)
    if conflicts:
        sections.append(conflicts)

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_research_brief(topic: str, synth_output: dict,
                          gate_report: str) -> str:
    """Format the final research brief markdown."""
    lines = [
        f"# Research Brief: {topic}",
        "",
        f"*Generated by Research Swarm on {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
    ]

    brief = synth_output.get("brief", "")
    if brief:
        lines.append(brief)
    else:
        lines.append("*Synthesizer produced no brief.*")

    experiments = synth_output.get("experiments_to_try", [])
    if experiments:
        lines.extend(["", "## Experiments to Try", ""])
        for i, exp in enumerate(experiments, 1):
            lines.append(f"{i}. {exp}")

    techniques = synth_output.get("techniques_found", [])
    if techniques:
        lines.extend(["", "## Techniques Discovered", ""])
        for t in techniques:
            lines.append(f"- {t}")

    lines.extend(["", "---", "", gate_report])

    return "\n".join(lines)


def save_output(topic: str, content: str) -> Path:
    """Save research brief to output directory."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", topic.lower().strip())[:50].strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = OUTPUT_DIR / f"{slug}_{timestamp}.md"
    filepath.write_text(content, encoding="utf-8")
    return filepath


def log_to_tsv(topic: str, agent_count: int, phases: str,
               actionability: float, status: str, output_file: str,
               key_finding: str):
    """Append entry to research-log.tsv."""
    date = datetime.now().strftime("%Y-%m-%d")
    finding_clean = key_finding.replace("\t", " ").replace("\n", " ")[:200]
    line = (
        f"{date}\t{topic}\t{agent_count}\t{phases}\t"
        f"{actionability}\t{status}\t{output_file}\t{finding_clean}\n"
    )
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


def dry_run(topic: str, agents: list[ResearchAgent]):
    """Show agent plan without executing."""
    print(f"\n{'=' * 60}")
    print(f"RESEARCH SWARM — DRY RUN")
    print(f"Topic: {topic}")
    print(f"{'=' * 60}\n")

    phases = ["scout", "research", "applied", "quality", "synthesis"]
    phase_names = {
        "scout": "SCOUT", "research": "RESEARCH", "applied": "APPLIED",
        "quality": "QUALITY GATE", "synthesis": "SYNTHESIS",
    }

    for phase in phases:
        phase_agents = get_agents_by_phase(agents, phase)
        if not phase_agents:
            continue
        exec_mode = "sequential" if phase == "quality" else "parallel"
        print(f"Phase: {phase_names[phase]} ({len(phase_agents)} agents, {exec_mode})")
        for a in phase_agents:
            print(f"  {a.id:22s} | model={a.model:8s} | timeout={a.timeout}s")
        print()

    print(f"Total: {len(agents)} agents")
    print(f"No agents will be invoked. Run without --dry-run to execute.\n")


# ---------------------------------------------------------------------------
# Main swarm execution
# ---------------------------------------------------------------------------


async def run_swarm(
    topic: str,
    agents: list[ResearchAgent],
    codebase: str = "",
    phases_filter: set | None = None,
    skip_gate: bool = False,
    verbose: bool = False,
) -> Path | None:
    """Run the full 5-phase research swarm."""

    print(f"\n{'=' * 60}")
    print(f"RESEARCH SWARM — {topic}")
    print(f"{'=' * 60}\n")

    all_phases = ["scout", "research", "applied", "quality", "synthesis"]
    active_phases = phases_filter or set(all_phases)

    # Load research program and memory
    program = load_program()
    config = load_config()
    mem_config = config.get("memory", {})
    mem = ResearchMemory()
    mem.decay_lambda = mem_config.get("decay_lambda", 0.01)
    mem.promotion_threshold = mem_config.get("promotion_threshold", 5)
    max_age_days = mem_config.get("max_technique_age_days", 90)
    mem.max_technique_age = max_age_days * 86400
    mem.initialize()
    memory_context = mem.build_memory_context(topic)

    stats = mem.stats
    meta = stats.get('meta_insights', 0)
    invalidated = stats.get('invalidated_techniques', 0)
    print(f"Memory: {stats.get('insights', 0)} insights ({meta} meta), "
          f"{stats.get('techniques', 0)} techniques ({invalidated} invalidated), "
          f"{stats.get('research_runs', 0)} prior runs")

    # Initialize metrics collector
    git_commit = ""
    try:
        git_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(Path(__file__).parent),
        )
        if git_result.returncode == 0:
            git_commit = git_result.stdout.strip()
    except Exception:
        pass

    mc = MetricsCollector()
    mc.start_run(
        run_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
        topic=topic,
        git_commit=git_commit,
    )
    mc.record_memory_state(stats)

    total_agents = len(agents)
    all_outputs = {}
    invocation_count = 0

    # --- Phase 1: SCOUT ---
    if "scout" in active_phases:
        scouts = get_agents_by_phase(agents, "scout")
        print(f"\n--- Phase 1: SCOUT ({len(scouts)} agents, parallel) ---")

        scout_task = (
            f"Find sources related to: {topic}\n\n"
            f"Research program context:\n{program[:500]}\n\n"
            f"Respond with a JSON object containing exactly these keys:\n"
            f"- sources (array of objects, each with: title, summary, relevance)\n"
            f"- summary (string — brief overview of what you found)\n"
            f"- relevance_score (number 0-1)"
        )
        scout_context = memory_context if memory_context else ""

        mc.start_phase("scout")
        start = time.monotonic()
        scout_outputs = await blast_agents(scouts, scout_context, scout_task)
        elapsed = time.monotonic() - start
        mc.end_phase("scout", scout_outputs, len(scout_context))
        print(f"  Scouts done [{elapsed:.1f}s]")

        all_outputs["scout"] = scout_outputs
        invocation_count += len(scouts)

        ok, total = validate_phase_output(
            "SCOUT", scout_outputs, ["sources", "summary"])
        print(f"  {ok}/{total} scouts produced usable output")
        if verbose:
            for o in scout_outputs:
                aid = o.get("_agent_id", "?")
                keys = [k for k in o.keys() if not k.startswith("_")]
                print(f"    {aid}: keys={keys}, raw={o.get('_raw', False)}, err={o.get('_error', False)}")

    # --- Phase 2: RESEARCH ---
    if "research" in active_phases:
        researchers = get_agents_by_phase(agents, "research")
        print(f"\n--- Phase 2: RESEARCH ({len(researchers)} agents, parallel) ---")

        scout_ctx = narrative_cast_scouts(all_outputs.get("scout", []), topic)
        research_task = (
            f"Analyze findings related to: {topic}\n\n"
            f"Focus on your specific domain. Be concrete and technical.\n\n"
            f"Respond with a JSON object containing exactly these keys:\n"
            f"- findings (string — detailed analysis from your domain)\n"
            f"- key_points (array of strings — most important takeaways)\n"
            f"- techniques (array of objects with: name, description, applicability)\n"
            f"- confidence (number 0-1)"
        )
        research_context = scout_ctx
        if memory_context:
            research_context = f"{memory_context}\n\n{scout_ctx}"

        mc.start_phase("research")
        start = time.monotonic()
        research_outputs = await blast_agents(researchers, research_context, research_task)
        elapsed = time.monotonic() - start
        mc.end_phase("research", research_outputs, len(research_context))
        print(f"  Researchers done [{elapsed:.1f}s]")

        all_outputs["research"] = research_outputs
        invocation_count += len(researchers)

        ok, total = validate_phase_output(
            "RESEARCH", research_outputs, ["findings", "key_points"])
        print(f"  {ok}/{total} researchers produced usable output")

    # --- Phase 3: APPLIED ---
    if "applied" in active_phases:
        applied = get_agents_by_phase(agents, "applied")
        print(f"\n--- Phase 3: APPLIED ({len(applied)} agents, parallel) ---")

        research_ctx = narrative_cast_research(all_outputs.get("research", []), topic)
        codebase_note = ""
        if codebase:
            codebase_note = f"\n\nCodebase to audit: {codebase}"

        applied_task = (
            f"Map research findings to the codebase for: {topic}\n\n"
            f"Produce concrete, actionable recommendations."
            f"{codebase_note}\n\n"
            f"Respond with a JSON object containing exactly these keys:\n"
            f"- analysis (string — how findings apply to the codebase)\n"
            f"- recommendations (array of objects with: action, priority, effort)\n"
            f"- priority (\"high\", \"medium\", or \"low\")"
        )

        mc.start_phase("applied")
        start = time.monotonic()
        applied_outputs = await blast_agents(applied, research_ctx, applied_task)
        elapsed = time.monotonic() - start
        mc.end_phase("applied", applied_outputs, len(research_ctx))
        print(f"  Applied done [{elapsed:.1f}s]")

        all_outputs["applied"] = applied_outputs
        invocation_count += len(applied)

        ok, total = validate_phase_output(
            "APPLIED", applied_outputs, ["analysis", "recommendations"])
        print(f"  {ok}/{total} applied agents produced usable output")

    # --- Phase 4: QUALITY GATE ---
    gate_report = ""
    judge_eval = {"actionability": 0, "vote": "keep"}

    if "quality" in active_phases and not skip_gate:
        quality_agents = get_agents_by_phase(agents, "quality")
        critic_agent = next((a for a in quality_agents if a.id == "critic"), None)
        judge_agent = next((a for a in quality_agents if a.id == "judge"), None)

        print(f"\n--- Phase 4: QUALITY GATE (sequential) ---")

        full_ctx = build_full_context(all_outputs, topic)

        # Critic first
        if critic_agent:
            critic_task = (
                f"Evaluate the research quality for: {topic}\n\n"
                f"Respond with a JSON object containing exactly these keys:\n"
                f"- issues (array of objects with claim, problem, severity)\n"
                f"- confidence (number 0-1)\n"
                f"- verdict (\"pass\", \"concerns\", or \"fail\")"
            )
            print(f"  Running critic...")
            start = time.monotonic()
            critic_output = await asyncio.to_thread(
                invoke_agent, critic_agent, full_ctx, critic_task
            )
            elapsed = time.monotonic() - start
            invocation_count += 1

            if verbose:
                print(f"  Critic raw output keys: {list(critic_output.keys())}")
                for k, v in critic_output.items():
                    if not k.startswith("_"):
                        print(f"    {k}: {str(v)[:120]}")

            critic_eval = evaluate_critic(critic_output)
            print(f"  Critic verdict: {critic_eval['verdict']} "
                  f"({critic_eval['total_issues']} issues) [{elapsed:.1f}s]")

            all_outputs.setdefault("quality", []).append(critic_output)

        # Judge sees everything including critic
        if judge_agent:
            judge_ctx = build_full_context(all_outputs, topic)
            judge_task = (
                f"Judge the research quality for: {topic}\n\n"
                f"Respond with a JSON object containing exactly these keys:\n"
                f"- coverage_score (number 0-10)\n"
                f"- accuracy_score (number 0-10)\n"
                f"- factuality_score (number 0-10 — are claims cited?)\n"
                f"- actionability_score (number 0-10)\n"
                f"- quality_vote (\"keep\" or \"discard\")\n"
                f"- notes (string explaining your decision)\n\n"
                f"Vote KEEP if actionability >= 6, DISCARD if below."
            )
            print(f"  Running judge (opus)...")
            start = time.monotonic()
            judge_output = await asyncio.to_thread(
                invoke_agent, judge_agent, judge_ctx, judge_task
            )
            elapsed = time.monotonic() - start
            invocation_count += 1

            config = load_config()
            min_act = config.get("quality", {}).get("min_actionability", 6)
            if verbose:
                print(f"  Judge raw output keys: {list(judge_output.keys())}")
                for k, v in judge_output.items():
                    if not k.startswith("_"):
                        print(f"    {k}: {str(v)[:120]}")

            # Compute mean researcher confidence for weighted consensus gate
            research_outputs = all_outputs.get("research", [])
            confidences = [
                o.get("confidence", 0.7)
                for o in research_outputs
                if not o.get("_error") and isinstance(o.get("confidence"), (int, float))
            ]
            mean_confidence = (
                sum(confidences) / len(confidences) if confidences else 0.7
            )

            judge_eval = evaluate_judge(judge_output, min_act, mean_confidence)
            print(f"  Judge: actionability={judge_eval['actionability']}/10, "
                  f"vote={judge_eval['vote']} [{elapsed:.1f}s]")

            all_outputs.setdefault("quality", []).append(judge_output)

            critic_result = critic_eval if critic_agent else {
                "verdict": "skipped", "confidence": 0,
                "total_issues": 0, "high_severity": 0,
                "medium_severity": 0, "issues": [],
            }
            gate_report = format_gate_report(critic_result, judge_eval)
            mc.record_quality_gate(judge_eval, critic_result)
            print(f"\n{gate_report}\n")

        # Check keep/discard
        if judge_eval["vote"] == "discard":
            print(f"  DISCARDED — actionability too low.")
            log_to_tsv(topic, invocation_count, ",".join(active_phases),
                       judge_eval["actionability"], "discard", "-",
                       judge_eval.get("notes", "")[:100])
            mem.log_run(topic, judge_eval["actionability"], "discard")
            mc.finalize()
            mc.save()
            mem.close()
            print(f"\nLogged to research-log.tsv. No brief produced.")
            _print_metrics_summary()
            return None

    elif skip_gate:
        print(f"\n--- Phase 4: QUALITY GATE (skipped via --no-gate) ---")
        judge_eval = {"actionability": 0, "vote": "keep", "notes": "Gate skipped"}

    # --- Phase 5: SYNTHESIS ---
    if "synthesis" in active_phases:
        synth_agents = get_agents_by_phase(agents, "synthesis")
        synth_agent = synth_agents[0] if synth_agents else None

        if synth_agent:
            print(f"\n--- Phase 5: SYNTHESIS (opus) ---")

            full_ctx = build_full_context(all_outputs, topic)
            synth_task = (
                f"Synthesize all findings into a research brief for: {topic}\n\n"
                f"Produce actionable recommendations with specific code changes.\n\n"
                f"Respond with a JSON object containing exactly these keys:\n"
                f"- brief (string — complete research brief in markdown)\n"
                f"- key_finding (string — single most important finding, one sentence)\n"
                f"- techniques_found (array of strings — named techniques to index)\n"
                f"- experiments_to_try (array of strings — concrete experiments)"
            )

            start = time.monotonic()
            synth_output = await asyncio.to_thread(
                invoke_agent, synth_agent, full_ctx, synth_task
            )
            elapsed = time.monotonic() - start
            invocation_count += 1
            print(f"  Synthesis complete [{elapsed:.1f}s]")

            # Format and save
            brief = format_research_brief(topic, synth_output, gate_report)
            filepath = save_output(topic, brief)

            # Extract key finding for log
            key_finding = synth_output.get("key_finding", "")
            if not key_finding:
                key_finding = synth_output.get("brief", "")[:100]

            # Log to TSV
            log_to_tsv(
                topic, invocation_count, ",".join(active_phases),
                judge_eval.get("actionability", 0), "keep",
                str(filepath.name), key_finding,
            )

            # Persist to memory
            run_id = mem.log_run(
                topic, judge_eval.get("actionability", 0),
                "keep", key_finding,
            )

            # Build provenance lookup from researcher technique outputs
            provenance = {}  # technique_name_prefix -> {source_url, evidence_type}
            for o in all_outputs.get("research", []):
                if o.get("_error"):
                    continue
                for t in o.get("techniques", []):
                    if isinstance(t, dict) and t.get("name"):
                        prefix = " ".join(t["name"].lower().split()[:3])
                        provenance[prefix] = {
                            "source_url": t.get("source_url", ""),
                            "evidence_type": t.get("evidence_type", "unverified"),
                        }

            # Store techniques with full metadata when available
            for t in synth_output.get("techniques_found", []):
                if isinstance(t, str):
                    # Parse "Name — description" format if present
                    name = t
                    desc = ""
                    if " — " in t:
                        parts = t.split(" — ", 1)
                        name, desc = parts[0].strip(), parts[1].strip()
                    elif " - " in t:
                        parts = t.split(" - ", 1)
                        name, desc = parts[0].strip(), parts[1].strip()

                    # Look up provenance by name prefix
                    prefix = " ".join(name.lower().split()[:3])
                    prov = provenance.get(prefix, {})

                    mem.store_technique(
                        name, description=desc, source=topic,
                        source_url=prov.get("source_url", ""),
                        evidence_type=prov.get("evidence_type", "unverified"),
                    )
                elif isinstance(t, dict):
                    mem.store_technique(
                        t.get("name", str(t)),
                        description=t.get("description", ""),
                        source=topic,
                        domain=t.get("domain", ""),
                        applicable_to=t.get("applicability", ""),
                        source_url=t.get("source_url", ""),
                        evidence_type=t.get("evidence_type", "unverified"),
                    )

            # Store insight
            if key_finding:
                mem.store_insight(key_finding, run_id)

            # Record technique overlap metrics
            raw_tech_count = sum(
                len(o.get("techniques", []))
                for o in all_outputs.get("research", [])
                if not o.get("_error") and isinstance(o.get("techniques"), list)
            )
            deduped_tech_count = len(synth_output.get("techniques_found", []))
            mc.record_technique_counts(raw_tech_count, deduped_tech_count)

            # Finalize and save metrics
            mc.finalize()
            mc.save()
            mem.close()

            print(f"\n{'=' * 60}")
            print(f"OUTPUT SAVED: {filepath}")
            print(f"Total agent invocations: {invocation_count}")
            print(f"Actionability: {judge_eval.get('actionability', 'N/A')}/10")
            print(f"Status: KEEP")
            print(f"{'=' * 60}\n")

            _print_metrics_summary()
            return filepath

    mc.finalize()
    mc.save()
    mem.close()
    return None


def _print_metrics_summary():
    """Print a compact metrics summary after a run."""
    records = load_all_metrics()
    if not records:
        return
    report = format_metrics_report(records)
    print(f"\n{report}\n")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Research Swarm: 14-agent AI research pipeline",
    )
    parser.add_argument("topic", nargs="?", default="",
                        help="The research topic")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show agent plan without executing")
    parser.add_argument("--codebase", default="",
                        help="Path to codebase for applied phase")
    parser.add_argument("--phases", default="",
                        help="Comma-separated phases to run (default: all)")
    parser.add_argument("--no-gate", action="store_true",
                        help="Skip quality gate (keep all findings)")
    parser.add_argument("--verbose", action="store_true",
                        help="Detailed logging")
    parser.add_argument("--metrics", action="store_true",
                        help="Show metrics report from all runs and exit")

    args = parser.parse_args()

    # Show metrics report and exit
    if args.metrics:
        records = load_all_metrics()
        if not records:
            print("No metrics recorded yet. Run a swarm first.")
        else:
            print(format_metrics_report(records, last_n=10))
        return

    if not args.topic:
        parser.error("topic is required (unless using --metrics)")

    # Load config
    config = load_config()
    models = config.get("models", {})
    timeouts = config.get("timeouts", {})

    # Build agents
    agents = build_agents(models, timeouts)

    if args.dry_run:
        dry_run(args.topic, agents)
        return

    # Parse phases filter
    phases_filter = None
    if args.phases:
        phases_filter = set(args.phases.split(","))

    filepath = asyncio.run(
        run_swarm(
            args.topic,
            agents,
            codebase=args.codebase,
            phases_filter=phases_filter,
            skip_gate=args.no_gate,
            verbose=args.verbose,
        )
    )

    if filepath:
        print(f"Done. Output at: {filepath}")
    else:
        print("Done. No output produced (discarded or incomplete).")


if __name__ == "__main__":
    main()
