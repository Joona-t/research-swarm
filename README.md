# Research Swarm

> **Experimental** — This is an early-stage research tool. Expect rough edges, occasional timeouts, and results that get discarded by the quality gate. That's by design.

A 14-agent AI research pipeline that runs from your terminal. Give it a topic, and it sends out scouts, researchers, applied analysts, a critic, a judge, and a synthesizer — then produces an actionable research brief or throws it away if it's not good enough.

## Why This Exists

Building AI agents is hard. The field moves fast — new papers, new frameworks, new patterns every week. Keeping up manually doesn't scale.

We wanted a tool that could:

1. **Research a topic deeply** across multiple angles simultaneously (architecture, memory, prompts, evaluation, infrastructure)
2. **Challenge its own findings** with a dedicated critic before accepting them
3. **Produce actionable output** — not summaries, but specific techniques, code changes, and experiments with keep/discard criteria
4. **Learn from past runs** — each successful run stores techniques and insights that inform future research

The key insight: **a single AI agent doing research hits a quality ceiling**. It either goes broad and shallow, or deep and narrow. By splitting the work across 14 specialized agents with different perspectives, you get both breadth and depth — and the quality gate prevents garbage from leaking through.

## The Reasoning

This draws from two sources:

**Andrej Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) pattern** — The idea that you program AI agents via markdown, not code. The `program.md` file defines what to research and what the quality bar is. Results are logged in a TSV. Bad runs get discarded like a `git reset`. Good findings compound over time. One change at a time, measure, keep or discard.

**Parallel agent execution (blitz-swarm pattern)** — Instead of one agent doing everything sequentially, blast multiple specialized agents in parallel and synthesize their outputs. Scouts use cheap/fast models (Haiku) for breadth. Researchers use mid-tier models (Sonnet) for focused analysis. The judge and synthesizer use the strongest model (Opus) because their decisions are the highest-stakes.

The 5-phase pipeline creates natural quality checkpoints:

```
SCOUT → RESEARCH → APPLIED → QUALITY GATE → SYNTHESIS
(find)   (analyze)  (apply)   (challenge)    (produce)
```

Each phase builds on the previous one's output. If the quality gate says discard, the run is logged but no brief is produced. This prevents the system from outputting mediocre research — it either clears the bar or doesn't ship.

## The 14 Agents

| Phase | Agents | Model | Execution |
|-------|--------|-------|-----------|
| **Scout** (3) | arxiv-scout, impl-scout, bench-scout | Haiku | Parallel |
| **Research** (5) | arch, memory, prompt, eval, infra researchers | Sonnet | Parallel |
| **Applied** (3) | codebase-auditor, gap-analyst, experiment-designer | Sonnet | Parallel |
| **Quality Gate** (2) | critic, judge | Sonnet, Opus | Sequential |
| **Synthesis** (1) | synthesizer | Opus | Single |

**Model tiering logic:**
- **Haiku** for scouts — fast and cheap, their job is finding signal, not analyzing it
- **Sonnet** for researchers and applied agents — focused depth on specific domains
- **Opus** for judge and synthesizer — highest-stakes decisions deserve the strongest reasoning

## Usage

### Prerequisites

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- No additional dependencies — the swarm invokes agents via `claude -p` subprocesses

### Run a research topic

```bash
python3 orchestrator.py "multi-agent consensus convergence"
```

### Dry run (preview the agent plan)

```bash
python3 orchestrator.py "your topic" --dry-run
```

### Point at a specific codebase for the applied phase

```bash
python3 orchestrator.py "your topic" --codebase ~/path/to/your/project
```

### Run specific phases only

```bash
python3 orchestrator.py "your topic" --phases scout,research
```

### Skip the quality gate

```bash
python3 orchestrator.py "your topic" --no-gate
```

## How It Works

1. **Scouts** fan out and find sources — papers, implementations, benchmarks
2. **Researchers** analyze those findings through 5 different domain lenses (architecture, memory, prompts, evaluation, infrastructure)
3. **Applied agents** map the research to your actual codebase — what to change, where, and why
4. **Critic** challenges the findings — flags hype, missing context, cherry-picked results
5. **Judge** (Opus) scores on coverage, accuracy, and actionability. Votes KEEP or DISCARD
6. **Synthesizer** (Opus) produces the final research brief if the judge kept it

## Output

Successful runs produce:
- A markdown research brief in `output/` with techniques, code changes, and experiments
- A log entry in `research-log.tsv`
- Techniques and insights stored in `memory.db` (SQLite) for future runs

## G-Memory

The swarm has a simple SQLite-based memory system. After each successful run, it stores:
- **Techniques** — named patterns with descriptions and source topics
- **Insights** — one-sentence key findings linked to their source run

On future runs, relevant past techniques and insights are injected into researcher prompts as historical context. This is how the swarm compounds knowledge over time.

## Configuration

Edit `config.toml` to change models, timeouts, and quality thresholds:

```toml
[models]
scout = "haiku"
researcher = "sonnet"
applied = "sonnet"
critic = "sonnet"
judge = "opus"
synthesizer = "opus"

[timeouts]
scout = 120
researcher = 180
applied = 150
quality = 120
synthesizer = 180

[quality]
min_actionability = 6
```

Edit `program.md` to steer the swarm's research focus — this is the Karpathy-style "programming via markdown" approach.

## Claude Code Slash Command

If you use Claude Code, copy the slash command to use `/research` directly:

```bash
cp research-command.md ~/.claude/commands/research.md
```

Then: `/research "your topic"`

## What's Experimental

- Agents don't always follow output schemas perfectly — the parser is resilient but not bulletproof
- Applied agents can timeout on broad topics (150s limit)
- Scout findings depend on the model's training data, not live web search
- The quality gate is strict — expect some runs to be discarded, especially on vague topics
- Token usage is significant: a full 14-agent run costs roughly what 14 individual Claude conversations would

## Project Structure

```
research-swarm/
├── orchestrator.py      # Main entrypoint — 5-phase execution, CLI
├── agents.py            # 14 agent definitions, role prompts, output schemas
├── consensus.py         # Quality gate — critic eval, judge eval, keep/discard
├── memory.py            # SQLite G-Memory — techniques, insights, runs
├── config.toml          # Model assignments, timeouts, thresholds
├── program.md           # Research program (human-editable, steers the swarm)
├── research-log.tsv     # Persistent log of all runs
├── plan.md              # Architecture plan and design decisions
├── research.md          # Background research that informed the design
├── output/              # Generated research briefs (gitignored)
└── memory.db            # SQLite G-Memory storage (gitignored)
```

## License

MIT
