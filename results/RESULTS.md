# Results

## Full Run Table (40 runs)

Data source: metrics.jsonl and research-log.tsv. All scores on 0-10 scale.

| # | Run ID | Topic (abbreviated) | Agents | Quality | Action | Fact | Coverage | Accuracy | Overlap | Wall(s) | Vote |
|---|--------|---------------------|--------|---------|--------|------|----------|----------|---------|---------|------|
| 1 | 20260313_231040 | Reducing agent timeout failures | 11 | 7.0 | 7.0 | — | 8.0 | 6.0 | 0.69 | 584 | keep |
| 2 | 20260313_232641 | Reducing hallucination/factual accuracy | 11 | 7.0 | 7.0 | — | 8.0 | 6.0 | 0.62 | 709 | keep |
| 3 | 20260313_233657 | Reducing hallucination/factual accuracy | 11 | 6.3 | 7.0 | — | 7.0 | 5.0 | 0.74 | 619 | keep |
| 4 | 20260314_000326 | Applied agent failures/context-to-action | 11 | 6.5 | 7.0 | 4.0 | 8.0 | 7.0 | 0.76 | 709 | keep |
| 5 | 20260314_040541 | Semantic similarity/redundancy elimination | 11 | 5.8 | 6.0 | 4.0 | 7.0 | 6.0 | 0.58 | 671 | keep |
| 6 | 20260314_041826 | Multi-agent coordination patterns | 11 | 6.8 | 7.0 | 6.0 | 7.0 | 7.0 | 0.05 | 737 | keep |
| 7 | 20260314_043101 | Grounding with tool-augmented search | 11 | 6.0 | 6.0 | 5.0 | 7.0 | 6.0 | 0.28 | 682 | keep |
| 8 | 20260314_044439 | Automated evaluation frameworks | 11 | 4.5 | 6.0 | 3.0 | 4.0 | 5.0 | 0.00 | 370 | **discard** |
| 9 | 20260314_045126 | Automated evaluation frameworks | 11 | 7.0 | 8.0 | 5.0 | 8.0 | 7.0 | 0.53 | 639 | keep |
| 10 | 20260314_050219 | Priority-aware context compression | 11 | 6.5 | 7.0 | 4.0 | 8.0 | 7.0 | 0.33 | 764 | keep |
| 11 | 20260314_051559 | Reducing latency in coding agents | 11 | 6.5 | 7.0 | 5.0 | 7.0 | 7.0 | 0.71 | 647 | keep |
| 12 | 20260314_062651 | Lightweight semantic dedup | 3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | 72 | incomplete |
| 13 | 20260314_062918 | Lightweight semantic dedup | 11 | 6.2 | 7.0 | 4.0 | 7.0 | 7.0 | 0.46 | 626 | keep |
| 14 | 20260314_064422 | Semantic dedup for LLM outputs | 3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | 73 | incomplete |
| 15 | 20260314_064913 | Semantic dedup for LLM outputs | 3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | 98 | incomplete |
| 16 | 20260314_065056 | Improving factuality | 11 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | 338 | **discard** |
| 17 | 20260314_080220 | Improving factuality | 3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | 122 | incomplete |
| 18 | 20260314_080427 | Improving factuality in pipelines | 11 | 7.2 | 8.0 | 6.0 | 8.0 | 7.0 | 1.00 | 763 | keep |
| 19 | 20260314_082938 | Optimal agent count/scaling laws | 11 | 6.2 | 7.0 | 4.0 | 7.0 | 7.0 | 0.55 | 541 | keep |
| 20 | 20260314_084357 | RAG hallucination reduction | 11 | 5.5 | 3.0 | 5.0 | 7.0 | 7.0 | 0.00 | 452 | **discard** |
| 21 | 20260314_085129 | Fine-tuning on consumer hardware | 11 | 6.0 | 3.0 | 6.0 | 8.0 | 7.0 | 0.00 | 528 | **discard** |
| 22 | 20260314_090017 | Code gen evaluation benchmarks | 11 | 6.2 | 7.0 | 5.0 | 7.0 | 6.0 | 0.14 | 562 | keep |
| 23 | 20260314_090939 | RAG hallucination reduction | 7 | 6.0 | 6.0 | 5.0 | 7.0 | 6.0 | 0.05 | 601 | keep |
| 24 | 20260314_091940 | Fine-tuning on consumer hardware | 7 | 4.5 | 2.0 | 5.0 | 6.0 | 5.0 | 0.00 | 480 | **discard** |
| 25 | 20260314_092740 | Code gen evaluation benchmarks | 7 | 6.5 | 6.0 | 6.0 | 7.0 | 7.0 | 0.47 | 632 | keep |
| 26 | 20260314_093812 | RAG hallucination reduction | 5 | 6.5 | 6.0 | 6.0 | 7.0 | 7.0 | 0.07 | 603 | keep |
| 27 | 20260314_095534 | Fine-tuning on consumer hardware | 5 | 5.5 | 4.0 | 5.0 | 6.0 | 7.0 | 0.00 | 438 | **discard** |
| 28 | 20260314_095534 | Code gen evaluation benchmarks | 5 | 6.2 | 6.0 | 5.0 | 7.0 | 7.0 | -0.14 | 548 | keep |
| 29 | 20260314_100442 | RAG hallucination reduction | 4 | 6.0 | 7.0 | 4.0 | 6.0 | 7.0 | 0.07 | 467 | keep |
| 30 | 20260314_101229 | Fine-tuning on consumer hardware | 4 | 6.5 | 6.0 | 6.0 | 7.0 | 7.0 | 0.08 | 620 | keep |
| 31 | 20260314_102249 | Code gen evaluation benchmarks | 4 | 5.8 | 6.0 | 5.0 | 6.0 | 6.0 | 0.00 | 584 | keep |
| 32 | 20260314_155020 | Chain-of-thought prompting | 5 | 6.0 | 6.0 | 5.0 | 7.0 | 6.0 | 0.23 | 537 | keep |
| 33 | 20260314_160000 | Speculative decoding for agents | 5 | 6.5 | 6.0 | 6.0 | 7.0 | 7.0 | 0.00 | 628 | keep |
| 34 | 20260314_161101 | Autonomous self-improvement | 5 | 5.5 | 6.0 | 4.0 | 6.0 | 6.0 | 0.38 | 673 | keep |
| 35 | 20260314_165044 | Chain-of-thought prompting | 5 | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 | 0.23 | 502 | keep |
| 36 | 20260314_165912 | Speculative decoding for agents | 5 | 7.0 | 7.0 | 7.0 | 7.0 | 7.0 | 0.00 | 441 | keep |
| 37 | 20260314_170638 | Autonomous self-improvement | 5 | 6.8 | 6.0 | 7.0 | 7.0 | 7.0 | 1.00 | 737 | keep |
| 38 | 20260314_174532 | Cost optimization/model routing | 5 | 6.8 | 7.0 | 6.0 | 7.0 | 7.0 | 0.12 | 695 | keep |
| 39 | 20260314_175713 | Parallel vs sequential pipelines | 5 | 7.2 | 7.0 | 7.0 | 7.0 | 8.0 | 0.00 | 442 | keep |
| 40 | 20260314_180440 | Agent role specialization | 5 | 6.8 | 7.0 | 6.0 | 7.0 | 7.0 | 1.00 | 633 | keep |

**Notes:**
- "—" in Factuality column: metric not yet tracked at time of run
- Runs 12, 14, 15, 17: incomplete (scout-only or partial phase execution)
- Agent count reflects total_agent_invocations from metrics.jsonl
- All scores are from the judge agent (Claude Opus)

## Aggregate Statistics

| Metric | Kept Runs (n=30) | Discards (n=6) | Incomplete (n=4) |
|--------|-----------------|----------------|-------------------|
| Avg Quality | 6.5 | 4.3 | 0.0 |
| Avg Actionability | 6.7 | 3.0 | 0.0 |
| Avg Factuality | 5.3 | 4.0 | 0.0 |
| Avg Coverage | 7.1 | 5.8 | 0.0 |
| Avg Accuracy | 6.7 | 5.5 | 0.0 |
| Avg Overlap | 0.37 | 0.00 | 0.00 |
| Avg Wall Clock | 620s | 434s | 91s |

## Memory Growth

| Run Range | Techniques | Insights | Meta-Insights |
|-----------|-----------|----------|---------------|
| 1-10 | 40 → 177 | 4 → 12 | 0 |
| 11-20 | 201 → 241 | 13 → 16 | 0 |
| 21-30 | 241 → 351 | 16 → 23 | 0 |
| 31-40 | 364 → 448 | 24 → 31 | 0 |

Techniques accumulate monotonically. No meta-insights have been promoted (threshold of 5 related insights not yet reached in any cluster).
