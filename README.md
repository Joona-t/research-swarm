# Research Swarm

An 8-agent AI research pipeline that runs from your terminal. Give it a topic, and it sends out scouts with live web search, researchers, an applied analyst, a critic, a judge, and a synthesizer — then produces an actionable research brief or throws it away if it's not good enough.

## Why 8 Agents, Not 14?

This swarm started with 14 agents. We ran a [12-run ablation experiment](output/ablation_results.json) across 4 configurations (14, 10, 8, 7 agents) and 3 topics to find the optimal count. The data:

| Config | Agents | Avg Quality | Avg Actionability | Avg Factuality |
|--------|--------|-------------|-------------------|----------------|
| full | 14 | 5.9 | 4.3 | 5.3 |
| lean | 10 | 5.7 | 4.7 | 5.3 |
| **minimal** | **8** | **6.1** | **5.3** | **5.3** |
| skeleton | 7 | 6.1 | 6.3 | 5.0 |

**8 agents match or exceed 14-agent quality** with higher actionability. The literature backs this up — homogeneous agent scaling hits diminishing returns at 3-5 agents. Our 5 researchers had massive domain overlap; 2 well-scoped researchers cover the same ground with less redundancy noise.

The roster is config-driven. All 14 prompts are preserved — flip back to 14 by removing `[swarm.roster]` from `config.toml`.

## Why This Exists

Building AI agents is hard. The field moves fast — new papers, frameworks, and patterns every week. We wanted a tool that could:

1. **Research a topic deeply** across multiple angles simultaneously
2. **Ground findings in real sources** via live web search (DuckDuckGo MCP)
3. **Challenge its own findings** with a dedicated critic before accepting them
4. **Produce actionable output** — specific techniques, code changes, and experiments with keep/discard criteria
5. **Learn from past runs** — each successful run stores techniques and insights that inform future research

## The Pipeline

```
SCOUT → RESEARCH → APPLIED → QUALITY GATE → SYNTHESIS
(search)  (analyze)  (apply)   (challenge)    (produce)
```

### The 8 Agents

| Phase | Agents | Model | Execution |
|-------|--------|-------|-----------|
| **Scout** (2) | arxiv-scout, impl-scout | Haiku | Parallel |
| **Research** (2) | arch-researcher, prompt-researcher | Sonnet | Parallel |
| **Applied** (1) | experiment-designer | Sonnet | Single |
| **Quality Gate** (2) | critic, judge | Sonnet, Opus | Sequential |
| **Synthesis** (1) | synthesizer | Opus | Single |

**Model tiering:** Haiku for fast scouting, Sonnet for focused analysis, Opus for high-stakes judgment and synthesis.

### Live Web Search

Scouts have their own MCP web search server (`search_server.py`) powered by DuckDuckGo — free, no API key, fully self-hosted. Two tools:

- **web_search** — searches DuckDuckGo with operators (`site:arxiv.org`, `"exact phrase"`)
- **fetch_page** — reads actual page content (paper abstracts, READMEs, docs)

This is how the swarm grounds citations in real sources instead of hallucinating paper titles.

## Usage

### Prerequisites

- Python 3.11+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated
- `pip install ddgs mcp httpx` (for scout web search)

### Run a research topic

```bash
python3 orchestrator.py "multi-agent consensus convergence 2025"
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

### View the dashboard

```bash
python3 dashboard.py
```

Generates `dashboard.html` with Chart.js graphs tracking quality, actionability, factuality, overlap, and wall clock across all runs.

### Run an ablation experiment

```bash
python3 ablation.py                    # all 4 configs x 3 topics
python3 ablation.py --configs full,lean  # specific configs only
```

## How It Works

1. **Scouts** search the web and find sources — real papers, implementations, benchmarks with real URLs
2. **Researchers** analyze those findings through domain lenses (architecture, prompting)
3. **Applied agent** maps the research to your codebase — what to change, where, and why
4. **Critic** challenges the findings — flags hype, echo-chambered citations, missing context
5. **Judge** (Opus) scores on coverage, accuracy, actionability, and factuality. Votes KEEP or DISCARD
6. **Synthesizer** (Opus) produces the final research brief if the judge kept it

## Key Features

- **Semantic deduplication** — Jaccard + bigram similarity with complete-linkage clustering catches "Three-Tier Memory" / "Hierarchical Memory Architecture" / "Temporal Memory Tiers" as the same idea
- **Priority-aware context compression** — high-confidence, well-evidenced sections preserved in full; low-priority sections compressed or dropped
- **Evidence labeling** — every technique tagged with evidence type (peer_reviewed, preprint, repo, unverified)
- **Adversarial quality gate** — critic + judge catch hallucinations, echo-chamber amplification, and inflated grounding claims
- **G-Memory** — SQLite-based memory with exponential decay. Techniques and insights compound across runs

## Output

Successful runs produce:
- A markdown research brief in `output/` with techniques, code changes, and experiments
- A log entry in `research-log.tsv`
- Metrics appended to `metrics.jsonl`
- Techniques and insights stored in `memory.db` for future runs

## Configuration

Edit `config.toml` to change models, timeouts, agent roster, and quality thresholds:

```toml
[swarm.roster]
scouts = ["arxiv-scout", "impl-scout"]
researchers = ["arch-researcher", "prompt-researcher"]
applied = ["experiment-designer"]

[models]
scout = "haiku"
researcher = "sonnet"
judge = "opus"
synthesizer = "opus"

[quality]
min_actionability = 6
```

Remove `[swarm.roster]` to use all 14 agents.

## Project Structure

```
research-swarm/
├── orchestrator.py      # Main entrypoint — 5-phase execution, CLI
├── agents.py            # 14 agent definitions, role prompts, output schemas
├── search_server.py     # MCP web search server (DuckDuckGo + page fetch)
├── consensus.py         # Quality gate — critic eval, judge eval, keep/discard
├── context.py           # Priority-aware context compression
├── dedup.py             # Semantic technique deduplication
├── memory.py            # SQLite G-Memory — techniques, insights, runs
├── metrics.py           # Per-run metrics collection, regression detection
├── dashboard.py         # HTML dashboard generator (Chart.js)
├── ablation.py          # Agent-count ablation experiment runner
├── config.toml          # Model assignments, timeouts, roster, thresholds
├── program.md           # Research program (steers the swarm)
├── research-log.tsv     # Persistent log of all runs
├── metrics.jsonl        # Machine-readable metrics for dashboard
├── output/              # Generated research briefs (gitignored)
└── memory.db            # SQLite G-Memory storage (gitignored)
```

## Evolution

This swarm has been recursively self-improved over 31 instrumented runs:

1. **JSON compliance** — PARSE schemas, retry logic, two-pass reasoning
2. **Context injection** — narrative casting, dynamic token budgets
3. **Role differentiation** — OUT_OF_SCOPE blocks, capability registry
4. **Timeout handling** — failure policy, partial recovery
5. **Hallucination gate** — adversarial critic, confidence-weighted consensus
6. **Applied agent quality** — confidence propagation, CoT scaffolding
7. **Semantic dedup** — Jaccard+bigram similarity, agglomerative clustering (overlap 76% → 38%)
8. **Grounding** — evidence labeling, citation verification protocol (factuality 4.0 → 5.0)
9. **Context compression** — priority-aware section scoring (applied success 2/3 → 3/3)
10. **Web search** — custom MCP server with DuckDuckGo (factuality 4.0 → 6.0)
11. **Agent-count ablation** — data-driven restructure from 14 to 8 agents (no quality loss)

## License

MIT
