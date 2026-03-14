# Research Questions

## RQ1: Does reducing overlapping agent scope improve output quality?

**Why it matters:** Multi-agent systems often deploy many agents with loosely defined roles, leading to redundant output that synthesis agents must reconcile. If scope boundaries are more important than agent count, system designers should invest in prompt engineering over agent proliferation.

**Status:** Tested. The 14→8 agent restructure removed 5 researchers with overlapping domains. The 8-agent configuration scored higher on quality (6.5 vs 6.0) and actionability (6.2 vs 6.1) across 12 ablation runs. Additionally, explicit OUT_OF_SCOPE declarations in agent prompts reduced technique overlap from 76% to 38%.

**Evidence:** metrics.jsonl (runs with 11 vs 5 agent invocations), ablation.py results, dedup.py overlap measurements.

## RQ2: Does adversarial critique improve factual grounding?

**Why it matters:** LLM-generated research frequently contains hallucinated citations and inflated confidence. A dedicated adversarial agent that challenges findings before acceptance could catch these issues — but may also add cost and latency without proportional benefit.

**Status:** Partially tested. Adding a critic agent (commit 088764f) and web search grounding (commit f742f39) improved factuality from 4.0 to 6.0 across subsequent runs. However, factuality has plateaued around 5.3 in the 8-agent configuration, and the critic's contribution vs. web search's contribution has not been isolated.

**Evidence:** metrics.jsonl factuality scores before/after commit 088764f and f742f39. Confound: both changes were introduced close together.

## RQ3: What is the quality/cost tradeoff between different agent counts?

**Why it matters:** Each additional agent consumes tokens and adds latency. If fewer agents can match quality, the system becomes cheaper and faster. But too few agents may miss important dimensions of a research topic.

**Status:** Tested via 12-run ablation across 4 configurations (14, 10, 8, 7 agents) and 3 topics. The 8-agent configuration was adopted as the best tradeoff: comparable or better quality than 14 agents, with approximately 55% fewer agent invocations. The 7-agent configuration showed a factuality dip (5.0 vs 5.9), suggesting the quality gate is load-bearing.

**Evidence:** Ablation runs in metrics.jsonl. Caveat: 3 topics is a small sample, and cost tracking (USD) was not implemented during the ablation period.

## RQ4: Does cross-run memory improve research quality over time?

**Why it matters:** If the system can learn from past runs, it should produce better research on related topics without re-discovering known findings. This would demonstrate compounding intelligence — a key claim of the G-Memory design.

**Status:** Not yet validated. The system has accumulated 448 techniques and 31 insights across 40 runs. Memory grows monotonically. However, no controlled experiment has compared runs with empty vs. populated memory on the same topic, so the causal effect on quality is unknown.

**Evidence:** Memory growth tracked in metrics.jsonl (memory_techniques, memory_insights fields). No isolation experiment conducted.

## RQ5: Can semantic deduplication reduce technique overlap without losing coverage?

**Why it matters:** Parallel agents discovering the same technique under different names is a core problem in multi-agent systems. Deduplication must be aggressive enough to catch synonyms but conservative enough to preserve genuinely distinct findings.

**Status:** Tested. Jaccard + bigram similarity with complete-linkage clustering at threshold 0.39 reduces overlap from 76% to 38%. Higher thresholds (0.50) caused over-merging — all techniques collapsed into one cluster on 1/3 topics (commit 27f0358 reverted this). No coverage loss has been measured at 0.39, but "coverage" is scored by the judge, not independently verified.

**Evidence:** dedup.py measurements, metrics.jsonl overlap_ratio field, commit 27f0358 (revert).
