"""Evaluation metrics (EVAL_PLAN §2): temporal IoU, matching, recall, precision@10, Spearman, Jaccard.

Pipeline position: used by evaluate.py after a run. Pure functions on plain data (intervals are
(episode, start_s, end_s) tuples) so every number can be checked by hand. No scipy: the allowed
dependency list is short (TECH_SPEC §9), and Spearman is a few lines.
"""

from __future__ import annotations

import re

Interval = tuple[int, float, float]

SEGMENT = re.compile(r"E(\d+)\s+(\d+):(\d+(?:\.\d+)?)\s*-\s*(\d+):(\d+(?:\.\d+)?)")


def parse_gold_segments(text: str) -> list[Interval]:
    """'E01 00:11.0-00:41.5; E02 00:03.0-00:20.0' -> intervals. NONE or empty -> []."""
    out: list[Interval] = []
    for m in SEGMENT.finditer(text or ""):
        ep, m1, s1, m2, s2 = m.groups()
        out.append((int(ep), int(m1) * 60 + float(s1), int(m2) * 60 + float(s2)))
    return out


def merge(intervals: list[Interval]) -> list[Interval]:
    """Union of overlapping intervals within each episode, so overlap/union never double-counts."""
    out: list[Interval] = []
    for ep, s, e in sorted(intervals):
        if out and out[-1][0] == ep and s <= out[-1][2]:
            out[-1] = (ep, out[-1][1], max(out[-1][2], e))
        else:
            out.append((ep, s, e))
    return out


def total(intervals: list[Interval]) -> float:
    return sum(e - s for _, s, e in intervals)


def overlap(a: list[Interval], b: list[Interval]) -> float:
    """Seconds shared by two interval sets, counted only inside the same episode."""
    a, b = merge(a), merge(b)
    return sum(max(0.0, min(e1, e2) - max(s1, s2)) for ep1, s1, e1 in a for ep2, s2, e2 in b if ep1 == ep2)


def iou(a: list[Interval], b: list[Interval]) -> float:
    shared = overlap(a, b)
    union = total(merge(a)) + total(merge(b)) - shared
    return shared / union if union > 0 else 0.0


def inside(block: Interval | None, promo: list[Interval]) -> bool:
    """True if a block (episode, start, end) lies fully inside one of the promo's intervals."""
    if block is None:
        return False
    ep, s, e = block
    return any(ep == pe and ps - 1e-6 <= s and e <= pend + 1e-6 for pe, ps, pend in promo)


def match_level(tool: list[Interval], gold: list[Interval], gold_hook: Interval | None = None,
                gold_cliff: Interval | None = None, strict: float = 0.5, lenient: float = 0.3) -> str | None:
    """'strict' if IoU >= 0.5; 'lenient' if IoU >= 0.3 or both gold hook and cliff blocks sit inside the tool
    promo; else None."""
    v = iou(tool, gold)
    if v >= strict:
        return "strict"
    if v >= lenient or (inside(gold_hook, tool) and inside(gold_cliff, tool)):
        return "lenient"
    return None


def recall(gold_matched: list[bool], weights: list[float] | None = None) -> float | None:
    """Share of gold promos matched; weighted by quality when weights are given. None if no gold promos."""
    if not gold_matched:
        return None
    w = weights or [1.0] * len(gold_matched)
    return sum(wi for m, wi in zip(gold_matched, w) if m) / sum(w)


def precision_at_k(ratings_in_rank_order: list[int], k: int = 10, good: int = 2) -> tuple[int, int]:
    """(count of ratings >= good among the top k, number rated in the top k)."""
    top = ratings_in_rank_order[:k]
    return sum(1 for r in top if r >= good), len(top)


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1       # ties share their average rank
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman rho (Pearson on average ranks). None if fewer than 3 pairs or no variation."""
    if len(x) != len(y) or len(x) < 3:
        return None
    rx, ry = _average_ranks(x), _average_ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx, vy = sum((a - mx) ** 2 for a in rx), sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy) ** 0.5


def matched_pairs(a: list[list[Interval]], b: list[list[Interval]], threshold: float = 0.5) -> int:
    """How many promos in `a` have a one-to-one partner in `b` with IoU >= threshold (greedy, best first)."""
    pairs = sorted(((iou(x, y), i, j) for i, x in enumerate(a) for j, y in enumerate(b)), reverse=True)
    used_a: set[int] = set()
    used_b: set[int] = set()
    n = 0
    for v, i, j in pairs:
        if v < threshold:
            break
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            n += 1
    return n


def jaccard_matched(a: list[list[Interval]], b: list[list[Interval]], threshold: float = 0.5) -> float | None:
    """Jaccard of two promo lists under IoU matching: matched / (|a| + |b| - matched)."""
    if not a and not b:
        return None
    m = matched_pairs(a, b, threshold)
    return m / (len(a) + len(b) - m)
