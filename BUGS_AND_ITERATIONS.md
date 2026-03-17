# Bugs & Iterations

## : |2026-03-14|||Revert dedup threshold to 0.39 — 0.50 caused overlap=1.0 on 1/3 topics

**Problem:** |2026-03-14|||Revert dedup threshold to 0.39 — 0.50 caused overlap=1.0 on 1/3 topics
**Details:** Exp 3 failed: "recursive code editing" topic had all techniques merged.
Keeping configurable threshold in config.toml for future sweep.
Regenerate dashboard with runs 35-37 (cost tracking now visible).
**Files:** config.toml,dashboard.html
**Commit:** 27f0358

## : |2026-03-13|||Apply role differentiation research: OUT_OF_SCOPE, capability registry, dedup

**Problem:** |2026-03-13|||Apply role differentiation research: OUT_OF_SCOPE, capability registry, dedup
**Details:** - OUT_OF_SCOPE sections: each of the 5 researcher prompts now explicitly
  lists what it must NOT analyze, with delegation targets. Prevents the
  domain bleeding that caused 38 overlapping techniques in run #4.
- Capability registry: CAPABILITY_REGISTRY dict maps each researcher to
**Files:** agents.py,orchestrator.py,research-log.tsv
**Commit:** 94c6334

## : |2026-03-14|||Fix confidence pipeline: remove inverted override, wire critic verdict into gate

**Problem:** |2026-03-14|||Fix confidence pipeline: remove inverted override, wire critic verdict into gate
**Details:** The quality gate had inverted logic — high actionability silently overrode
judge "discard" votes to "keep." Removed this (judge discard is now final).
Added critic-fail gate: if critic says "fail", even a judge "keep" gets
overridden to "discard." Added effective_threshold and critic_verdict to
metrics for observability.
**Files:** agents.py,consensus.py,metrics.jsonl,metrics.py,orchestrator.py
**Commit:** e7c2cb6

<!-- Format:
## YYYY-MM-DD: Short Title

**Problem:** What went wrong or needed changing
**Root cause:** Why it happened
**Fix:** What was done to resolve it
-->
