"""Research Swarm — Quality gate voting and keep/discard logic."""

import json


def _safe_num(val, default=0) -> float:
    """Coerce a value to a number, returning default if not possible."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            pass
    return default


def _find_key(d: dict, *candidates, default=None):
    """Return the first matching value from a dict, trying multiple key names."""
    for key in candidates:
        if key in d:
            return d[key]
    return default


def evaluate_critic(critic_output: dict) -> dict:
    """Parse and summarize critic findings."""
    issues = _find_key(critic_output, "issues", "concerns", "problems", default=[])
    if not isinstance(issues, list):
        issues = []
    verdict = _find_key(critic_output, "verdict", "assessment", "overall_verdict",
                        default="concerns")
    confidence = _safe_num(_find_key(critic_output, "confidence", "confidence_score",
                                      default=0.5))

    high_severity = [i for i in issues if isinstance(i, dict) and i.get("severity") == "high"]
    medium_severity = [i for i in issues if isinstance(i, dict) and i.get("severity") == "medium"]

    return {
        "verdict": verdict,
        "confidence": confidence,
        "total_issues": len(issues),
        "high_severity": len(high_severity),
        "medium_severity": len(medium_severity),
        "issues": issues,
    }


def evaluate_judge(judge_output: dict, min_actionability: int = 6,
                   researcher_confidence: float = 0.7,
                   critic_verdict: str = "concerns") -> dict:
    """Parse judge scores and make the keep/discard decision.

    Confidence-weighted consensus: if mean researcher confidence is low,
    require higher actionability to keep. This prevents low-confidence
    speculative findings from passing the gate.
    """
    coverage = _safe_num(_find_key(judge_output, "coverage_score", "coverage", default=0))
    accuracy = _safe_num(_find_key(judge_output, "accuracy_score", "accuracy", default=0))
    actionability = _safe_num(_find_key(judge_output, "actionability_score",
                                         "actionability", default=0))
    factuality = _safe_num(_find_key(judge_output, "factuality_score",
                                      "factuality", default=0))
    vote = _find_key(judge_output, "quality_vote", "vote", "decision", default="discard")
    if isinstance(vote, str):
        vote = vote.lower().strip()
    notes = str(_find_key(judge_output, "notes", "explanation", "reasoning",
                           "rationale", default=""))

    # Dynamic threshold: low-confidence research needs higher actionability
    effective_threshold = min_actionability
    if researcher_confidence < 0.6:
        effective_threshold = min_actionability + 1

    # Override vote only to discard — never override an explicit discard
    if actionability < effective_threshold:
        vote = "discard"

    # Critic "fail" is a strong discard signal
    if critic_verdict == "fail" and vote == "keep":
        vote = "discard"
        notes += " [Overridden: critic verdict was FAIL]"

    # Include factuality in average (4 dimensions now)
    dimensions = [coverage, accuracy, actionability]
    if factuality > 0:
        dimensions.append(factuality)
    avg = round(sum(dimensions) / len(dimensions), 1)

    return {
        "coverage": coverage,
        "accuracy": accuracy,
        "factuality": factuality,
        "actionability": actionability,
        "vote": vote,
        "notes": notes,
        "avg_score": avg,
        "researcher_confidence": round(researcher_confidence, 2),
        "effective_threshold": effective_threshold,
        "critic_verdict": critic_verdict,
    }


def format_gate_report(critic_eval: dict, judge_eval: dict) -> str:
    """Format a human-readable quality gate report."""
    lines = [
        "## Quality Gate Report",
        "",
        f"**Critic verdict:** {critic_eval['verdict']} "
        f"(confidence: {critic_eval['confidence']:.0%})",
        f"  Issues: {critic_eval['total_issues']} total "
        f"({critic_eval['high_severity']} high, {critic_eval['medium_severity']} medium)",
    ]

    if critic_eval["issues"]:
        lines.append("")
        for issue in critic_eval["issues"][:5]:
            severity = issue.get("severity", "?")
            claim = issue.get("claim", "")[:60]
            problem = issue.get("problem", "")[:80]
            lines.append(f"  [{severity}] {claim}: {problem}")

    # Factuality line only if scored
    factuality_line = ""
    if judge_eval.get("factuality", 0) > 0:
        factuality_line = f"\n  Factuality:    {judge_eval['factuality']}/10"

    # Confidence weighting note
    conf_note = ""
    if judge_eval.get("effective_threshold", 6) > 6:
        conf_note = (
            f"\n  (Low researcher confidence {judge_eval.get('researcher_confidence', 0):.0%} "
            f"→ threshold raised to {judge_eval['effective_threshold']})"
        )

    lines.extend([
        "",
        f"**Judge scores:**",
        f"  Coverage:      {judge_eval['coverage']}/10",
        f"  Accuracy:      {judge_eval['accuracy']}/10",
        f"  Actionability: {judge_eval['actionability']}/10{factuality_line}",
        f"  Average:       {judge_eval['avg_score']}/10{conf_note}",
        "",
        f"**Decision: {judge_eval['vote'].upper()}**",
        f"  {judge_eval['notes']}",
    ])

    return "\n".join(lines)
