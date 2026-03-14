# Artifacts

A map of every file in this repository and what it contains.

## Core System

| File | Purpose | Format |
|------|---------|--------|
| `orchestrator.py` | Main entrypoint; 5-phase pipeline, CLI argument parsing, phase orchestration | Python |
| `agents.py` | 14 agent definitions with system prompts, output schemas, capability registry | Python |
| `search_server.py` | MCP web search server; DuckDuckGo search + page fetching for scouts | Python |
| `consensus.py` | Quality gate logic; critic evaluation, judge scoring, keep/discard decision | Python |
| `context.py` | Priority-aware context compression; section scoring, budget allocation | Python |
| `dedup.py` | Semantic deduplication; Jaccard + bigram similarity, complete-linkage clustering | Python |
| `memory.py` | G-Memory management; SQLite with WAL, exponential decay, insight promotion | Python |
| `metrics.py` | Per-run instrumentation; metric collection, regression detection, reporting | Python |
| `dashboard.py` | HTML dashboard generator; Chart.js visualizations of run metrics | Python |
| `ablation.py` | Ablation experiment runner; tests multiple agent configurations | Python |
| `config.toml` | Configuration; model assignments, timeouts, agent roster, quality thresholds | TOML |

## Run Data

| File | Purpose | Format |
|------|---------|--------|
| `metrics.jsonl` | Per-run metrics (40 entries); quality scores, timing, agent counts, memory state | Newline-delimited JSON |
| `research-log.tsv` | Run audit trail; topic, date, actionability, status, key finding | TSV |
| `dashboard.html` | Generated metrics dashboard with interactive charts | HTML |
| `output/` | Research briefs from kept runs (gitignored) | Markdown |
| `memory.db` | SQLite G-Memory database; techniques, insights, decay scores (gitignored) | SQLite |

## Documentation

| File | Purpose |
|------|---------|
| `program.md` | Research program definition; focus areas, priorities, quality bar |
| `research.md` | Design decisions; source analysis (Blitz-Swarm, autoresearch, LoveSpark swarm) |
| `plan.md` | System planning documentation |
| `research-command.md` | CLI command documentation |

## Research Documents (docs/)

| File | Purpose |
|------|---------|
| `RESEARCH_QUESTIONS.md` | 5 research questions with status and evidence links |
| `METHODOLOGY.md` | How experiments are run, variables, success criteria |
| `EVALUATION.md` | Metric definitions, scoring logic, evaluation caveats |
| `ABLATIONS.md` | 11 major design changes with hypotheses and results |
| `LIMITATIONS.md` | 16 known limitations and failure modes |
| `ROADMAP.md` | Validated next steps vs. speculative ideas |
| `CLAIMS_AND_EVIDENCE.md` | Every claim mapped to evidence with strength ratings |
| `RESEARCH_LOG.md` | Lab notebook; commit-by-commit narrative |
| `RESULTS.md` | Structured results table (in results/) |

## Results (results/)

| File | Purpose |
|------|---------|
| `RESULTS.md` | Full 40-run results table with all measured dimensions |
