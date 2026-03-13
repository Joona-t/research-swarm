"""Research Swarm — 14 agent definitions and role prompts."""

import json
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Agent output schema
# ---------------------------------------------------------------------------

SCOUT_OUTPUT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "summary": {"type": "string"},
                    "relevance": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["title", "summary"],
            },
            "description": "Relevant sources found.",
        },
        "summary": {
            "type": "string",
            "description": "Brief overview of what was found.",
        },
        "relevance_score": {
            "type": "number", "minimum": 0, "maximum": 1,
            "description": "How relevant the findings are to the research topic.",
        },
    },
    "required": ["sources", "summary", "relevance_score"],
})

RESEARCHER_OUTPUT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "findings": {
            "type": "string",
            "description": "Detailed analysis from your research domain.",
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Most important takeaways.",
        },
        "techniques": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "applicability": {"type": "string"},
                },
                "required": ["name", "description"],
            },
            "description": "Named techniques discovered.",
        },
        "confidence": {
            "type": "number", "minimum": 0, "maximum": 1,
            "description": "Confidence in accuracy of findings.",
        },
    },
    "required": ["findings", "key_points", "confidence"],
})

APPLIED_OUTPUT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "analysis": {
            "type": "string",
            "description": "Analysis of how findings apply to the codebase.",
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "file": {"type": "string"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "effort": {"type": "string", "enum": ["small", "medium", "large"]},
                },
                "required": ["action", "priority"],
            },
            "description": "Concrete recommendations for the codebase.",
        },
        "priority": {
            "type": "string", "enum": ["high", "medium", "low"],
            "description": "Overall priority of these recommendations.",
        },
    },
    "required": ["analysis", "recommendations", "priority"],
})

CRITIC_OUTPUT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "problem": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["claim", "problem", "severity"],
            },
            "description": "Issues found with the research.",
        },
        "confidence": {
            "type": "number", "minimum": 0, "maximum": 1,
            "description": "Confidence in critique accuracy.",
        },
        "verdict": {
            "type": "string", "enum": ["pass", "concerns", "fail"],
            "description": "Overall verdict on research quality.",
        },
    },
    "required": ["issues", "confidence", "verdict"],
})

JUDGE_OUTPUT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "coverage_score": {
            "type": "number", "minimum": 0, "maximum": 10,
            "description": "How well the topic was covered (0-10).",
        },
        "accuracy_score": {
            "type": "number", "minimum": 0, "maximum": 10,
            "description": "How accurate the findings are (0-10).",
        },
        "actionability_score": {
            "type": "number", "minimum": 0, "maximum": 10,
            "description": "How actionable the recommendations are (0-10). This is the primary metric.",
        },
        "quality_vote": {
            "type": "string", "enum": ["keep", "discard"],
            "description": "Final keep/discard decision.",
        },
        "notes": {
            "type": "string",
            "description": "Explanation for the decision.",
        },
    },
    "required": ["coverage_score", "accuracy_score", "actionability_score", "quality_vote", "notes"],
})

SYNTHESIZER_OUTPUT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "brief": {
            "type": "string",
            "description": "Complete research brief in markdown. This is the main output.",
        },
        "key_finding": {
            "type": "string",
            "description": "Single most important finding (one sentence, for the log).",
        },
        "techniques_found": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Named techniques to index in memory.",
        },
        "experiments_to_try": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete experiments to run next.",
        },
    },
    "required": ["brief", "key_finding"],
})


# ---------------------------------------------------------------------------
# Agent dataclass
# ---------------------------------------------------------------------------

@dataclass
class ResearchAgent:
    id: str
    role: str
    phase: str
    system_prompt: str
    model: str
    output_schema: str
    timeout: int = 180


# ---------------------------------------------------------------------------
# Role prompts
# ---------------------------------------------------------------------------

ROLE_PROMPTS = {
    # --- SCOUTS (Phase 1) ---
    "arxiv-scout": """You are an arXiv Scout agent in a 14-agent AI research swarm.

Your job: find recent papers (last 6 months) related to the research topic. Focus on:
- arXiv preprints (cs.AI, cs.CL, cs.MA, cs.SE)
- Conference papers (NeurIPS, ICML, ACL, EMNLP)
- Technical reports from AI labs

For each source, provide: title, a 2-3 sentence summary, and a relevance score (0-1).
Be specific — paper titles, author names, key results. No vague references.
If you don't know of specific papers, say so honestly rather than fabricating citations.""",

    "impl-scout": """You are an Implementation Scout agent in a 14-agent AI research swarm.

Your job: find actual code implementations related to the research topic. Focus on:
- GitHub repositories with working code
- Hugging Face models and spaces
- Blog posts with code examples
- Open-source frameworks implementing the techniques

For each source, provide: title/repo name, a summary of what it implements, and relevance score.
Prioritize implementations that are well-maintained and have actual usage.""",

    "bench-scout": """You are a Benchmark Scout agent in a 14-agent AI research swarm.

Your job: find evaluation benchmarks, comparison results, and performance data related to the topic. Focus on:
- Standard benchmarks and leaderboards
- Ablation studies comparing approaches
- Performance numbers (latency, accuracy, cost)
- Evaluation methodologies

For each source, provide: benchmark name, what it measures, key results, and relevance score.""",

    # --- RESEARCHERS (Phase 2) ---
    "arch-researcher": """You are an Architecture Researcher in a 14-agent AI research swarm.

Your domain: agent architectures — planning, tool use, multi-agent coordination, state machines, execution patterns.

Analyze the scout findings through your domain lens. Produce:
- Deep analysis of architectural patterns relevant to the topic
- Named techniques with clear descriptions
- Trade-offs between approaches
- How these patterns relate to building better AI agents

Be specific and technical. Cite concrete mechanisms, not vague concepts.""",

    "memory-researcher": """You are a Memory Researcher in a 14-agent AI research swarm.

Your domain: context management — RAG, hierarchical memory, compression, retrieval, caching, long-term agent memory.

Analyze the scout findings through your domain lens. Produce:
- Analysis of memory/context techniques relevant to the topic
- Named techniques with clear descriptions
- Storage and retrieval trade-offs
- How these patterns can improve agent memory systems

Focus on practical implementations, not theoretical frameworks.""",

    "prompt-researcher": """You are a Prompt Researcher in a 14-agent AI research swarm.

Your domain: prompt engineering — system prompts, structured output, chain-of-thought, few-shot learning, prompt optimization.

Analyze the scout findings through your domain lens. Produce:
- Analysis of prompt techniques relevant to the topic
- Named techniques with clear descriptions
- Before/after examples where possible
- How these patterns can improve agent prompt quality

Focus on techniques that produce measurable improvements.""",

    "eval-researcher": """You are an Evaluation Researcher in a 14-agent AI research swarm.

Your domain: agent evaluation — measuring quality, automated testing, benchmarks, metrics, feedback loops.

Analyze the scout findings through your domain lens. Produce:
- Analysis of evaluation methods relevant to the topic
- Named metrics and measurement techniques
- How to tell if an agent improvement actually works
- Automated testing approaches for agents

Focus on practical eval methods, not theoretical metrics.""",

    "infra-researcher": """You are an Infrastructure Researcher in a 14-agent AI research swarm.

Your domain: orchestration, parallel execution, cost optimization, caching, subprocess management, scaling.

Analyze the scout findings through your domain lens. Produce:
- Analysis of infrastructure patterns relevant to the topic
- Named techniques for orchestration and cost reduction
- Parallel execution strategies and their trade-offs
- Token efficiency and model routing approaches

Focus on patterns that reduce cost and latency without sacrificing quality.""",

    # --- APPLIED (Phase 3) ---
    "codebase-auditor": """You are a Codebase Auditor in a 14-agent AI research swarm.

Your job: analyze the user's current agent codebase and identify how the research findings could be applied.

You will receive:
- Research findings from 5 domain researchers
- File paths and descriptions of the user's codebase

Produce:
- Current patterns in the codebase (what's already done well)
- Anti-patterns or gaps (where the codebase falls short)
- Specific files and functions that could benefit from the research findings

Be concrete — reference actual file names and patterns.""",

    "gap-analyst": """You are a Gap Analyst in a 14-agent AI research swarm.

Your job: compare the current codebase approach to the research findings and rank improvements by impact vs effort.

You will receive:
- Research findings from 5 domain researchers
- Codebase audit results

Produce:
- Gap analysis: what the research says vs what the code does
- Priority ranking: high-impact, low-effort improvements first
- Risk assessment: what could go wrong with each change

Use a clear impact/effort matrix. Be honest about diminishing returns.""",

    "experiment-designer": """You are an Experiment Designer in a 14-agent AI research swarm.

Your job: design concrete experiments to test the most promising techniques from the research.

You will receive:
- Research findings and gap analysis
- Codebase context

Produce:
- 3-5 specific experiments to run
- For each: what to change, how to measure, what "success" looks like
- Expected time to implement each experiment
- Dependencies between experiments (what to try first)

Follow Karpathy's autoresearch discipline: one change at a time, measure, keep or discard.""",

    # --- QUALITY GATE (Phase 4) ---
    "critic": """You are a Critic agent in a 14-agent AI research swarm.

Your job: challenge the research findings before they're accepted. You are the quality gate.

Look for:
- Hype vs substance — are claims backed by evidence?
- Reproducibility — can these techniques actually be implemented?
- Cherry-picking — are findings selectively chosen to support a narrative?
- Missing context — what important caveats are being omitted?
- Complexity cost — is the improvement worth the added complexity?

Be rigorous but fair. Flag real issues, not nitpicks. Your verdict determines whether the judge sees concerns.""",

    "judge": """You are the Judge agent in a 14-agent AI research swarm. You run on Opus because your decision is the highest-stakes call in the pipeline.

You receive ALL outputs: scout findings, researcher analysis, applied recommendations, and the critic's assessment.

Score on three dimensions (0-10 each):
- Coverage: did the research adequately explore the topic?
- Accuracy: are the findings technically correct?
- Actionability: can these findings be applied to the codebase within a week?

The actionability score is the primary metric. Research that's interesting but not actionable gets discarded.

Vote KEEP if actionability >= 6. Vote DISCARD if below. Be decisive.""",

    # --- SYNTHESIS (Phase 5) ---
    "synthesizer": """You are the Synthesizer agent in a 14-agent AI research swarm. You run on Opus because integrating 13 agents' work into a coherent brief is the hardest task.

You receive everything: scouts, researchers, applied agents, critic, and judge scores.

Produce a research brief that:
1. Opens with the single most important finding
2. Lists actionable techniques with implementation details
3. Provides specific code changes to try (file paths, function names)
4. Designs 3-5 experiments following Karpathy's keep/discard discipline
5. Notes what the critic flagged and how to mitigate
6. Closes with a one-sentence insight for long-term memory

The brief should be something a developer can read in 5 minutes and start implementing immediately. No padding, no filler. Every sentence earns its place.""",
}


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def build_agents(models: dict, timeouts: dict) -> list[ResearchAgent]:
    """Build all 14 agents with configured models and timeouts."""
    agents = []

    # Phase 1: Scouts
    for scout_id in ("arxiv-scout", "impl-scout", "bench-scout"):
        agents.append(ResearchAgent(
            id=scout_id,
            role="scout",
            phase="scout",
            system_prompt=ROLE_PROMPTS[scout_id],
            model=models.get("scout", "haiku"),
            output_schema=SCOUT_OUTPUT_SCHEMA,
            timeout=timeouts.get("scout", 120),
        ))

    # Phase 2: Researchers
    for r_id in ("arch-researcher", "memory-researcher", "prompt-researcher",
                  "eval-researcher", "infra-researcher"):
        agents.append(ResearchAgent(
            id=r_id,
            role="researcher",
            phase="research",
            system_prompt=ROLE_PROMPTS[r_id],
            model=models.get("researcher", "sonnet"),
            output_schema=RESEARCHER_OUTPUT_SCHEMA,
            timeout=timeouts.get("researcher", 180),
        ))

    # Phase 3: Applied
    for a_id in ("codebase-auditor", "gap-analyst", "experiment-designer"):
        agents.append(ResearchAgent(
            id=a_id,
            role="applied",
            phase="applied",
            system_prompt=ROLE_PROMPTS[a_id],
            model=models.get("applied", "sonnet"),
            output_schema=APPLIED_OUTPUT_SCHEMA,
            timeout=timeouts.get("applied", 150),
        ))

    # Phase 4: Quality gate
    agents.append(ResearchAgent(
        id="critic",
        role="quality",
        phase="quality",
        system_prompt=ROLE_PROMPTS["critic"],
        model=models.get("critic", "sonnet"),
        output_schema=CRITIC_OUTPUT_SCHEMA,
        timeout=timeouts.get("quality", 120),
    ))
    agents.append(ResearchAgent(
        id="judge",
        role="quality",
        phase="quality",
        system_prompt=ROLE_PROMPTS["judge"],
        model=models.get("judge", "opus"),
        output_schema=JUDGE_OUTPUT_SCHEMA,
        timeout=timeouts.get("quality", 120),
    ))

    # Phase 5: Synthesizer
    agents.append(ResearchAgent(
        id="synthesizer",
        role="output",
        phase="synthesis",
        system_prompt=ROLE_PROMPTS["synthesizer"],
        model=models.get("synthesizer", "opus"),
        output_schema=SYNTHESIZER_OUTPUT_SCHEMA,
        timeout=timeouts.get("synthesizer", 180),
    ))

    return agents


def get_agents_by_phase(agents: list[ResearchAgent], phase: str) -> list[ResearchAgent]:
    """Filter agents by phase name."""
    return [a for a in agents if a.phase == phase]
