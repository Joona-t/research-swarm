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

from agents import ResearchAgent, build_agents, get_agents_by_phase
from consensus import evaluate_critic, evaluate_judge, format_gate_report
from memory import ResearchMemory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.toml"
PROGRAM_PATH = Path(__file__).parent / "program.md"
LOG_PATH = Path(__file__).parent / "research-log.tsv"
OUTPUT_DIR = Path(__file__).parent / "output"
MAX_CONTEXT_CHARS = 3000

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


def invoke_agent(agent: ResearchAgent, context: str, task: str) -> dict:
    """Invoke a single agent via claude CLI subprocess."""
    prompt = _build_prompt(agent, context, task)

    cmd = [
        "claude", "-p", prompt,
        "--system-prompt", agent.system_prompt,
        "--output-format", "json",
        "--model", agent.model,
        "--dangerously-skip-permissions",
    ]

    label = f"{agent.role}({agent.id})"
    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=agent.timeout,
        )
        elapsed = time.monotonic() - start
        print(f"  {label} done [{elapsed:.1f}s]")

        if result.returncode != 0:
            stderr = (result.stderr or "")[:200]
            print(f"  {label} ERROR: exit {result.returncode}")
            if stderr:
                print(f"    {stderr}")
            return _error_output(agent, f"Exit code {result.returncode}")

        return _parse_output(agent, result.stdout)

    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        print(f"  {label} TIMEOUT [{elapsed:.1f}s]")
        return _error_output(agent, f"Timed out after {agent.timeout}s")
    except Exception as e:
        print(f"  {label} EXCEPTION: {e}")
        return _error_output(agent, str(e))


def _build_prompt(agent: ResearchAgent, context: str, task: str) -> str:
    """Build the user prompt for an agent."""
    sections = [f"## Task\n{task}"]

    if context:
        # Cap context to prevent timeouts
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated]"
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


def build_full_context(all_outputs: dict) -> str:
    """Build full context from all phases for quality gate and synthesis."""
    sections = []

    if "scout" in all_outputs:
        sections.append("## Scout Findings")
        sections.append(build_scout_context(all_outputs["scout"]))

    if "research" in all_outputs:
        sections.append("## Research Findings")
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
    mem = ResearchMemory()
    mem.initialize()
    memory_context = mem.build_memory_context(topic)

    stats = mem.stats
    print(f"Memory: {stats.get('insights', 0)} insights, "
          f"{stats.get('techniques', 0)} techniques, "
          f"{stats.get('research_runs', 0)} prior runs")

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

        start = time.monotonic()
        scout_outputs = await blast_agents(scouts, scout_context, scout_task)
        elapsed = time.monotonic() - start
        print(f"  Scouts done [{elapsed:.1f}s]")

        all_outputs["scout"] = scout_outputs
        invocation_count += len(scouts)

        ok = sum(1 for o in scout_outputs if not o.get("_error"))
        print(f"  {ok}/{len(scouts)} scouts returned results")
        if verbose:
            for o in scout_outputs:
                aid = o.get("_agent_id", "?")
                keys = [k for k in o.keys() if not k.startswith("_")]
                print(f"    {aid}: keys={keys}, raw={o.get('_raw', False)}, err={o.get('_error', False)}")

    # --- Phase 2: RESEARCH ---
    if "research" in active_phases:
        researchers = get_agents_by_phase(agents, "research")
        print(f"\n--- Phase 2: RESEARCH ({len(researchers)} agents, parallel) ---")

        scout_ctx = build_scout_context(all_outputs.get("scout", []))
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

        start = time.monotonic()
        research_outputs = await blast_agents(researchers, research_context, research_task)
        elapsed = time.monotonic() - start
        print(f"  Researchers done [{elapsed:.1f}s]")

        all_outputs["research"] = research_outputs
        invocation_count += len(researchers)

        ok = sum(1 for o in research_outputs if not o.get("_error"))
        print(f"  {ok}/{len(researchers)} researchers returned results")

    # --- Phase 3: APPLIED ---
    if "applied" in active_phases:
        applied = get_agents_by_phase(agents, "applied")
        print(f"\n--- Phase 3: APPLIED ({len(applied)} agents, parallel) ---")

        research_ctx = build_research_context(all_outputs.get("research", []))
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

        start = time.monotonic()
        applied_outputs = await blast_agents(applied, research_ctx, applied_task)
        elapsed = time.monotonic() - start
        print(f"  Applied done [{elapsed:.1f}s]")

        all_outputs["applied"] = applied_outputs
        invocation_count += len(applied)

        ok = sum(1 for o in applied_outputs if not o.get("_error"))
        print(f"  {ok}/{len(applied)} applied agents returned results")

    # --- Phase 4: QUALITY GATE ---
    gate_report = ""
    judge_eval = {"actionability": 0, "vote": "keep"}

    if "quality" in active_phases and not skip_gate:
        quality_agents = get_agents_by_phase(agents, "quality")
        critic_agent = next((a for a in quality_agents if a.id == "critic"), None)
        judge_agent = next((a for a in quality_agents if a.id == "judge"), None)

        print(f"\n--- Phase 4: QUALITY GATE (sequential) ---")

        full_ctx = build_full_context(all_outputs)

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
            judge_ctx = build_full_context(all_outputs)
            judge_task = (
                f"Judge the research quality for: {topic}\n\n"
                f"Respond with a JSON object containing exactly these keys:\n"
                f"- coverage_score (number 0-10)\n"
                f"- accuracy_score (number 0-10)\n"
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

            judge_eval = evaluate_judge(judge_output, min_act)
            print(f"  Judge: actionability={judge_eval['actionability']}/10, "
                  f"vote={judge_eval['vote']} [{elapsed:.1f}s]")

            all_outputs.setdefault("quality", []).append(judge_output)

            gate_report = format_gate_report(
                critic_eval if critic_agent else {"verdict": "skipped", "confidence": 0,
                                                   "total_issues": 0, "high_severity": 0,
                                                   "medium_severity": 0, "issues": []},
                judge_eval,
            )
            print(f"\n{gate_report}\n")

        # Check keep/discard
        if judge_eval["vote"] == "discard":
            print(f"  DISCARDED — actionability too low.")
            log_to_tsv(topic, invocation_count, ",".join(active_phases),
                       judge_eval["actionability"], "discard", "-",
                       judge_eval.get("notes", "")[:100])
            mem.log_run(topic, judge_eval["actionability"], "discard")
            mem.close()
            print(f"\nLogged to research-log.tsv. No brief produced.")
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

            full_ctx = build_full_context(all_outputs)
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

            # Store techniques
            for t in synth_output.get("techniques_found", []):
                if isinstance(t, str):
                    mem.store_technique(t, source=topic)

            # Store insight
            if key_finding:
                mem.store_insight(key_finding, run_id)

            mem.close()

            print(f"\n{'=' * 60}")
            print(f"OUTPUT SAVED: {filepath}")
            print(f"Total agent invocations: {invocation_count}")
            print(f"Actionability: {judge_eval.get('actionability', 'N/A')}/10")
            print(f"Status: KEEP")
            print(f"{'=' * 60}\n")

            return filepath

    mem.close()
    return None


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Research Swarm: 14-agent AI research pipeline",
    )
    parser.add_argument("topic", help="The research topic")
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

    args = parser.parse_args()

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
