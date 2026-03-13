# Research Swarm — Plan

> 14-agent AI research swarm. CLI tool invoked via `/research "topic"`.
> Adapts Karpathy's autoresearch loop + blitz-swarm parallel execution.

## Architecture

```
research-swarm/
├── orchestrator.py      # Main entrypoint + phased execution + consensus
├── agents.py            # 14 agent definitions + role prompts
├── consensus.py         # Voting logic + keep/discard + actionability scoring
├── memory.py            # SQLite G-Memory (simplified, no Redis/LanceDB)
├── program.md           # The research program (Karpathy-style, human-editable)
├── research-log.tsv     # Persistent experiment log
├── config.toml          # Swarm configuration
├── output/              # Dated research briefs
└── memory.db            # SQLite G-Memory storage
```

## The 14 Agents

### Phase 1: SCOUT (3 agents, parallel)
All scouts blast simultaneously. They gather raw signal.

| # | ID | Role | Model | Job |
|---|----|------|-------|-----|
| 1 | `arxiv-scout` | scout | haiku | Find recent papers on the topic from arXiv, conferences, preprints |
| 2 | `impl-scout` | scout | haiku | Find actual implementations: GitHub repos, HF models, blog posts with code |
| 3 | `bench-scout` | scout | haiku | Find benchmarks, comparisons, eval results related to the topic |

**Output:** Each scout returns `{ sources: [...], summary: "...", relevance_score: 0-1 }`

**Why haiku:** Scouts do breadth, not depth. Fast and cheap. Their job is to find signal, not analyze it.

### Phase 2: RESEARCH (5 agents, parallel)
All researchers blast simultaneously with scout findings as context.

| # | ID | Role | Model | Job |
|---|----|------|-------|-----|
| 4 | `arch-researcher` | researcher | sonnet | Agent architectures: planning, tool use, multi-agent coordination |
| 5 | `memory-researcher` | researcher | sonnet | Context management: RAG, hierarchical memory, compression |
| 6 | `prompt-researcher` | researcher | sonnet | Prompt engineering: system prompts, structured output, CoT |
| 7 | `eval-researcher` | researcher | sonnet | Evaluation: measuring agent quality, automated testing, benchmarks |
| 8 | `infra-researcher` | researcher | sonnet | Orchestration, parallel execution, cost optimization, caching |

**Output:** Each returns `{ findings: "...", key_points: [...], techniques: [...], confidence: 0-1 }`

**Context injection:** Each researcher receives ALL scout outputs + their role-specific focus area. They don't see each other's output (round 1). In round 2+ (if consensus fails), they see everything.

### Phase 3: APPLIED (3 agents, parallel)
Map research findings to our actual codebase.

| # | ID | Role | Model | Job |
|---|----|------|-------|-----|
| 9 | `codebase-auditor` | applied | sonnet | Read current agent code, identify patterns and gaps |
| 10 | `gap-analyst` | applied | sonnet | Compare current approach to research findings, rank by impact |
| 11 | `experiment-designer` | applied | sonnet | Design concrete experiments to test promising techniques |

**Output:** Each returns `{ analysis: "...", recommendations: [...], priority: "high/med/low" }`

**Context injection:** All researcher outputs + relevant file paths from our codebase. The `--codebase` flag points to the directory to audit (defaults to `~/Claude x LoveSpark/`).

### Phase 4: QUALITY GATE (2 agents, sequential)
Critic runs first, then judge sees critic's assessment.

| # | ID | Role | Model | Job |
|---|----|------|-------|-----|
| 12 | `critic` | quality | sonnet | Challenge hype, check reproducibility, flag weak claims |
| 13 | `judge` | quality | opus | Score on coverage/accuracy/actionability, cast final vote |

**Output:**
- Critic: `{ issues: [...], confidence: 0-1, verdict: "pass/concerns/fail" }`
- Judge: `{ actionability_score: 0-10, quality_vote: "keep/discard", notes: "..." }`

**The keep/discard decision:** If judge votes "discard", the run is logged but no research brief is produced. This is the Karpathy `git reset` equivalent — we don't advance on bad research.

### Phase 5: SYNTHESIS (1 agent)
Only runs if judge voted "keep".

| # | ID | Role | Model | Job |
|---|----|------|-------|-----|
| 14 | `synthesizer` | output | opus | Produce final research brief with actionable recommendations |

**Output:** Structured markdown research brief saved to `output/`.

## Execution Flow

```
/research "how to make multi-agent consensus converge faster"

Phase 1: SCOUT ──────────────────────────── ~30s
  ├── arxiv-scout    ─┐
  ├── impl-scout     ─┤ parallel (haiku)
  └── bench-scout    ─┘

Phase 2: RESEARCH ───────────────────────── ~60-120s
  ├── arch-researcher    ─┐
  ├── memory-researcher  ─┤
  ├── prompt-researcher  ─┤ parallel (sonnet)
  ├── eval-researcher    ─┤
  └── infra-researcher   ─┘

Phase 3: APPLIED ────────────────────────── ~60-90s
  ├── codebase-auditor     ─┐
  ├── gap-analyst          ─┤ parallel (sonnet)
  └── experiment-designer  ─┘

Phase 4: QUALITY GATE ──────────────────── ~30-60s
  ├── critic  → (sequential)
  └── judge   → keep/discard decision

Phase 5: SYNTHESIS (if kept) ────────────── ~60s
  └── synthesizer → research brief

Total: ~4-6 minutes for a full research run
```

## CLI Interface

```bash
# Basic research run
python3 orchestrator.py "multi-agent consensus convergence"

# Dry run — show agent plan without executing
python3 orchestrator.py "topic" --dry-run

# Limit to specific phases
python3 orchestrator.py "topic" --phases scout,research

# Point to specific codebase for applied phase
python3 orchestrator.py "topic" --codebase ~/Claude\ x\ LoveSpark/blitz-swarm/

# Skip quality gate (keep all findings)
python3 orchestrator.py "topic" --no-gate

# Verbose logging
python3 orchestrator.py "topic" --verbose
```

## program.md (Karpathy-style)

The `program.md` file defines the research program. The human edits this to steer the swarm's research focus. This is the equivalent of Karpathy's `program.md` — you're not editing Python, you're programming the agents via markdown.

```markdown
# Research Program

## Focus Areas
- Multi-agent coordination and consensus
- Memory systems for agent continuity
- Prompt optimization for structured output
- Tool use patterns and MCP integration
- Cost optimization (token efficiency)

## Current Priorities
1. Make blitz-swarm consensus converge in fewer rounds
2. Reduce agent timeout issues in subprocess invocation
3. Improve G-Memory retrieval accuracy

## Codebase Context
- Primary: ~/Claude x LoveSpark/blitz-swarm/
- Secondary: ~/Claude x LoveSpark/AGENT-SWARM.md
- Skills: ~/.claude/commands/

## Quality Bar
- Actionability score >= 6 to keep
- At least 2 concrete code changes recommended
- Techniques must be implementable without new dependencies
```

## research-log.tsv

Persistent log of every research run. Tab-separated.

```
date	topic	agents	phases	actionability	status	output_file	key_finding
2026-03-14	multi-agent consensus	14	all	8	keep	output/multi_agent_consensus_20260314.md	Async voting with timeout reduces rounds by 40%
2026-03-14	prompt optimization	14	all	4	discard	-	No actionable findings for our stack
```

## G-Memory (Simplified)

Stripped-down version of blitz-swarm's memory. SQLite only, no Redis, no LanceDB.

**Tables:**
- `research_runs` — id, topic, date, actionability, status, insight
- `techniques` — id, name, source, domain, applicable_to, tried, worked
- `insights` — id, content, supporting_runs, access_count

**Retrieval:** On each new run, query `insights` and `techniques` tables for entries matching the topic. Inject as historical context into researcher prompts.

**Compounding:** After each "keep" run, extract one-sentence insight and store it. After 10+ runs, the swarm has accumulated domain knowledge that makes it progressively better.

## Timeout Prevention

Blitz-swarm's #1 issue: researcher agents timeout. Fixes:

1. **Narrow prompts** — each agent has ONE focused job, not "research everything about X"
2. **Haiku for scouts** — fast model for breadth tasks
3. **120s timeout for scouts, 180s for researchers, 120s for applied/quality** — tuned per phase
4. **Prompt size cap** — context injection is capped at 3000 chars per agent
5. **JSON output mode** — `--output-format json` forces structured, concise responses

## Slash Command

`~/.claude/commands/research.md` — invokes the orchestrator.

```
/research "topic"
/research "topic" --dry-run
/research "topic" --phases scout,research
```

---

## TODO (implementation checklist)

- [x] `orchestrator.py` — main entrypoint, phased execution, CLI args
- [x] `agents.py` — 14 agent definitions with role prompts
- [x] `consensus.py` — quality gate voting, keep/discard logic
- [x] `memory.py` — SQLite G-Memory (simplified)
- [x] `program.md` — initial research program
- [x] `config.toml` — default configuration
- [x] `research-log.tsv` — header row
- [x] `~/.claude/commands/research.md` — slash command skill
- [x] Test: dry run
- [ ] Test: full run on a narrow topic
- [ ] Test: G-Memory persistence across runs
