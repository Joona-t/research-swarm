# Methodology

## Experiment Structure

Each run of Research Swarm constitutes a single experiment with the following structure:

1. **Input:** A research topic string (e.g., "multi-agent consensus convergence 2025")
2. **Configuration:** Agent roster, model assignments, quality thresholds (all in config.toml)
3. **Execution:** 5-phase pipeline (scout → research → applied → quality gate → synthesis)
4. **Output:** A markdown research brief (if kept) or discard record (if rejected)
5. **Measurement:** Per-run metrics logged to metrics.jsonl and research-log.tsv

## Variables

### Independent Variables (Changed Between Runs)
- Research topic
- Agent count (14, 10, 8, 7 — tested in ablation)
- Agent roster composition (which agents are active)
- Deduplication threshold (0.39 vs 0.50)
- Architectural features (e.g., before/after adding web search, critic, dedup)

### Controlled Variables (Held Constant Within a Run)
- Model assignments per phase (Haiku/Sonnet/Opus)
- Context budget per model tier
- Quality gate threshold (actionability >= 6)
- Timeout limits per phase
- Output format (markdown brief)

### Dependent Variables (Measured)
- Quality score (0-10, composite)
- Actionability score (0-10, primary metric)
- Factuality score (0-10)
- Coverage score (0-10)
- Accuracy score (0-10)
- Keep/discard decision
- Technique overlap ratio (pre- vs post-dedup)
- Wall clock time
- Agent success/error/timeout counts
- Memory state (techniques, insights accumulated)

## What Counts as Success

A run is "successful" (kept) when:
1. The judge scores actionability >= 6
2. The critic does not issue a "fail" verdict
3. At least 50% of agents in each phase produce parseable output

A run is "discarded" when:
1. Actionability < 6 (most common)
2. Critic verdict = "fail" (overrides judge scores)
3. Catastrophic failure (majority of agents return empty output)

## What Counts as an Improvement

An architectural change is considered an improvement when:
1. The target metric improves by >= 0.5 points on subsequent runs
2. No other metric degrades by > 1.0 point
3. The improvement is observed across at least 2 consecutive runs on different topics

These thresholds are informal — with 40 runs, statistical significance testing is not feasible.

## Evaluation Caveats

1. **Single evaluator:** All scoring is done by Claude (Opus for judge, Sonnet for critic). No human ground truth, no inter-rater reliability.
2. **Evaluator bias:** The same model family (Claude) produces the research AND evaluates it. Systematic biases in Claude's output may not be caught.
3. **Topic dependence:** Quality scores vary significantly by topic. Topics mismatched with the target codebase (e.g., GPU fine-tuning for a browser extension project) consistently score low on actionability regardless of research quality.
4. **Temporal confounds:** Multiple changes were often introduced in the same commit or close together, making it difficult to isolate the effect of individual changes.
5. **No blind evaluation:** The judge knows it is evaluating the system's own output, which may introduce leniency bias.

## Run Protocol

```bash
# Standard run
python3 orchestrator.py "topic" --codebase ~/target/project

# The system automatically:
# 1. Logs the run to research-log.tsv
# 2. Appends metrics to metrics.jsonl
# 3. Stores techniques in memory.db
# 4. Saves the brief to output/ (if kept)
```

No manual intervention is required during a run. The quality gate decision (keep/discard) is automated.
