"""Research Swarm — Per-run metrics collection and analysis.

Every run produces a structured metrics record appended to metrics.jsonl.
This is the swarm's lab notebook — immutable, append-only, machine-readable.

Metrics collected per run:
  - Phase success rates (ok/total per phase)
  - Per-agent timing (wall clock seconds)
  - Technique overlap ratio (deduped/raw — measures researcher differentiation)
  - Quality gate scores (coverage, accuracy, actionability)
  - Token cost estimate (chars sent × model cost weight)
  - Total wall clock time
  - Memory state (techniques, insights, meta-insights at run start)

Analysis functions compute:
  - Rolling averages across N runs
  - Regression detection (metric dropped >threshold from rolling avg)
  - Before/after comparison for A/B testing changes
"""

import json
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

METRICS_PATH = Path(__file__).parent / "metrics.jsonl"

# Relative cost weights per model tier (normalized to haiku = 1)
MODEL_COST_WEIGHT = {
    "haiku": 1.0,
    "sonnet": 3.0,
    "opus": 15.0,
}


@dataclass
class PhaseMetrics:
    """Metrics for a single phase execution."""
    phase: str
    agents_total: int = 0
    agents_ok: int = 0
    agents_error: int = 0
    agents_timeout: int = 0
    agents_raw: int = 0
    wall_clock_s: float = 0.0
    context_chars_sent: int = 0

    @property
    def success_rate(self) -> float:
        return self.agents_ok / max(self.agents_total, 1)


@dataclass
class RunMetrics:
    """Complete metrics for a single swarm run."""
    # Identity
    run_id: str = ""
    topic: str = ""
    timestamp: float = 0.0
    git_commit: str = ""

    # Phase metrics
    phases: dict = field(default_factory=dict)  # phase_name -> PhaseMetrics dict

    # Quality gate
    coverage: float = 0.0
    accuracy: float = 0.0
    factuality: float = 0.0
    actionability: float = 0.0
    avg_quality: float = 0.0
    vote: str = ""
    researcher_confidence: float = 0.0
    critic_issues_total: int = 0
    critic_issues_high: int = 0

    # Differentiation
    techniques_raw: int = 0          # before dedup
    techniques_deduped: int = 0      # after dedup
    overlap_ratio: float = 0.0       # 1 - (deduped / raw) — lower is better

    # Cost
    total_wall_clock_s: float = 0.0
    total_agent_invocations: int = 0
    estimated_cost_units: float = 0.0  # chars × model_weight, arbitrary units

    # Memory state at run start
    memory_techniques: int = 0
    memory_insights: int = 0
    memory_meta_insights: int = 0
    memory_prior_runs: int = 0


class MetricsCollector:
    """Collects metrics during a swarm run, then persists to JSONL."""

    def __init__(self):
        self.run = RunMetrics()
        self._phase_timers: dict[str, float] = {}
        self._agent_timings: list[dict] = []
        self._run_start: float = 0.0

    def start_run(self, run_id: str, topic: str, git_commit: str = ""):
        self.run = RunMetrics(
            run_id=run_id,
            topic=topic,
            timestamp=time.time(),
            git_commit=git_commit,
        )
        self._run_start = time.monotonic()

    def record_memory_state(self, stats: dict):
        self.run.memory_techniques = stats.get("techniques", 0)
        self.run.memory_insights = stats.get("insights", 0)
        self.run.memory_meta_insights = stats.get("meta_insights", 0)
        self.run.memory_prior_runs = stats.get("research_runs", 0)

    def start_phase(self, phase: str):
        self._phase_timers[phase] = time.monotonic()

    def end_phase(self, phase: str, outputs: list[dict], context_chars: int = 0):
        wall_clock = time.monotonic() - self._phase_timers.get(phase, time.monotonic())

        ok = 0
        errors = 0
        timeouts = 0
        raw = 0

        for o in outputs:
            if o.get("_error"):
                msg = o.get("_error_msg", "")
                if "Timed out" in msg or "TIMEOUT" in msg:
                    timeouts += 1
                else:
                    errors += 1
            elif o.get("_raw"):
                raw += 1
            else:
                ok += 1

        pm = PhaseMetrics(
            phase=phase,
            agents_total=len(outputs),
            agents_ok=ok,
            agents_error=errors,
            agents_timeout=timeouts,
            agents_raw=raw,
            wall_clock_s=round(wall_clock, 1),
            context_chars_sent=context_chars,
        )

        self.run.phases[phase] = asdict(pm)
        self.run.total_agent_invocations += len(outputs)

    def record_agent_timing(self, agent_id: str, model: str,
                            elapsed_s: float, context_chars: int):
        """Record per-agent timing for cost estimation."""
        self._agent_timings.append({
            "agent_id": agent_id,
            "model": model,
            "elapsed_s": round(elapsed_s, 1),
            "context_chars": context_chars,
        })
        # Accumulate cost estimate
        weight = MODEL_COST_WEIGHT.get(model, 3.0)
        self.run.estimated_cost_units += context_chars * weight

    def record_quality_gate(self, judge_eval: dict, critic_eval: dict):
        self.run.coverage = judge_eval.get("coverage", 0)
        self.run.accuracy = judge_eval.get("accuracy", 0)
        self.run.factuality = judge_eval.get("factuality", 0)
        self.run.actionability = judge_eval.get("actionability", 0)
        self.run.avg_quality = judge_eval.get("avg_score", 0)
        self.run.vote = judge_eval.get("vote", "")
        self.run.researcher_confidence = judge_eval.get("researcher_confidence", 0)
        self.run.critic_issues_total = critic_eval.get("total_issues", 0)
        self.run.critic_issues_high = critic_eval.get("high_severity", 0)

    def record_technique_counts(self, raw_count: int, deduped_count: int):
        self.run.techniques_raw = raw_count
        self.run.techniques_deduped = deduped_count
        if raw_count > 0:
            self.run.overlap_ratio = round(1 - (deduped_count / raw_count), 3)

    def finalize(self):
        self.run.total_wall_clock_s = round(
            time.monotonic() - self._run_start, 1
        )
        self.run.estimated_cost_units = round(self.run.estimated_cost_units)

    def save(self):
        """Append metrics record to JSONL file."""
        record = asdict(self.run)
        record["_agent_timings"] = self._agent_timings
        with open(METRICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------
# Analysis — compute trends and detect regressions
# ---------------------------------------------------------------------------


def load_all_metrics() -> list[dict]:
    """Load all metrics records from JSONL."""
    if not METRICS_PATH.exists():
        return []
    records = []
    with open(METRICS_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def compute_rolling_avg(records: list[dict], key: str,
                        window: int = 5) -> list[float]:
    """Compute rolling average for a top-level numeric metric."""
    values = [r.get(key, 0) for r in records if isinstance(r.get(key), (int, float))]
    if len(values) < window:
        return values
    avgs = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        avgs.append(round(statistics.mean(values[start:i + 1]), 2))
    return avgs


def detect_regressions(records: list[dict], window: int = 3,
                       threshold: float = 0.15) -> list[dict]:
    """Detect metrics that regressed >threshold from rolling average.

    Returns list of {metric, current, rolling_avg, delta_pct} dicts.

    Checks: actionability, avg_quality, overlap_ratio (inverted — higher is worse),
    and per-phase success rates.
    """
    if len(records) < window + 1:
        return []

    latest = records[-1]
    prior = records[-(window + 1):-1]
    regressions = []

    # Quality metrics (higher is better)
    for key in ("actionability", "avg_quality", "accuracy", "coverage", "factuality"):
        current = latest.get(key, 0)
        prior_vals = [r.get(key, 0) for r in prior if isinstance(r.get(key), (int, float))]
        if not prior_vals:
            continue
        avg = statistics.mean(prior_vals)
        if avg > 0:
            delta = (current - avg) / avg
            if delta < -threshold:
                regressions.append({
                    "metric": key,
                    "current": current,
                    "rolling_avg": round(avg, 2),
                    "delta_pct": round(delta * 100, 1),
                    "direction": "dropped",
                })

    # Overlap ratio (lower is better — regression means it went UP)
    current_overlap = latest.get("overlap_ratio", 0)
    prior_overlaps = [r.get("overlap_ratio", 0) for r in prior
                      if isinstance(r.get("overlap_ratio"), (int, float))]
    if prior_overlaps:
        avg_overlap = statistics.mean(prior_overlaps)
        if avg_overlap > 0:
            delta = (current_overlap - avg_overlap) / avg_overlap
            if delta > threshold:
                regressions.append({
                    "metric": "overlap_ratio",
                    "current": current_overlap,
                    "rolling_avg": round(avg_overlap, 3),
                    "delta_pct": round(delta * 100, 1),
                    "direction": "increased (worse)",
                })

    # Per-phase success rates
    for phase_name, phase_data in latest.get("phases", {}).items():
        if not isinstance(phase_data, dict):
            continue
        total = phase_data.get("agents_total", 0)
        ok = phase_data.get("agents_ok", 0)
        if total == 0:
            continue
        current_rate = ok / total

        prior_rates = []
        for r in prior:
            p = r.get("phases", {}).get(phase_name, {})
            if isinstance(p, dict) and p.get("agents_total", 0) > 0:
                prior_rates.append(p["agents_ok"] / p["agents_total"])

        if not prior_rates:
            continue
        avg_rate = statistics.mean(prior_rates)
        if avg_rate > 0:
            delta = (current_rate - avg_rate) / avg_rate
            if delta < -threshold:
                regressions.append({
                    "metric": f"{phase_name}_success_rate",
                    "current": round(current_rate, 2),
                    "rolling_avg": round(avg_rate, 2),
                    "delta_pct": round(delta * 100, 1),
                    "direction": "dropped",
                })

    return regressions


def format_metrics_report(records: list[dict], last_n: int = 5) -> str:
    """Format a human-readable metrics report from the last N runs."""
    if not records:
        return "No metrics recorded yet."

    recent = records[-last_n:]

    lines = [
        f"## Swarm Metrics Report ({len(records)} total runs, showing last {len(recent)})",
        "",
        "| Run | Topic | Quality | Action. | Overlap | Applied% | Wall(s) | Cost |",
        "|-----|-------|---------|---------|---------|----------|---------|------|",
    ]

    for i, r in enumerate(recent):
        topic = r.get("topic", "?")[:30]
        quality = r.get("avg_quality", 0)
        action = r.get("actionability", 0)
        overlap = r.get("overlap_ratio", 0)
        wall = r.get("total_wall_clock_s", 0)
        cost = r.get("estimated_cost_units", 0)

        # Applied success rate
        applied = r.get("phases", {}).get("applied", {})
        if isinstance(applied, dict) and applied.get("agents_total", 0) > 0:
            applied_pct = f"{applied['agents_ok']}/{applied['agents_total']}"
        else:
            applied_pct = "—"

        lines.append(
            f"| {len(records) - last_n + i + 1} "
            f"| {topic} "
            f"| {quality} "
            f"| {action} "
            f"| {overlap:.0%} "
            f"| {applied_pct} "
            f"| {wall:.0f} "
            f"| {cost:,.0f} |"
        )

    # Trends
    if len(records) >= 3:
        lines.extend(["", "### Trends (last 3 runs)"])
        last3 = records[-3:]
        for key, label in [
            ("actionability", "Actionability"),
            ("avg_quality", "Avg Quality"),
            ("overlap_ratio", "Overlap Ratio"),
            ("total_wall_clock_s", "Wall Clock (s)"),
        ]:
            vals = [r.get(key, 0) for r in last3]
            if all(isinstance(v, (int, float)) for v in vals):
                trend = "→"
                if vals[-1] > vals[0] * 1.05:
                    trend = "↑" if key != "overlap_ratio" else "↑ (worse)"
                elif vals[-1] < vals[0] * 0.95:
                    trend = "↓" if key != "overlap_ratio" else "↓ (better)"
                lines.append(
                    f"  {label}: {vals[0]:.1f} → {vals[1]:.1f} → {vals[2]:.1f} {trend}"
                )

    # Regressions
    regressions = detect_regressions(records)
    if regressions:
        lines.extend(["", "### ⚠ Regressions Detected"])
        for reg in regressions:
            lines.append(
                f"  {reg['metric']}: {reg['current']} "
                f"(avg: {reg['rolling_avg']}, {reg['delta_pct']:+.1f}%)"
            )

    return "\n".join(lines)
