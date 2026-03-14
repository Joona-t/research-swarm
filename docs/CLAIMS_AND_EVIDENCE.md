# Claims and Evidence

Every significant claim made in this repository, mapped to its evidence source, strength, and caveats.

## Architecture Claims

### "8 agents match or exceed 14-agent quality"
- **Evidence:** 12-run ablation in metrics.jsonl (runs with 5 vs 11 agent invocations across 3 topics)
- **Strength:** Moderate
- **Caveats:** 3 topics only. Single LLM evaluator. Quality is a composite score that may mask dimension-specific regressions.

### "Explicit OUT_OF_SCOPE declarations reduce redundancy more effectively than removing agents"
- **Evidence:** Observed directionally — overlap decreased after commit 94c6334 (role differentiation). The 8-agent config with scope boundaries outperformed 14 agents without them.
- **Strength:** Weak-to-moderate — confounded with other simultaneous changes (dedup, agent count reduction).
- **Caveats:** No isolated A/B test of scope boundaries alone.

### "Sequential phasing outperforms parallel blast for research tasks"
- **Evidence:** Design rationale in research.md. No direct comparison against parallel execution in this codebase.
- **Strength:** Design bet, not empirically tested.
- **Caveats:** Blitz-Swarm (parallel architecture) exists as a separate project but uses different agents, topics, and evaluation, so direct comparison is not valid.

## Quality Claims

### "Adversarial critique improves factual grounding (4.0 → 5.0)"
- **Evidence:** metrics.jsonl factuality scores before/after commit 088764f.
- **Strength:** Moderate
- **Caveats:** Web search was added shortly after (commit f742f39), confounding the effect. The combined improvement is 4.0 → 6.0, but the individual contributions are not isolated.

### "Web search improved factuality from 4.0 to 6.0"
- **Evidence:** metrics.jsonl factuality scores before/after commit f742f39.
- **Strength:** Strong — largest single improvement, clearly time-bounded.
- **Caveats:** Factuality is scored by an LLM, not by human verification of citations.

### "Semantic deduplication reduces overlap from 76% to 38%"
- **Evidence:** metrics.jsonl overlap_ratio field before/after commit 779f26b.
- **Strength:** Strong — algorithmic measurement, not LLM-scored.
- **Caveats:** Coverage (whether dedup removed genuinely distinct techniques) is scored by the judge, not independently verified.

### "Dedup threshold 0.50 caused over-merging"
- **Evidence:** Commit 27f0358 revert. Overlap=1.0 on 1/3 ablation topics at threshold 0.50.
- **Strength:** Strong — clear failure, immediate revert.
- **Caveats:** Only tested on 3 topics.

## System Claims

### "The quality gate correctly identifies and rejects low-quality research"
- **Evidence:** 6 discard decisions in research-log.tsv with reasons. 3/6 were topic-codebase mismatches correctly identified. 1/6 was a catastrophic failure. 2/6 were quality-related discards.
- **Strength:** Moderate — the gate works, but "correctly" assumes the threshold (actionability >= 6) is well-calibrated, which has not been validated against human judgment.
- **Caveats:** No false-negative analysis (kept runs that should have been discarded).

### "G-Memory enables cross-run learning"
- **Evidence:** Memory growth curve: 40 → 448 techniques, 4 → 31 insights across 40 runs.
- **Strength:** Weak — memory accumulates, but the effect on output quality is not measured.
- **Caveats:** No controlled experiment (empty vs. populated memory on same topic).

### "Applied agent success rate improved from 2/3 to 3/3"
- **Evidence:** Observed after commit a699f52.
- **Strength:** Weak — very small sample (one phase with 3 agents).
- **Caveats:** "Success" means producing parseable output, not producing correct recommendations.

## Presentation Claims

### "75% keep rate across 40 runs"
- **Evidence:** research-log.tsv (30 keeps, 6 discards, 4 incomplete/empty).
- **Strength:** Strong — directly observable.
- **Caveats:** 4 runs had empty output (no vote recorded), which are excluded from the keep/discard count but included in the total.
