"""Research Swarm Dashboard — generates an HTML metrics dashboard.

Reads metrics.jsonl and produces a single-page dashboard with Chart.js graphs
tracking quality, actionability, factuality, overlap, wall clock, and agent count.

Usage:
    python3 dashboard.py           # generates dashboard.html and opens it
    python3 dashboard.py --no-open # generates without opening
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

METRICS_PATH = Path(__file__).parent / "metrics.jsonl"
OUTPUT_PATH = Path(__file__).parent / "dashboard.html"


def load_metrics() -> list[dict]:
    """Load all metrics entries."""
    if not METRICS_PATH.exists():
        return []
    entries = []
    for line in METRICS_PATH.read_text().strip().split("\n"):
        if line.strip():
            entries.append(json.loads(line))
    return entries


def generate_dashboard(metrics: list[dict]) -> str:
    """Generate HTML dashboard from metrics data."""

    # Filter to runs with actual data (quality > 0)
    valid = [m for m in metrics if m.get("avg_quality", 0) > 0]

    # Extract series data
    labels = [f"Run {i+1}" for i in range(len(valid))]
    topics = [m.get("topic", "?")[:40] for m in valid]
    quality = [m.get("avg_quality", 0) for m in valid]
    actionability = [m.get("actionability", 0) for m in valid]
    factuality = [m.get("factuality", 0) for m in valid]
    accuracy = [m.get("accuracy", 0) for m in valid]
    coverage = [m.get("coverage", 0) for m in valid]
    overlap = [round(m.get("overlap_ratio", 0) * 100, 1) for m in valid]
    wall_clock = [round(m.get("wall_clock_s", m.get("total_wall_clock_s", 0)), 0) for m in valid]
    agent_count = [m.get("agent_count", m.get("total_agent_invocations", 14)) for m in valid]
    applied_rate = [round(m.get("applied_success_rate", 0) * 100, 0) for m in valid]
    timestamps = [m.get("timestamp", "") for m in valid]
    cost_usd = [round(m.get("total_cost_usd", 0), 4) for m in valid]
    input_tokens = [m.get("total_input_tokens", 0) for m in valid]
    output_tokens = [m.get("total_output_tokens", 0) for m in valid]

    # Compute running averages (window=3)
    def running_avg(data, window=3):
        result = []
        for i in range(len(data)):
            start = max(0, i - window + 1)
            result.append(round(sum(data[start:i+1]) / (i - start + 1), 2))
        return result

    quality_avg = running_avg(quality)
    action_avg = running_avg(actionability)
    fact_avg = running_avg(factuality)
    cost_avg = running_avg(cost_usd)

    # Summary stats
    n = len(valid)
    latest = valid[-1] if valid else {}
    best_quality = max(quality) if quality else 0
    best_action = max(actionability) if actionability else 0
    best_fact = max(factuality) if factuality else 0
    avg_quality = round(sum(quality) / n, 1) if n else 0
    avg_wall = round(sum(wall_clock) / n, 0) if n else 0
    total_cost = round(sum(cost_usd), 2)
    avg_cost = round(total_cost / n, 4) if n else 0

    # Build the topic table rows
    table_rows = ""
    for i, m in enumerate(valid):
        vote = m.get("status", m.get("vote", "?"))
        status_class = "status-keep" if vote == "keep" else "status-discard"
        wall = round(m.get("wall_clock_s", m.get("total_wall_clock_s", 0)))
        agents = m.get("agent_count", m.get("total_agent_invocations", 14))
        run_cost = m.get("total_cost_usd", 0)
        cost_display = f"${run_cost:.2f}" if run_cost > 0 else "—"
        table_rows += f"""
        <tr>
            <td>{i+1}</td>
            <td class="topic-cell" title="{m.get('topic', '?')}">{m.get('topic', '?')[:50]}</td>
            <td>{agents}</td>
            <td>{m.get('avg_quality', 0):.1f}</td>
            <td>{m.get('actionability', 0):.1f}</td>
            <td>{m.get('factuality', 0):.1f}</td>
            <td>{round(m.get('overlap_ratio', 0) * 100)}%</td>
            <td>{wall}s</td>
            <td>{cost_display}</td>
            <td class="{status_class}">{vote.upper()}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Swarm Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            background: #0d1117;
            color: #e6edf3;
            padding: 24px;
        }}
        h1 {{
            font-size: 28px;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #58a6ff, #bc8cff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{ color: #8b949e; margin-bottom: 24px; font-size: 14px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
        }}
        .stat-card .label {{ color: #8b949e; font-size: 12px; text-transform: uppercase; }}
        .stat-card .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
        .stat-card .trend {{ font-size: 12px; margin-top: 4px; }}
        .trend-up {{ color: #3fb950; }}
        .trend-down {{ color: #f85149; }}
        .trend-flat {{ color: #8b949e; }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(480px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .chart-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 16px;
        }}
        .chart-card h3 {{ font-size: 14px; color: #8b949e; margin-bottom: 12px; }}
        canvas {{ max-height: 280px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            text-align: left;
            padding: 8px 12px;
            border-bottom: 2px solid #30363d;
            color: #8b949e;
            font-weight: 600;
        }}
        td {{
            padding: 8px 12px;
            border-bottom: 1px solid #21262d;
        }}
        tr:hover {{ background: #161b22; }}
        .topic-cell {{ max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        .status-keep {{ color: #3fb950; font-weight: 600; }}
        .status-discard {{ color: #f85149; font-weight: 600; }}
        .section-title {{
            font-size: 18px;
            margin: 24px 0 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #30363d;
        }}
        .ablation-note {{
            background: #161b22;
            border-left: 3px solid #58a6ff;
            padding: 12px 16px;
            margin-bottom: 24px;
            font-size: 13px;
            line-height: 1.6;
            border-radius: 0 8px 8px 0;
        }}
        .ablation-note strong {{ color: #58a6ff; }}
    </style>
</head>
<body>
    <h1>Research Swarm Dashboard</h1>
    <p class="subtitle">
        {n} successful runs | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        | Latest: {latest.get('agent_count', '?')} agents
    </p>

    <div class="ablation-note">
        <strong>Ablation Finding (Run 20-31):</strong> Agent-count ablation across 4 configs (14/10/8/7 agents)
        and 3 topics showed <strong>8 agents match 14-agent quality</strong> (6.1 vs 5.9 avg)
        with higher actionability (5.3 vs 4.3). Swarm restructured from 14 to 8 agents.
        Dropped: bench-scout, memory-researcher, eval-researcher, infra-researcher, codebase-auditor, gap-analyst.
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="label">Avg Quality</div>
            <div class="value">{avg_quality}</div>
            <div class="trend {'trend-up' if len(quality) > 1 and quality[-1] >= quality[-2] else 'trend-down' if len(quality) > 1 else 'trend-flat'}">
                Latest: {quality[-1] if quality else 0:.1f}
            </div>
        </div>
        <div class="stat-card">
            <div class="label">Best Quality</div>
            <div class="value">{best_quality:.1f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Best Actionability</div>
            <div class="value">{best_action:.1f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Best Factuality</div>
            <div class="value">{best_fact:.1f}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Runs</div>
            <div class="value">{n}</div>
        </div>
        <div class="stat-card">
            <div class="label">Avg Wall Clock</div>
            <div class="value">{avg_wall:.0f}s</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Cost</div>
            <div class="value">${total_cost:.2f}</div>
            <div class="trend trend-flat">Avg: ${avg_cost:.4f}/run</div>
        </div>
    </div>

    <div class="charts-grid">
        <div class="chart-card">
            <h3>Quality Scores Over Time</h3>
            <canvas id="qualityChart"></canvas>
        </div>
        <div class="chart-card">
            <h3>Factuality & Actionability</h3>
            <canvas id="factChart"></canvas>
        </div>
        <div class="chart-card">
            <h3>Overlap Ratio (%)</h3>
            <canvas id="overlapChart"></canvas>
        </div>
        <div class="chart-card">
            <h3>Wall Clock (seconds) & Agent Count</h3>
            <canvas id="perfChart"></canvas>
        </div>
        <div class="chart-card">
            <h3>Cost per Run (USD)</h3>
            <canvas id="costChart"></canvas>
        </div>
    </div>

    <h2 class="section-title">Run History</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>Topic</th>
                <th>Agents</th>
                <th>Quality</th>
                <th>Action.</th>
                <th>Fact.</th>
                <th>Overlap</th>
                <th>Wall</th>
                <th>Cost</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>

    <script>
        const labels = {json.dumps(labels)};
        const topics = {json.dumps(topics)};

        const chartDefaults = {{
            responsive: true,
            maintainAspectRatio: true,
            plugins: {{
                legend: {{ labels: {{ color: '#8b949e', font: {{ size: 11 }} }} }},
                tooltip: {{
                    callbacks: {{
                        title: (items) => topics[items[0].dataIndex] || labels[items[0].dataIndex]
                    }}
                }}
            }},
            scales: {{
                x: {{ ticks: {{ color: '#484f58', font: {{ size: 10 }} }}, grid: {{ color: '#21262d' }} }},
                y: {{ ticks: {{ color: '#484f58' }}, grid: {{ color: '#21262d' }} }}
            }}
        }};

        // Quality chart
        new Chart(document.getElementById('qualityChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'Avg Quality',
                        data: {json.dumps(quality)},
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88,166,255,0.1)',
                        fill: true,
                        tension: 0.3,
                    }},
                    {{
                        label: '3-Run Average',
                        data: {json.dumps(quality_avg)},
                        borderColor: '#bc8cff',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        tension: 0.3,
                    }},
                    {{
                        label: 'Coverage',
                        data: {json.dumps(coverage)},
                        borderColor: '#3fb950',
                        borderWidth: 1,
                        pointRadius: 2,
                        tension: 0.3,
                    }},
                    {{
                        label: 'Accuracy',
                        data: {json.dumps(accuracy)},
                        borderColor: '#d29922',
                        borderWidth: 1,
                        pointRadius: 2,
                        tension: 0.3,
                    }}
                ]
            }},
            options: {{ ...chartDefaults, scales: {{ ...chartDefaults.scales, y: {{ ...chartDefaults.scales.y, min: 0, max: 10 }} }} }}
        }});

        // Factuality & Actionability
        new Chart(document.getElementById('factChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'Actionability',
                        data: {json.dumps(actionability)},
                        borderColor: '#3fb950',
                        backgroundColor: 'rgba(63,185,80,0.1)',
                        fill: true,
                        tension: 0.3,
                    }},
                    {{
                        label: 'Factuality',
                        data: {json.dumps(factuality)},
                        borderColor: '#f85149',
                        backgroundColor: 'rgba(248,81,73,0.1)',
                        fill: true,
                        tension: 0.3,
                    }},
                    {{
                        label: 'Action. 3-Run Avg',
                        data: {json.dumps(action_avg)},
                        borderColor: '#3fb950',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        tension: 0.3,
                    }},
                    {{
                        label: 'Fact. 3-Run Avg',
                        data: {json.dumps(fact_avg)},
                        borderColor: '#f85149',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        tension: 0.3,
                    }}
                ]
            }},
            options: {{ ...chartDefaults, scales: {{ ...chartDefaults.scales, y: {{ ...chartDefaults.scales.y, min: 0, max: 10 }} }} }}
        }});

        // Overlap chart
        new Chart(document.getElementById('overlapChart'), {{
            type: 'bar',
            data: {{
                labels: labels,
                datasets: [{{
                    label: 'Overlap %',
                    data: {json.dumps(overlap)},
                    backgroundColor: (ctx) => {{
                        const v = ctx.raw;
                        if (v > 60) return 'rgba(248,81,73,0.6)';
                        if (v > 40) return 'rgba(210,153,34,0.6)';
                        return 'rgba(63,185,80,0.6)';
                    }},
                    borderRadius: 4,
                }}]
            }},
            options: {{ ...chartDefaults, scales: {{ ...chartDefaults.scales, y: {{ ...chartDefaults.scales.y, min: 0, max: 100 }} }} }}
        }});

        // Performance chart (wall clock + agent count)
        new Chart(document.getElementById('perfChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'Wall Clock (s)',
                        data: {json.dumps(wall_clock)},
                        borderColor: '#d29922',
                        backgroundColor: 'rgba(210,153,34,0.1)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y',
                    }},
                    {{
                        label: 'Agent Count',
                        data: {json.dumps(agent_count)},
                        borderColor: '#bc8cff',
                        borderWidth: 2,
                        pointRadius: 4,
                        tension: 0,
                        yAxisID: 'y1',
                    }},
                    {{
                        label: 'Applied Success %',
                        data: {json.dumps(applied_rate)},
                        borderColor: '#58a6ff',
                        borderWidth: 1,
                        pointRadius: 2,
                        tension: 0.3,
                        yAxisID: 'y1',
                    }}
                ]
            }},
            options: {{
                ...chartDefaults,
                scales: {{
                    x: chartDefaults.scales.x,
                    y: {{ ...chartDefaults.scales.y, position: 'left', title: {{ display: true, text: 'Seconds', color: '#8b949e' }} }},
                    y1: {{ ...chartDefaults.scales.y, position: 'right', min: 0, max: 20, title: {{ display: true, text: 'Count / %', color: '#8b949e' }}, grid: {{ drawOnChartArea: false }} }}
                }}
            }}
        }});

        // Cost chart (USD per run)
        new Chart(document.getElementById('costChart'), {{
            type: 'bar',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'Cost (USD)',
                        data: {json.dumps(cost_usd)},
                        backgroundColor: 'rgba(63,185,80,0.5)',
                        borderColor: '#3fb950',
                        borderWidth: 1,
                        borderRadius: 4,
                        yAxisID: 'y',
                    }},
                    {{
                        label: '3-Run Avg',
                        data: {json.dumps(cost_avg)},
                        type: 'line',
                        borderColor: '#bc8cff',
                        borderDash: [5, 5],
                        pointRadius: 0,
                        tension: 0.3,
                        yAxisID: 'y',
                    }}
                ]
            }},
            options: {{
                ...chartDefaults,
                scales: {{
                    ...chartDefaults.scales,
                    y: {{ ...chartDefaults.scales.y, min: 0, title: {{ display: true, text: 'USD', color: '#8b949e' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    return html


def main():
    metrics = load_metrics()
    if not metrics:
        print("No metrics found in metrics.jsonl")
        return

    html = generate_dashboard(metrics)
    OUTPUT_PATH.write_text(html)
    print(f"Dashboard generated: {OUTPUT_PATH}")
    print(f"  {len([m for m in metrics if m.get('avg_quality', 0) > 0])} successful runs plotted")

    if "--no-open" not in sys.argv:
        subprocess.run(["open", str(OUTPUT_PATH)])


if __name__ == "__main__":
    main()
