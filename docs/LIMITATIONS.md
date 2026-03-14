# Limitations

## Evaluation Limitations

1. **Single LLM evaluator.** All quality metrics are scored by Claude Opus. There is no human evaluation baseline, no inter-rater reliability measurement, and no comparison against human expert assessment. LLM self-evaluation may systematically overrate or underrate specific quality dimensions.

2. **Evaluator-generator alignment.** The same model family (Claude) generates the research and evaluates it. The evaluator may share systematic biases with the generator, failing to catch errors that a different model or human reviewer would notice.

3. **No downstream validation.** "Actionability" is scored on a scale but never validated by actually implementing the recommended changes. A run scoring 8/10 on actionability may contain recommendations that fail in practice.

## Statistical Limitations

4. **Small sample size.** 40 total runs, 12 ablation runs. No statistical significance testing is feasible. All findings are observations from a small dataset, not statistically validated conclusions.

5. **Topic confounds.** Quality scores vary significantly by topic. The ablation study used only 3 topics, which may not represent the system's behavior on other topic types.

6. **Temporal confounds.** Multiple architectural changes were often introduced in the same commit or close temporal proximity, making it difficult to isolate the causal effect of individual changes.

## System Limitations

7. **Subprocess timeouts.** Applied agents occasionally timeout at 200s when processing large research contexts. The system has partial recovery (extracting output before timeout) but this loses information.

8. **Cost tracking gap.** Per-run API costs are not tracked (estimated_cost_units = 0 in all 40 metrics entries). Cost analysis requires external billing data, which has not been correlated with run data.

9. **Web search quality.** DuckDuckGo results vary in quality and may not surface the most relevant papers or implementations. No comparison against academic search engines (Semantic Scholar, Google Scholar) has been conducted.

10. **Memory compounding unvalidated.** G-Memory accumulates techniques across runs (448 to date) but the causal effect on quality has not been tested. No controlled experiment comparing empty vs. populated memory exists.

## External Validity

11. **Single codebase target.** Most runs target the LoveSpark browser extension codebase (vanilla JS, Manifest V3). Findings about actionability may not generalize to other codebases or languages.

12. **Solo operator.** All runs, architectural decisions, and quality assessments are by a single person. No independent replication has been attempted.

13. **Claude-dependent.** The entire system depends on the Claude model family. Behavior with other LLMs (GPT-4, Gemini, open-source models) is unknown.

## Known Failure Patterns

14. **Topic-codebase mismatch.** When the research topic is fundamentally mismatched with the target codebase (e.g., GPU fine-tuning for a browser extension project), the system correctly discards the output but wastes compute. No pre-filtering mechanism exists.

15. **Factuality plateau.** Factuality scores have plateaued around 5.3 in the 8-agent configuration despite multiple interventions. The root cause is unclear.

16. **Dedup threshold fragility.** The deduplication threshold (0.39) was found by trial-and-error. It may be suboptimal for topics outside the tested distribution.
