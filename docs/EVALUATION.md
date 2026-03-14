# Evaluation

## Scoring System

All metrics are scored on a 0-10 integer scale by the judge agent (Claude Opus). The judge receives the complete research output and scores each dimension independently.

### Metric Definitions

#### Actionability (Primary Metric)
**Definition:** Can these findings be implemented within one week by a solo developer working on the target codebase? Requires specific code changes, file paths, and keep/discard criteria for proposed experiments.

**Score interpretation:**
- 8-10: Immediately implementable with minimal interpretation
- 6-7: Implementable with some additional research or adaptation
- 4-5: Interesting but requires significant work to translate into code changes
- 1-3: Academic survey with no clear implementation path
- 0: Empty or catastrophically failed output

**Threshold:** Runs scoring < 6 are discarded.

**What this metric does NOT capture:** Whether the recommended changes actually improve the target system. No follow-up measurement is conducted.

#### Coverage
**Definition:** Does the research address the topic's major dimensions? A topic like "multi-agent consensus" should cover convergence algorithms, round management, dissent handling, and scaling behavior.

**What this metric does NOT capture:** Whether important dimensions were missed entirely (unknown unknowns).

#### Accuracy
**Definition:** Are the technical claims in the research factually correct? Does the research correctly describe how cited systems work?

**What this metric does NOT capture:** Subtle errors that the judge (an LLM) might not catch due to training data limitations.

#### Factuality
**Definition:** Are findings grounded in verifiable sources? Are cited papers real? Do referenced repositories exist?

**What this metric does NOT capture:** Whether the cited sources actually support the claims made (citation relevance vs. citation existence).

## Quality Gate Logic

```
IF critic_verdict == "fail":
    DISCARD (override all scores)
ELIF actionability < 6:
    DISCARD
ELIF actionability < 6 AND confidence < 0.6:
    DISCARD (stricter threshold for low-confidence runs)
ELSE:
    KEEP
```

## Automatic vs. Human Metrics

| Metric | Type | Evaluator |
|--------|------|-----------|
| Actionability | Automatic | Claude Opus (judge agent) |
| Coverage | Automatic | Claude Opus (judge agent) |
| Accuracy | Automatic | Claude Opus (judge agent) |
| Factuality | Automatic | Claude Opus (judge agent) |
| Critic verdict | Automatic | Claude Sonnet (critic agent) |
| Overlap ratio | Automatic | dedup.py (algorithmic) |
| Wall clock time | Automatic | orchestrator.py (system timer) |
| Agent success rate | Automatic | orchestrator.py (process exit codes) |
| Human assessment | **Not implemented** | — |

## Deduplication Metrics

Technique overlap is measured algorithmically, not by LLM scoring:

1. Raw technique count: total techniques extracted across all researchers
2. Deduplicated technique count: unique techniques after clustering
3. Overlap ratio: `1 - (deduped / raw)`

**Method:** Jaccard similarity on canonicalized word sets (60% weight) + bigram overlap (40% weight), with complete-linkage clustering at threshold 0.39.

## Regression Detection

The metrics system (metrics.py) tracks rolling averages and flags regressions:
- Rolling window: configurable (default: 5 runs)
- Regression threshold: metric drops > 15% below rolling average
- Alerts appear in dashboard and metric reports

This is an early warning system, not a formal statistical test.
