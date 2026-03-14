# Roadmap

## Validated Next Steps

These are backed by observations from existing runs and address known, measured deficiencies.

1. **Implement per-run cost tracking.** All 40 runs show estimated_cost_units = 0. Correlating API billing data with run IDs would enable cost/quality tradeoff analysis. This is a straightforward engineering task.

2. **Add a pre-dispatch topic filter.** 3 of 6 discards were caused by topic-codebase mismatch. A lightweight classifier (or even a keyword check) could reject mismatched topics before spending tokens.

3. **Run memory isolation experiment.** Compare the same topic with empty vs. populated G-Memory to measure the causal effect of cross-run learning (RQ4). This requires clearing memory.db before a controlled run.

4. **Add human evaluation baseline.** Score 10 research briefs manually on the same 4 dimensions, then compare with judge scores to measure evaluator agreement.

5. **Isolate critic vs. web search contribution.** Run the same topics with and without the critic agent to separate the factuality gains from adversarial review vs. web search grounding.

## Speculative Ideas

These are architecturally interesting but not motivated by measured deficiencies.

6. **Pre-dispatch sufficiency gating.** Block redundant agent spawns at the orchestrator level before any tokens are spent. This appeared in multiple research briefs but has not been implemented or tested.

7. **Embedding-based deduplication.** Replace Jaccard + bigram similarity with vector embeddings for cross-lingual and semantic dedup. Would require adding a sentence-transformer dependency.

8. **Multi-model evaluation.** Use a different model family (e.g., GPT-4) as an independent judge to measure inter-rater reliability.

9. **Continuous research mode.** Chain multiple runs with automated topic selection based on memory gaps, as in Karpathy's autoresearch loop.

10. **Publish research briefs as a dataset.** Release the 30 kept research briefs as a public dataset for studying multi-agent research output quality.
