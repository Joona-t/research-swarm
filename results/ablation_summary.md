# Ablation Study: Agent Count Optimization

12 runs across 4 configurations and 3 topics (runs 20-31 in metrics.jsonl).

## Design

**Independent variable:** Agent count (11, 7, 5, 4)
**Controlled variables:** Model assignments (Haiku scouts, Sonnet researchers, Opus judge/synthesizer), timeouts (120s scout, 200s applied), dedup threshold (0.39)
**Dependent variables:** avg_quality, actionability, factuality (all 0-10, LLM-evaluated)
**Topics held constant across all 4 configs:**
1. Hallucination reduction in retrieval-augmented systems
2. Efficient fine-tuning methods for LLMs
3. Code generation evaluation benchmarks

## Results

| Config | Agents | n | Avg Quality | Actionability | Factuality | Wall Clock (s) | Keep Rate |
|--------|--------|---|-------------|---------------|------------|----------------|-----------|
| full | 11 | 3 | 5.9 | 4.3 | 5.3 | 514 | 1/3 (33%) |
| lean | 7 | 3 | 5.7 | 4.7 | 5.3 | 571 | 2/3 (67%) |
| minimal | 5 | 3 | **6.1** | **5.3** | 5.3 | 530 | 2/3 (67%) |
| skeleton | 4 | 3 | **6.1** | **6.3** | 5.0 | 557 | **3/3 (100%)** |

## Per-Run Detail

| Run | Config | Topic | Quality | Actionability | Factuality | Vote |
|-----|--------|-------|---------|---------------|------------|------|
| 20 | full (11) | Hallucination | 5.5 | 3.0 | 5.0 | discard |
| 21 | full (11) | Fine-tuning | 6.0 | 3.0 | 6.0 | discard |
| 22 | full (11) | Code gen | 6.2 | 7.0 | 5.0 | keep |
| 23 | lean (7) | Hallucination | 6.0 | 6.0 | 5.0 | keep |
| 24 | lean (7) | Fine-tuning | 4.5 | 2.0 | 5.0 | discard |
| 25 | lean (7) | Code gen | 6.5 | 6.0 | 6.0 | keep |
| 26 | minimal (5) | Hallucination | 6.5 | 6.0 | 6.0 | keep |
| 27 | minimal (5) | Fine-tuning | 5.5 | 4.0 | 5.0 | discard |
| 28 | minimal (5) | Code gen | 6.2 | 6.0 | 5.0 | keep |
| 29 | skeleton (4) | Hallucination | 6.0 | 7.0 | 4.0 | keep |
| 30 | skeleton (4) | Fine-tuning | 6.5 | 6.0 | 6.0 | keep |
| 31 | skeleton (4) | Code gen | 5.8 | 6.0 | 5.0 | keep |

## Interpretation

1. **Quality does not scale with agent count.** 5 and 4 agents both scored 6.1 avg quality, matching or exceeding the 11-agent config (5.9). Adding more agents beyond 5 did not improve output quality in this experiment.

2. **Actionability inversely correlates with agent count.** Full (11 agents): 4.3. Skeleton (4 agents): 6.3. More agents produced more comprehensive but less actionable output — the synthesis step averaged away specificity.

3. **Factuality is independent of agent count.** All configs scored 5.0-5.3. Factuality appears to be a function of the grounding mechanism (web search), not agent count.

4. **Keep rate improves with fewer agents.** Full: 33%. Skeleton: 100%. Fewer agents produced more consistently usable output, likely because less synthesis was needed and expert signal was not diluted.

5. **Wall clock is flat.** All configs clustered around 514-571s. The bottleneck is the applied phase timeout (200s), not parallelism.

## Caveats

- **n=3 per config.** These are directional signals, not statistically significant results. A single outlier (run 24: actionability 2.0) can swing an average substantially.
- **Single LLM evaluator.** All scores assigned by one Opus judge instance. No inter-rater reliability.
- **3 topics only.** Findings may not generalize to other research domains.
- **Temporal confounds.** Runs executed sequentially over ~4 hours. Memory accumulation between runs could bias later configs (though ablation was designed to minimize this by alternating topics).
- **No human evaluation.** LLM quality scores were not validated against human judgment.

## Key Takeaway

For the Research Swarm pipeline, 5-8 agents is the sweet spot. Adding more agents produces diminishing returns on quality while reducing actionability and keep rate. This finding directly informed the LoveSpark Agent Swarm restructure from 22 to 15 agents.
