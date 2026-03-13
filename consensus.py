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


def evaluate_judge(judge_output: dict, min_actionability: int = 6) -> dict:
    """Parse judge scores and make the keep/discard decision."""
    coverage = _safe_num(_find_key(judge_output, "coverage_score", "coverage", default=0))
    accuracy = _safe_num(_find_key(judge_output, "accuracy_score", "accuracy", default=0))
    actionability = _safe_num(_find_key(judge_output, "actionability_score",
                                         "actionability", default=0))
    vote = _find_key(judge_output, "quality_vote", "vote", "decision", default="discard")
    if isinstance(vote, str):
        vote = vote.lower().strip()
    notes = str(_find_key(judge_output, "notes", "explanation", "reasoning",
                           "rationale", default=""))

    # Override vote if actionability is below threshold
    if actionability < min_actionability:
        vote = "discard"
    elif actionability >= min_actionability and vote == "discard":
        # Judge voted discard but score says keep — trust the score
        vote = "keep"

    return {
        "coverage": coverage,
        "accuracy": accuracy,
        "actionability": actionability,
        "vote": vote,
        "notes": notes,
        "avg_score": round((coverage + accuracy + actionability) / 3, 1),
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

    lines.extend([
        "",
        f"**Judge scores:**",
        f"  Coverage:      {judge_eval['coverage']}/10",
        f"  Accuracy:      {judge_eval['accuracy']}/10",
        f"  Actionability: {judge_eval['actionability']}/10",
        f"  Average:       {judge_eval['avg_score']}/10",
        "",
        f"**Decision: {judge_eval['vote'].upper()}**",
        f"  {judge_eval['notes']}",
    ])

    return "\n".join(lines)
