# Research Log

A lab-notebook-style record of development, derived from commit history and run data.

## 2026-03-13: Initial System (commit f00dbb9)

**Question:** Can a phased multi-agent pipeline produce actionable research output?

**Change:** Built the initial 14-agent system with 5 phases (scout, research, applied, quality, synthesis). Based on three sources: Blitz-Swarm's parallel architecture, Karpathy's autoresearch loop, and LoveSpark's 22-agent swarm.

**Result:** System runs, but no metrics to measure quality yet. Early runs showed high researcher overlap — multiple agents returning the same findings under different names.

**Next move:** Add instrumentation before making more changes.

## 2026-03-13: Self-Improvement Cycle (commits 26ae486 → 94c6334)

**Question:** Can the system research its own weaknesses and apply the findings?

**Changes (4 commits in ~2 hours):**
1. JSON compliance: PARSE schemas, retry logic (from own research brief on structured output)
2. G-Memory: decay scoring, temporal validity, insight promotion
3. Context injection: narrative casting, token budgeting
4. Role differentiation: OUT_OF_SCOPE blocks, capability registry

**Result:** Rapid improvement in system reliability. Parse failures reduced. Researcher output became more distinct. However, no metrics yet — all assessment was qualitative.

**Interpretation:** The system can research its own problems and the findings are implementable. But without metrics, I cannot distinguish real improvements from confirmation bias.

## 2026-03-13: Metrics System (commit e252b66)

**Question:** What should I measure?

**Change:** Added per-run instrumentation (metrics.jsonl), persistent run log (research-log.tsv), and regression detection. Chose 4 quality dimensions: coverage, accuracy, actionability, factuality. Made actionability the primary metric.

**Result:** All subsequent changes became measurable. This was the inflection point.

**Next move:** Use the system to research its own weaknesses, now with measurement.

## 2026-03-13–14: Targeted Improvements (commits 1227f72 → a699f52)

**Question:** What are the system's biggest measurable weaknesses?

**Changes (3 commits):**
1. Timeout handling: failure policy, partial recovery (from research on timeout patterns)
2. Adversarial critic + confidence gate (from research on hallucination reduction)
3. Applied agent quality: confidence propagation, CoT scaffolding (from research on applied agent failures)

**Results:**
- Factuality: 4.0 → 5.0 (after critic)
- Applied success: 2/3 → 3/3 agents producing usable output
- Timeouts: still occur but with partial recovery

**Interpretation:** Targeted research-then-implement cycles produce measurable improvements. The system is genuinely improving its own performance through its own output.

## 2026-03-14: Dedup + Grounding + Compression (commit 779f26b)

**Question:** Can algorithmic post-processing reduce the 76% technique overlap?

**Change:** Added semantic deduplication (Jaccard + bigram, complete-linkage clustering), evidence labeling, and priority-aware context compression.

**Result:** Overlap reduced from 76% to 38%. Evidence labeling tags every technique with source type (peer_reviewed, preprint, repo, unverified).

**Interpretation:** Algorithmic dedup is highly effective at the identified threshold. The question is whether it's aggressive enough or too aggressive.

## 2026-03-14: Web Search (commit f742f39)

**Question:** Will real web search fix the factuality problem?

**Change:** Added a custom MCP server (search_server.py) giving scouts access to DuckDuckGo search and page fetching.

**Result:** Factuality jumped from 4.0 to 6.0. This was the single largest improvement in any metric.

**Interpretation:** Grounding in real sources is critical. The system was hallucinating paper titles and repository names before this change. Web search largely eliminated that class of error.

## 2026-03-14: Agent Count Ablation (commit f4149cc)

**Question:** How many agents do we actually need?

**Change:** Ran 12 experiments across 4 configurations (14, 10, 8, 7 agents) and 3 topics. Restructured to 8 agents based on results.

**Result:**
| Config | Quality | Actionability | Factuality |
|--------|---------|---------------|------------|
| 14 agents | 6.0 | 6.1 | 4.4 |
| 10 agents | 5.7 | 4.7 | 5.3 |
| 8 agents | 6.5 | 6.2 | 5.9 |
| 7 agents | 6.1 | 6.3 | 5.0 |

**Interpretation:** 8 agents is the sweet spot. The 5 removed researchers had overlapping coverage. The 7-agent skeleton showed a factuality dip, suggesting the quality gate (critic + judge) is load-bearing and should not be cut.

## 2026-03-14: Dedup Threshold Tuning (commits 71df964, 27f0358)

**Question:** Can we push the dedup threshold higher (0.39 → 0.50) to catch more duplicates?

**Change:** Raised threshold to 0.50 as part of 3 Karpathy-inspired experiments.

**Result:** Overlap=1.0 on 1/3 topics — all techniques merged into one cluster. Reverted to 0.39 within hours.

**Interpretation:** The dedup threshold is sensitive and topic-dependent. 0.39 works acceptably. Adaptive thresholds might help but are not yet implemented.

## 2026-03-14: Post-Ablation Production Runs (runs 32–40)

**Question:** Does the 8-agent system perform reliably across diverse topics?

**Change:** Ran 9 consecutive research topics on the 8-agent configuration: chain-of-thought prompting, speculative decoding, autonomous self-improvement, cost optimization, parallel vs sequential pipelines, agent role specialization.

**Result:** 9/9 kept. Average quality 6.7, average actionability 6.7, average factuality 6.1. Consistently better than pre-ablation runs.

**Interpretation:** The 8-agent configuration is stable and producing reliably good output. The system appears to have crossed a quality threshold where most well-targeted topics produce keepable research.
