"""Agent-count ablation experiment.

Tests 4 configurations on the same topics to find the optimal agent count.
Measures quality, actionability, factuality, overlap, wall clock, and cost.

Usage:
    python3 ablation.py
    python3 ablation.py --configs full,lean    # run specific configs only
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from agents import build_agents, ResearchAgent
from orchestrator import run_swarm, load_config

# --- Ablation configurations ---
# Each config specifies which agent IDs to keep.
# Quality gate (critic + judge) and synthesizer are always included.

CONFIGS = {
    "full": {
        "scouts": ["arxiv-scout", "impl-scout", "bench-scout"],
        "researchers": ["arch-researcher", "memory-researcher", "prompt-researcher",
                        "eval-researcher", "infra-researcher"],
        "applied": ["codebase-auditor", "gap-analyst", "experiment-designer"],
        "total": 14,
    },
    "lean": {
        "scouts": ["arxiv-scout", "impl-scout"],
        "researchers": ["arch-researcher", "memory-researcher", "prompt-researcher"],
        "applied": ["codebase-auditor", "experiment-designer"],
        "total": 10,
    },
    "minimal": {
        "scouts": ["arxiv-scout", "impl-scout"],
        "researchers": ["arch-researcher", "prompt-researcher"],
        "applied": ["experiment-designer"],
        "total": 8,
    },
    "skeleton": {
        "scouts": ["arxiv-scout"],
        "researchers": ["arch-researcher", "prompt-researcher"],
        "applied": ["experiment-designer"],
        "total": 6,
    },
}

# Core agents always included (never cut)
CORE_AGENTS = {"critic", "judge", "synthesizer"}

# Test topics — diverse enough to stress different agent specializations
TOPICS = [
    "Techniques for reducing hallucination in retrieval-augmented generation systems 2025-2026",
    "Efficient fine-tuning methods for large language models on consumer hardware 2025",
    "Code generation evaluation benchmarks and automated testing for LLM outputs 2025-2026",
]


def filter_agents(all_agents: list[ResearchAgent], config: dict) -> list[ResearchAgent]:
    """Filter agents to match an ablation configuration."""
    keep_ids = set(config["scouts"] + config["researchers"] + config["applied"])
    keep_ids |= CORE_AGENTS
    return [a for a in all_agents if a.id in keep_ids]


def load_latest_metrics(n: int = 1) -> list[dict]:
    """Load the last N entries from metrics.jsonl."""
    metrics_path = Path(__file__).parent / "metrics.jsonl"
    if not metrics_path.exists():
        return []
    lines = metrics_path.read_text().strip().split("\n")
    return [json.loads(line) for line in lines[-n:]]


async def run_ablation(configs_filter: list[str] | None = None):
    """Run the full ablation experiment."""
    config = load_config()
    models = config.get("models", {})
    timeouts = config.get("timeouts", {})
    all_agents = build_agents(models, timeouts)

    configs_to_run = configs_filter or list(CONFIGS.keys())
    results = []

    print("=" * 70)
    print("AGENT-COUNT ABLATION EXPERIMENT")
    print(f"Configs: {configs_to_run}")
    print(f"Topics: {len(TOPICS)}")
    print(f"Total runs: {len(configs_to_run) * len(TOPICS)}")
    print("=" * 70)

    for config_name in configs_to_run:
        cfg = CONFIGS[config_name]
        agents = filter_agents(all_agents, cfg)
        agent_count = len(agents)

        print(f"\n{'─' * 60}")
        print(f"CONFIG: {config_name} ({agent_count} agents)")
        print(f"  Scouts: {cfg['scouts']}")
        print(f"  Researchers: {cfg['researchers']}")
        print(f"  Applied: {cfg['applied']}")
        print(f"{'─' * 60}")

        for i, topic in enumerate(TOPICS):
            print(f"\n  [{config_name}] Topic {i+1}/{len(TOPICS)}: {topic[:60]}...")
            start = time.monotonic()

            output_path = await run_swarm(
                topic=topic,
                agents=agents,
                verbose=False,
            )

            elapsed = time.monotonic() - start

            # Grab the metrics from the last run
            latest = load_latest_metrics(1)
            if latest:
                m = latest[0]
                results.append({
                    "config": config_name,
                    "agents": agent_count,
                    "topic": topic[:50],
                    "quality": m.get("avg_quality", 0),
                    "actionability": m.get("actionability", 0),
                    "factuality": m.get("factuality", 0),
                    "overlap": m.get("overlap_ratio", 0),
                    "applied_rate": m.get("applied_success_rate", 0),
                    "wall_s": round(elapsed, 1),
                    "status": m.get("status", "?"),
                })
            else:
                results.append({
                    "config": config_name,
                    "agents": agent_count,
                    "topic": topic[:50],
                    "quality": 0, "actionability": 0, "factuality": 0,
                    "overlap": 0, "applied_rate": 0, "wall_s": round(elapsed, 1),
                    "status": "no_metrics",
                })

    # --- Results summary ---
    print("\n" + "=" * 70)
    print("ABLATION RESULTS")
    print("=" * 70)

    # Per-run table
    print(f"\n{'Config':<10} {'Agents':>6} {'Quality':>7} {'Action':>6} {'Fact':>4} "
          f"{'Overlap':>7} {'Applied':>7} {'Wall(s)':>7} {'Status':<8} Topic")
    print("─" * 100)
    for r in results:
        print(f"{r['config']:<10} {r['agents']:>6} {r['quality']:>7.1f} "
              f"{r['actionability']:>6.1f} {r['factuality']:>4.1f} "
              f"{r['overlap']:>6.0%} {r['applied_rate']:>7.0%} "
              f"{r['wall_s']:>7.1f} {r['status']:<8} {r['topic'][:40]}")

    # Per-config averages
    print(f"\n{'─' * 70}")
    print(f"{'Config':<10} {'Agents':>6} {'Avg Quality':>11} {'Avg Action':>10} "
          f"{'Avg Fact':>8} {'Avg Wall':>8}")
    print("─" * 70)

    for config_name in configs_to_run:
        cfg_results = [r for r in results if r["config"] == config_name]
        if not cfg_results:
            continue
        n = len(cfg_results)
        avg_q = sum(r["quality"] for r in cfg_results) / n
        avg_a = sum(r["actionability"] for r in cfg_results) / n
        avg_f = sum(r["factuality"] for r in cfg_results) / n
        avg_w = sum(r["wall_s"] for r in cfg_results) / n
        agents = cfg_results[0]["agents"]
        print(f"{config_name:<10} {agents:>6} {avg_q:>11.1f} {avg_a:>10.1f} "
              f"{avg_f:>8.1f} {avg_w:>8.1f}")

    # Save raw results
    results_path = Path(__file__).parent / "output" / "ablation_results.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nRaw results saved to: {results_path}")

    # Verdict
    print(f"\n{'=' * 70}")
    print("VERDICT")
    print("=" * 70)
    full_results = [r for r in results if r["config"] == "full"]
    if full_results:
        full_avg = sum(r["quality"] for r in full_results) / len(full_results)
        for config_name in configs_to_run:
            if config_name == "full":
                continue
            cfg_results = [r for r in results if r["config"] == config_name]
            if not cfg_results:
                continue
            cfg_avg = sum(r["quality"] for r in cfg_results) / len(cfg_results)
            delta = cfg_avg - full_avg
            agents = cfg_results[0]["agents"]
            if abs(delta) <= 0.5:
                print(f"  {config_name} ({agents} agents): KEEP — quality within 0.5 of full (delta: {delta:+.1f})")
            elif delta < -1.0:
                print(f"  {config_name} ({agents} agents): DISCARD — quality dropped >1.0 (delta: {delta:+.1f})")
            else:
                print(f"  {config_name} ({agents} agents): MARGINAL — quality delta {delta:+.1f}")


if __name__ == "__main__":
    configs_filter = None
    if "--configs" in sys.argv:
        idx = sys.argv.index("--configs")
        if idx + 1 < len(sys.argv):
            configs_filter = sys.argv[idx + 1].split(",")

    asyncio.run(run_ablation(configs_filter))
