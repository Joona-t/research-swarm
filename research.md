# Research Swarm — Research

## Sources Studied

### 1. Blitz-Swarm (our existing system)
- **Location:** `~/Claude x LoveSpark/blitz-swarm/`
- **Pattern:** Dynamic agent count, parallel blast via `asyncio.gather()`, consensus voting, G-Memory 3-tier storage
- **Agent invocation:** Stateless `claude -p` subprocess calls with `--output-format json`
- **Strengths:** Parallel execution, consensus convergence, dissent preservation, memory compounding
- **Weaknesses:** Researcher agents timeout at 300s (prompt too heavy for stateless subprocess), no phased execution (scouts vs researchers vs evaluators), generic roles not specialized for AI research

### 2. Karpathy's autoresearch
- **Repo:** `github.com/karpathy/autoresearch`
- **Core insight:** `program.md` IS the research org — human writes markdown, agent executes autonomously
- **Loop discipline:** Modify → Run → Measure → Keep/Discard → Log → Repeat
- **Key elements to adapt:**
  - `program.md` paradigm — skill file defines research program
  - `results.tsv` — persistent experiment log with keep/discard status
  - Single metric focus — everything measured against one number
  - Never stop — autonomous until interrupted
  - Compound state — each run builds on last successful state

### 3. LoveSpark 22-Agent Swarm (AGENT-SWARM.md)
- **Pattern:** Council-based (6 Opus leads + 12 Sonnet specialists + 4 utilities)
- **Execution:** 4-wave lifecycle (Recon → Analysis → Gate → Action)
- **Key insight:** Phased execution with quality gates between phases works better than all-at-once blast for complex tasks

## Key Design Decisions

### Why separate from blitz-swarm?
Blitz-swarm is general-purpose research (any topic). Research Swarm is specialized: AI agent research to improve our codebase. Different agent roles, different execution phases, different output format.

### Why phased execution instead of single blast?
Scouts need to run first — researchers can't analyze papers they haven't found yet. Applied agents can't map to codebase without research findings. The dependency chain is real: Discovery → Analysis → Application → Quality → Synthesis.

### Why `claude -p` subprocesses?
Same as blitz-swarm: model-agnostic, stateless, no framework dependencies. Each agent is a CLI call. Orchestrator owns all state.

### Timeout fix from blitz-swarm learnings
Blitz-swarm researchers timeout at 180-300s. Root cause: researcher prompts are too heavy for single subprocess calls. Fix: shorter, more focused prompts per agent. Each of the 14 agents has a narrow scope — no agent tries to do "deep research on everything."

### Karpathy adaptations
| autoresearch element | Research Swarm adaptation |
|---------------------|--------------------------|
| `program.md` | `/research` skill file — human iterates on the research program |
| `train.py` (agent modifies) | Our agent codebase (prompts, architectures, patterns) |
| `val_bpb` (single metric) | Actionability score (0-10): can this be applied within a week? |
| `results.tsv` | `research-log.tsv` — topic, date, findings, actionability, status |
| Keep/discard | Critic + Judge vote → keep or discard findings |
| Never stop | Optional `--loop` flag for chained research sessions |
| Branch per run | Dated output files + G-Memory persistence |

## Technology Stack
- Python 3.12+ (matches blitz-swarm)
- `claude` CLI for agent invocation
- asyncio for parallel execution
- SQLite+WAL for G-Memory persistence (no Redis required)
- No external deps beyond standard library
