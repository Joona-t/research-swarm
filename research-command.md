Run a Research Swarm — 14-agent AI research pipeline on a given topic.

## Usage

The user provides a topic as the argument: `/research "topic here"`

## Execution Steps

1. **Show dry run first** — Always preview the agent plan before executing:
   ```bash
   cd ~/Claude\ x\ LoveSpark/research-swarm && python3 orchestrator.py "$ARGUMENTS" --dry-run
   ```

2. **Confirm and execute** — After showing the dry run, ask the user to confirm, then run the full swarm:
   ```bash
   cd ~/Claude\ x\ LoveSpark/research-swarm && python3 orchestrator.py "$ARGUMENTS"
   ```

3. **Show results** — When execution completes:
   - Display the quality gate report (keep/discard decision)
   - If kept: show the output file path and read the research brief
   - If discarded: explain why and show the judge's notes
   - Show the updated research-log.tsv entry

## Flags

Users can append flags after the topic:

- `--dry-run` — Only show agent plan, don't execute
- `--codebase ~/path/to/code` — Point applied agents at a specific codebase
- `--phases scout,research` — Run only specific phases
- `--no-gate` — Skip quality gate (keep all findings)
- `--verbose` — Detailed logging

## Examples

```
/research "multi-agent consensus convergence"
/research "prompt optimization for structured output" --codebase ~/Claude\ x\ LoveSpark/blitz-swarm/
/research "reducing agent timeout issues" --phases scout,research
/research "memory systems for long-running agents" --dry-run
```

## Post-Run

After a successful run:
- The brief is saved to `~/Claude x LoveSpark/research-swarm/output/`
- The run is logged in `research-log.tsv`
- Techniques and insights are stored in `memory.db` for future runs
- Read the brief and highlight the top 3 actionable findings for the user
