"""Research Swarm — Semantic technique deduplication.

Replaces naive 3-word prefix matching with multi-signal similarity:
  1. Keyword canonicalization (strip filler, normalize)
  2. Jaccard similarity on canonical word sets
  3. Bigram overlap for phrase-level matching
  4. Agglomerative clustering to group near-duplicates

Works offline — no embeddings, no API calls. O(n²) pairwise comparison
is fine for n < 100 techniques per run.
"""

import re
from collections import defaultdict

# Common filler words in technique names that don't carry semantic weight.
# "Memory" and "Context" are kept because they distinguish technique domains.
FILLER_WORDS = frozenset({
    "a", "an", "the", "of", "for", "in", "on", "to", "and", "or", "with",
    "based", "driven", "aware", "enhanced", "improved", "advanced", "novel",
    "framework", "system", "approach", "method", "methodology", "technique",
    "architecture", "pattern", "strategy", "mechanism", "module", "pipeline",
    "design", "implementation", "model", "using", "via", "through",
})

# Canonical synonyms: map variants to a single canonical form.
# Prevents "multi-agent" vs "multiagent" vs "multi agent" divergence.
SYNONYM_MAP = {
    "multiagent": "multi-agent",
    "multi agent": "multi-agent",
    "llm": "language-model",
    "llms": "language-model",
    "large language model": "language-model",
    "rag": "retrieval-augmented",
    "retrieval augmented generation": "retrieval-augmented",
    "retrieval-augmented generation": "retrieval-augmented",
    "cot": "chain-of-thought",
    "few shot": "few-shot",
    "fewshot": "few-shot",
    "zero shot": "zero-shot",
    "zeroshot": "zero-shot",
    "hierarchical": "tiered",
    "hierarchy": "tiered",
    "tiers": "tiered",
    "three tier": "tiered",
    "three-tier": "tiered",
    "multi tier": "tiered",
    "multi-tier": "tiered",
    "temporal": "time-decay",
    "exponential": "time-decay",
    "decay": "time-decay",
    "recency": "time-decay",
    "scoring": "ranking",
    "ranking": "ranking",
    "weighted": "ranking",
    "optimization": "optimize",
    "optimizing": "optimize",
    "compression": "compress",
    "compressing": "compress",
    "summarization": "compress",
    "routing": "route",
    "execution": "exec",
    "executing": "exec",
    "concurrent": "parallel",
    "concurrency": "parallel",
    "scaffolding": "prompting",
}


def canonicalize_name(name: str) -> set[str]:
    """Reduce a technique name to its canonical keyword set.

    Steps:
      1. Lowercase, split into words
      2. Apply synonym normalization per-word (no chain substitution)
      3. Remove filler words
      4. Return remaining content words as a set

    >>> sorted(canonicalize_name("Three-Tier Memory Hierarchy"))
    ['memory', 'tiered']
    >>> sorted(canonicalize_name("Hierarchical Memory Architecture"))
    ['memory', 'tiered']
    """
    text = name.lower().strip()

    # Apply multi-word synonyms first (before splitting)
    for pattern, canonical in sorted(SYNONYM_MAP.items(),
                                      key=lambda x: -len(x[0])):
        if " " in pattern and pattern in text:
            text = text.replace(pattern, canonical)

    # Split into words
    words = re.findall(r"[a-z][a-z0-9-]*", text)

    # Apply single-word synonyms (one pass, no chain substitution)
    canonical_words = []
    for w in words:
        canonical_words.append(SYNONYM_MAP.get(w, w))

    # Remove filler
    content_words = {w for w in canonical_words if w not in FILLER_WORDS}

    return content_words if content_words else set(canonical_words[:2])


def bigrams(words: set[str]) -> set[tuple[str, str]]:
    """Generate bigrams from a sorted word set for phrase-level matching."""
    sorted_words = sorted(words)
    if len(sorted_words) < 2:
        return set()
    return {(sorted_words[i], sorted_words[i + 1])
            for i in range(len(sorted_words) - 1)}


def technique_similarity(name_a: str, name_b: str) -> float:
    """Compute semantic similarity between two technique names.

    Combines:
      - Jaccard similarity on canonical word sets (weight: 0.6)
      - Bigram overlap ratio (weight: 0.4)

    Returns float in [0, 1]. Higher = more similar.
    """
    words_a = canonicalize_name(name_a)
    words_b = canonicalize_name(name_b)

    if not words_a or not words_b:
        return 0.0

    # Jaccard similarity
    intersection = words_a & words_b
    union = words_a | words_b
    jaccard = len(intersection) / len(union) if union else 0.0

    # Bigram overlap
    bi_a = bigrams(words_a)
    bi_b = bigrams(words_b)
    if bi_a or bi_b:
        bi_intersection = bi_a & bi_b
        bi_union = bi_a | bi_b
        bigram_sim = len(bi_intersection) / len(bi_union) if bi_union else 0.0
    else:
        # Single-word techniques: fall back to exact word match
        bigram_sim = 1.0 if words_a == words_b else 0.0

    return jaccard * 0.6 + bigram_sim * 0.4


def cluster_techniques(techniques: list[dict],
                        threshold: float = 0.40) -> list[list[dict]]:
    """Group techniques into clusters by semantic similarity.

    Uses complete-linkage agglomerative clustering: a technique joins a cluster
    only if it's similar enough to ALL existing members. This prevents
    transitive bridge-merging where A~B and B~C would incorrectly merge A,B,C
    even when A and C are unrelated.

    Args:
        techniques: list of dicts with at least "name" key
        threshold: similarity threshold for clustering (0.40 is tuned for
                  technique names — catches "Memory Hierarchy"/"Hierarchical Memory"
                  while keeping "Memory Decay" separate)

    Returns:
        list of clusters, each cluster is a list of technique dicts
    """
    n = len(techniques)
    if n == 0:
        return []

    # Compute pairwise similarity matrix
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            s = technique_similarity(techniques[i]["name"], techniques[j]["name"])
            sim[i][j] = s
            sim[j][i] = s

    # Complete-linkage: greedily assign each technique to a cluster
    # where it's similar to ALL members, or start a new cluster.
    clusters: list[list[int]] = []  # clusters of indices

    for i in range(n):
        best_cluster = -1
        best_min_sim = -1.0

        for ci, cluster in enumerate(clusters):
            # Complete-linkage: minimum similarity to any cluster member
            min_sim = min(sim[i][j] for j in cluster)
            if min_sim >= threshold and min_sim > best_min_sim:
                best_cluster = ci
                best_min_sim = min_sim

        if best_cluster >= 0:
            clusters[best_cluster].append(i)
        else:
            clusters.append([i])

    return [[techniques[i] for i in cluster] for cluster in clusters]


def _pick_best_from_cluster(cluster: list[dict]) -> dict:
    """Select the best representative technique from a duplicate cluster.

    Priority:
      1. Longest description (most informative)
      2. Has source_url or evidence_type != "unverified"
      3. First occurrence (preserve original ordering)

    Merges metadata: keeps the best description but notes all source agents.
    """
    if len(cluster) == 1:
        return cluster[0]

    # Score each candidate
    scored = []
    for i, t in enumerate(cluster):
        desc_len = len(t.get("description", ""))
        has_source = 1 if t.get("source_url") else 0
        has_evidence = 1 if t.get("evidence_type", "unverified") != "unverified" else 0
        score = desc_len + has_source * 50 + has_evidence * 30
        scored.append((score, i, t))

    scored.sort(key=lambda x: (-x[0], x[1]))
    best = dict(scored[0][2])  # Copy

    # Merge provenance: collect all source agents
    all_sources = []
    for t in cluster:
        src = t.get("from", "")
        if src and src not in all_sources:
            all_sources.append(src)
    best["from"] = ", ".join(all_sources) if all_sources else best.get("from", "")

    # Note merged count
    if len(cluster) > 1:
        best["_merged_count"] = len(cluster)
        alt_names = [t["name"] for t in cluster if t["name"] != best["name"]]
        if alt_names:
            best["_alt_names"] = alt_names[:3]

    return best


def deduplicate_techniques(techniques: list[dict],
                            threshold: float = 0.40) -> list[dict]:
    """Deduplicate a list of techniques using semantic similarity clustering.

    Main entry point. Takes raw technique list from all researchers,
    returns deduplicated list with best representative from each cluster.

    Args:
        techniques: list of dicts with at least "name" and optionally
                   "description", "from", "source_url", "evidence_type"
        threshold: similarity threshold (default 0.45, tuned empirically)

    Returns:
        deduplicated list of technique dicts, preserving original order
        of the best representative from each cluster
    """
    if len(techniques) <= 1:
        return list(techniques)

    clusters = cluster_techniques(techniques, threshold)

    deduped = []
    for cluster in clusters:
        best = _pick_best_from_cluster(cluster)
        deduped.append(best)

    return deduped
