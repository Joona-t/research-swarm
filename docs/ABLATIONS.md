# Ablations and Major Design Changes

Each entry documents a significant architectural change, the hypothesis behind it, and the measured result.

## 1. JSON Compliance (commit 26ae486)

**Change:** Added PARSE output schemas with field descriptions, single retry on malformed JSON, two-pass reasoning for complex agents.

**Hypothesis:** Structured output schemas and retry logic will reduce parse failures without degrading reasoning quality.

**Result:** Parse failures reduced qualitatively (not measured precisely before metrics system existed). Kept.

**Evidence strength:** Weak — no before/after metrics. Change predates the metrics system.

## 2. Context Injection: Narrative Casting (commit 296813e)

**Change:** Scout findings passed to researchers as natural language narratives instead of raw JSON data.

**Hypothesis:** Researchers will produce better analysis when receiving human-readable context rather than structured data blobs.

**Result:** Qualitative improvement in researcher output coherence. Not quantitatively measured.

**Evidence strength:** Weak — subjective assessment only.

## 3. Role Differentiation: OUT_OF_SCOPE (commit 94c6334)

**Change:** Added explicit OUT_OF_SCOPE declarations to each researcher's system prompt, plus a CAPABILITY_REGISTRY mapping coverage boundaries.

**Hypothesis:** Explicit negative scope will reduce technique overlap between researchers more effectively than positive scope alone.

**Result:** Technique overlap reduced (measured in subsequent runs), but the effect is confounded with later deduplication changes.

**Evidence strength:** Moderate — directionally positive but not isolated.

## 4. Metrics System (commit e252b66)

**Change:** Added per-run instrumentation (metrics.jsonl), research log (research-log.tsv), and regression detection.

**Hypothesis:** Without measurement, architectural changes are guesswork.

**Result:** All subsequent changes could be measured. This was the single most important infrastructure addition.

**Evidence strength:** N/A — infrastructure change, not a quality intervention.

## 5. Adversarial Critic + Confidence Gate (commit 088764f)

**Change:** Added a dedicated critic agent (Sonnet) that adversarially challenges research findings before the judge scores them. Added confidence-weighted gating.

**Hypothesis:** An adversarial review step will catch hallucinated citations and inflated claims, improving factuality.

**Result:** Factuality improved from 4.0 to 5.0 in subsequent runs. However, the confidence pipeline had a bug (inverted override) that was fixed in commit e7c2cb6.

**Evidence strength:** Moderate — factuality improved, but web search (added shortly after) also contributed.

## 6. Applied Agent Quality (commit a699f52)

**Change:** Added confidence propagation from researchers to applied agents, two-pass generation, chain-of-thought scaffolding, and trace IDs.

**Hypothesis:** Applied agents fail because they receive research findings without confidence signals, making it hard to prioritize.

**Result:** Applied phase success rate improved from 2/3 to 3/3 agents producing usable output.

**Evidence strength:** Moderate — clear improvement, but small sample and multiple changes bundled.

## 7. Semantic Deduplication (commit 779f26b)

**Change:** Implemented Jaccard + bigram similarity with complete-linkage clustering. Canonicalization strips filler words and applies synonym mapping.

**Hypothesis:** Algorithmic deduplication will reduce the 76% technique overlap that makes research briefs repetitive.

**Result:** Overlap reduced from 76% to 38% at threshold 0.39. Threshold 0.50 over-merged (overlap=1.0 on 1/3 topics) and was reverted (commit 27f0358).

**Evidence strength:** Strong — measured before/after, with a revert confirming threshold sensitivity.

## 8. Web Search via MCP (commit f742f39)

**Change:** Added a custom MCP server (search_server.py) giving scouts access to DuckDuckGo web search and page fetching.

**Hypothesis:** Real web search will ground citations in actual sources, improving factuality.

**Result:** Factuality improved from 4.0 to 6.0 in runs following this change. This was the single largest factuality improvement.

**Evidence strength:** Strong — clear before/after improvement, large effect size.

## 9. Agent Count Ablation: 14 → 8 (commit f4149cc)

**Change:** Reduced active agents from 14 to 8 by consolidating 5 overlapping researchers into 2 well-scoped researchers. All 14 agent prompts preserved in code; roster configured via config.toml.

**Hypothesis:** Fewer, better-scoped agents will match or exceed the quality of many overlapping agents.

**Result:** 12-run ablation across 4 configs and 3 topics. 8-agent config scored higher on quality (6.5 vs 6.0) and actionability (6.2 vs 6.1) than 14-agent baseline.

**Evidence strength:** Moderate — consistent across 3 topics, but 3 topics is a small sample.

## 10. Confidence Pipeline Fix (commit e7c2cb6)

**Change:** Fixed inverted override in confidence pipeline. Wired critic verdict into quality gate decision.

**Hypothesis:** The confidence gate was inverting its effect — high-confidence runs were being penalized.

**Result:** Bug fix. Critic verdict now correctly overrides judge scores on "fail."

**Evidence strength:** Strong — code fix with clear before/after behavior.

## 11. Dedup Threshold Revert (commit 27f0358)

**Change:** Reverted dedup threshold from 0.50 back to 0.39.

**Hypothesis:** Threshold 0.50 would catch more duplicates.

**Result:** Threshold 0.50 caused overlap=1.0 on 1/3 ablation topics (all techniques merged into one cluster). Reverted.

**Evidence strength:** Strong — clear failure, immediate revert.
