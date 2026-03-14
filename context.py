"""Research Swarm — Priority-aware context compression.

Replaces hard character truncation with intelligent compression:
  1. Split context into sections (by ## or ### headers)
  2. Score each section by importance signals (confidence, evidence, keywords)
  3. Keep high-priority sections in full
  4. Progressively summarize/truncate low-priority sections until budget met

No extra LLM calls — all scoring is heuristic, O(n) in section count.
"""

import re
from dataclasses import dataclass


@dataclass
class ContextSection:
    """A section of context with priority metadata."""
    header: str
    content: str
    priority: float = 0.5  # 0.0 = lowest, 1.0 = highest
    compressible: bool = True  # False for critical sections like conflicts


# Priority signals and their weights
PRIORITY_KEYWORDS = {
    # High-priority markers
    "high": 0.15,
    "HIGH": 0.15,
    "critical": 0.15,
    "PROVEN": 0.2,
    "peer_reviewed": 0.15,
    "preprint": 0.1,
    "confidence=0.9": 0.15,
    "confidence=0.8": 0.1,
    "confidence=1.0": 0.15,
    # Low-priority markers
    "low": -0.1,
    "LOW": -0.1,
    "FAILED": -0.15,
    "unverified": -0.05,
    "UNVERIFIED": -0.05,
    "nitpick": -0.1,
    "confidence=0.3": -0.1,
    "confidence=0.4": -0.05,
}

# Section types that should never be compressed
PROTECTED_HEADERS = frozenset({
    "conflicts",
    "disagreements",
    "grounding summary",
    "grounding report",
    "quality gate",
    "critic assessment",
})


def split_into_sections(context: str) -> list[ContextSection]:
    """Split context into sections by markdown headers.

    Handles ## and ### headers. Content before the first header
    becomes a section with header "preamble".
    """
    sections = []
    current_header = "preamble"
    current_lines = []

    for line in context.split("\n"):
        header_match = re.match(r"^(#{2,3})\s+(.+)$", line)
        if header_match:
            # Save previous section
            if current_lines:
                sections.append(ContextSection(
                    header=current_header,
                    content="\n".join(current_lines),
                ))
            current_header = header_match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    if current_lines:
        sections.append(ContextSection(
            header=current_header,
            content="\n".join(current_lines),
        ))

    return sections


def score_section(section: ContextSection) -> float:
    """Score a section's importance using keyword signals.

    Returns float in [0.0, 1.0]. Higher = more important.
    """
    base = 0.5
    text = section.content + " " + section.header

    # Check for protected headers
    header_lower = section.header.lower()
    if any(p in header_lower for p in PROTECTED_HEADERS):
        section.compressible = False
        return 1.0

    # Keyword-based scoring
    for keyword, weight in PRIORITY_KEYWORDS.items():
        count = text.count(keyword)
        if count > 0:
            base += weight * min(count, 3)  # Cap at 3 occurrences

    # Confidence scores: extract and average them
    conf_matches = re.findall(r"confidence[=:]?\s*(\d+\.?\d*)", text)
    if conf_matches:
        confs = [float(c) for c in conf_matches if 0 <= float(c) <= 1]
        if confs:
            avg_conf = sum(confs) / len(confs)
            base += (avg_conf - 0.5) * 0.3  # Boost high conf, penalize low

    # Evidence type boost: count grounded vs unverified
    grounded = text.count("peer_reviewed") + text.count("preprint") + text.count("[repo]")
    unverified = text.count("[UNVERIFIED]") + text.count("unverified")
    if grounded + unverified > 0:
        grounding_ratio = grounded / (grounded + unverified)
        base += (grounding_ratio - 0.5) * 0.2

    # Length penalty: very long sections get slight penalty (likely verbose)
    if len(section.content) > 2000:
        base -= 0.05

    return max(0.0, min(1.0, base))


def compress_section(section: ContextSection, target_chars: int) -> str:
    """Compress a section to fit within target_chars.

    Strategy:
      1. If already fits, return as-is
      2. Keep header and first paragraph (usually the summary)
      3. For bullet lists: keep first N items, add "[N more items compressed]"
      4. Hard truncate only as last resort
    """
    full = f"### {section.header}\n{section.content}"
    if len(full) <= target_chars:
        return full

    lines = section.content.split("\n")

    # Strategy: keep header + first substantive paragraph + bullet summary
    kept_lines = []
    bullet_lines = []
    non_bullet_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            bullet_lines.append(line)
        elif stripped:
            non_bullet_lines.append(line)

    # Keep first 2 non-bullet lines (usually summary/overview)
    kept_lines.extend(non_bullet_lines[:2])

    # Keep top bullets up to budget
    remaining = target_chars - len(f"### {section.header}\n") - sum(len(l) + 1 for l in kept_lines) - 50
    bullets_kept = 0
    for bl in bullet_lines:
        if remaining - len(bl) - 1 > 0:
            kept_lines.append(bl)
            remaining -= len(bl) + 1
            bullets_kept += 1
        else:
            break

    compressed_count = len(bullet_lines) - bullets_kept
    if compressed_count > 0:
        kept_lines.append(f"[{compressed_count} more items compressed]")

    result = f"### {section.header}\n" + "\n".join(kept_lines)

    # Final safety truncation
    if len(result) > target_chars:
        result = result[:target_chars - 30] + "\n[section truncated for budget]"

    return result


def prioritized_context(context: str, budget: int) -> str:
    """Build context string within budget using priority-aware compression.

    Algorithm:
      1. Split into sections, score each
      2. Sort by priority (highest first)
      3. Add high-priority sections in full until budget is 70% used
      4. Compress remaining sections to fit in the remaining 30%
      5. If still over budget, drop lowest-priority compressible sections

    Args:
        context: full context string (may exceed budget)
        budget: max characters for the context

    Returns:
        context string within budget, with low-priority sections compressed
    """
    if len(context) <= budget:
        return context

    sections = split_into_sections(context)
    if not sections:
        return context[:budget]

    # Score and sort
    for s in sections:
        s.priority = score_section(s)

    # Separate protected from compressible
    protected = [s for s in sections if not s.compressible]
    compressible = [s for s in sections if s.compressible]
    compressible.sort(key=lambda s: s.priority, reverse=True)

    # Phase 1: add all protected sections
    result_parts = []
    used = 0
    for s in protected:
        part = f"### {s.header}\n{s.content}"
        result_parts.append((s.priority, s.header, part))
        used += len(part) + 2  # +2 for newlines

    # Phase 2: add compressible sections, highest priority first
    full_budget = budget * 0.70  # Reserve 30% for compressed sections

    for s in compressible:
        part = f"### {s.header}\n{s.content}"
        if used + len(part) + 2 <= full_budget:
            result_parts.append((s.priority, s.header, part))
            used += len(part) + 2
        else:
            # Phase 3: compress this section to fit
            remaining = budget - used - 50  # Leave margin
            if remaining > 200:  # Minimum useful compressed section
                compressed = compress_section(s, max(200, remaining // max(1, len(compressible) - len(result_parts))))
                result_parts.append((s.priority, s.header, compressed))
                used += len(compressed) + 2
            # else: drop this section entirely

    # Rebuild in original section order (approximate: by header appearance in original)
    original_order = {s.header: i for i, s in enumerate(sections)}
    result_parts.sort(key=lambda x: original_order.get(x[1], 999))

    result = "\n\n".join(part for _, _, part in result_parts)

    # Append compression metadata so downstream agents know what happened
    sections_kept = len(result_parts)
    sections_total = len(sections)
    sections_dropped = sections_total - sections_kept
    if sections_dropped > 0 or any("compressed" in p.lower() for _, _, p in result_parts):
        result += (
            f"\n\n<!-- context_compression: kept={sections_kept}/{sections_total} "
            f"sections, dropped={sections_dropped}, budget={budget} chars -->"
        )

    # Final safety check
    if len(result) > budget:
        result = result[:budget - 40] + "\n\n[Context compressed to fit budget]"

    return result
