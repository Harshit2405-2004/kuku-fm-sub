"""Ranker tests (TECH_SPEC §4.6): weights, bonuses, penalties, the diversity caps and the skip log."""

from pathlib import Path

import pytest

from promo_finder.build import Candidate, Segment
from promo_finder.config import load_config
from promo_finder.judge import ClipScore
from promo_finder.parse import Block, Episode, Scene
from promo_finder.rank import diversify, rank, score_candidate

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def rcfg():
    return load_config(ROOT / "config.yaml")["rank"]


def episode(n, scenes=2):
    blocks = [Block(id=f"E{n:02d}-B{s:03d}", ep=n, scene=s, type="DIALOGUE", speaker="X", start=s * 50.0,
                    end=s * 50.0 + 2, text="t") for s in range(1, scenes + 1)]
    return Episode(ep=n, source_file="f", logline="l", continuity="c", duration=200.0,
                   scenes=[Scene(ep=n, num=s, heading="h", start=s * 50.0, end=s * 50.0 + 49) for s in range(1, scenes + 1)],
                   blocks=blocks)


def cand(cid, ep=20, scene=1, total=25.0, kind="single", flags=(), extra_eps=()):
    segs = [Segment(ep=ep, start=0, end=total, start_block="x", end_block="y")]
    segs += [Segment(ep=e, start=0, end=5, start_block="x", end_block="y") for e in extra_eps]
    return Candidate(id=cid, ep=ep, type=kind, segments=segs, hook_block=f"E{ep:02d}-B{scene:03d}", cliff_block="y",
                     start_block="x", end_block="y", beat_type="other", hook_summary="", cliff_summary="",
                     reasoning="", flags=list(flags), checks={}, hook_offset_s=1.0, total_s=total)


def js(cid, hook=5, cliff=5, standalone=5, trope=5, pacing=5, risk=()):
    return ClipScore(id=cid, hook_text="h", cliff_text="c", reasons="r", hook=hook, cliff=cliff,
                     standalone=standalone, trope_pull=trope, pacing=pacing, why="w", risk_flags=list(risk))


def test_base_is_weighted_and_normalised(rcfg):
    assert score_candidate(cand("A"), js("A"), rcfg)["final_score"] == pytest.approx(1.0)
    assert score_candidate(cand("A"), js("A", 1, 1, 1, 1, 1), rcfg)["final_score"] == pytest.approx(0.0)
    # hook 5, rest 1 -> only the hook weight counts
    assert score_candidate(cand("A"), js("A", 5, 1, 1, 1, 1), rcfg)["base"] == pytest.approx(0.35)


@pytest.mark.parametrize("ep,total,kind,expected", [
    (5, 25.0, "single", {"early_episode": 0.06}),
    (6, 25.0, "single", {"mid_episode": 0.03}),
    (15, 25.0, "single", {"mid_episode": 0.03}),
    (16, 25.0, "single", {}),
    (20, 30.0, "single", {"sweet_spot": 0.03}),
    (20, 45.0, "single", {"sweet_spot": 0.03}),
    (20, 45.1, "single", {}),
    (20, 25.0, "arc", {"arc": 0.02}),
])
def test_bonuses(rcfg, ep, total, kind, expected):
    assert score_candidate(cand("A", ep=ep, total=total, kind=kind), js("A"), rcfg)["bonuses"] == expected


def test_arc_episode_bonus_uses_its_earliest_episode(rcfg):
    arc = cand("ARC-1", ep=30, kind="arc", extra_eps=(2,))
    assert "early_episode" in score_candidate(arc, js("ARC-1"), rcfg)["bonuses"]


def test_penalties_from_builder_flags_and_judge_flags(rcfg):
    c = cand("A", flags=("midshot_start", "midshot_end", "trimmed"))
    parts = score_candidate(c, js("A", risk=("needs_context", "cliff_may_resolve", "graphic_violence")), rcfg)
    assert parts["penalties"] == {"cliff_may_resolve": 0.05, "midshot_end": 0.03, "midshot_start": 0.03,
                                  "needs_context": 0.05}
    assert parts["final_score"] == pytest.approx(1.0 - 0.16)


def test_graphic_violence_is_flagged_not_penalised_or_excluded(rcfg):
    eps = {20: episode(20)}
    ranked, _, _ = rank([cand("A")], {"A": js("A", risk=("graphic_violence",))}, eps, rcfg)
    assert ranked[0]["final_score"] == pytest.approx(1.0)
    assert "Brand-safety check" in ranked[0]["posting_rationale"]


def test_max_two_per_episode_in_top_20(rcfg):
    eps = {20: episode(20, scenes=3), 21: episode(21)}
    cands = [cand("A", scene=1), cand("B", scene=2), cand("C", scene=3), cand("D", ep=21)]
    scores = {"A": js("A"), "B": js("B", hook=4), "C": js("C", hook=3), "D": js("D", hook=1)}
    ranked, skips, _ = rank(cands, scores, eps, rcfg)
    assert [r["id"] for r in ranked] == ["A", "B", "D", "C"]
    assert skips == [{"id": "C", "at_rank": 3, "reason": "already 2 promos from episode 20 in the top 20",
                      "final_score": ranked[3]["final_score"], "placed_at": 4}]


def test_max_one_per_scene_in_top_10(rcfg):
    eps = {20: episode(20), 21: episode(21)}
    cands = [cand("A", scene=1), cand("B", scene=1), cand("C", ep=21)]
    scores = {"A": js("A"), "B": js("B", hook=4), "C": js("C", hook=1)}
    ranked, skips, _ = rank(cands, scores, eps, rcfg)
    assert [r["id"] for r in ranked] == ["A", "C", "B"]
    assert skips[0]["id"] == "B" and "scene 1" in skips[0]["reason"]


def test_caps_stop_applying_after_their_window(rcfg):
    dcfg = {"top_n": 2, "max_per_episode": 1, "top_scene_n": 1, "max_per_scene": 1}
    rows = [{"id": i, "episode_key": 1, "scene_key": (1, 1), "final_score": 1 - n / 10} for n, i in enumerate("ABC")]
    ordered, skips = diversify(rows, dcfg)
    # nothing else to move up, so the caps can't hold; order is kept and the skips are recorded
    assert [r["id"] for r in ordered] == ["A", "B", "C"]
    assert [s["id"] for s in skips] == ["B", "C"]


def test_unscored_candidates_are_not_ranked(rcfg):
    ranked, _, unscored = rank([cand("A"), cand("B", ep=21)], {"A": js("A")}, {20: episode(20), 21: episode(21)}, rcfg)
    assert [r["id"] for r in ranked] == ["A"] and unscored == ["B"]
    assert ranked[0]["rank"] == 1 and ranked[0]["posting_rationale"].startswith("Strong hook 5/5")


def test_ties_break_deterministically(rcfg):
    eps = {20: episode(20), 21: episode(21)}
    a, b = cand("B", ep=20), cand("A", ep=21)
    for order in ([a, b], [b, a]):
        ranked, _, _ = rank(order, {"A": js("A"), "B": js("B")}, eps, rcfg)
        assert [r["id"] for r in ranked] == ["A", "B"]


def test_cliff_gate_keeps_low_cliff_out_of_top10_but_not_removed(rcfg):
    """D-042: 12 promos; the two best by score have cliff 2. They must drop below rank 10, still ranked."""
    eps = {n: episode(n) for n in range(20, 32)}
    cands = [cand(f"P{n}", ep=n) for n in range(20, 32)]
    scores = {f"P{n}": (js(f"P{n}", cliff=2) if n in (20, 21) else js(f"P{n}", 2, 3, 2, 2, 2)) for n in range(20, 32)}
    ranked, skips, _ = rank(cands, scores, eps, rcfg)
    assert len(ranked) == 12
    top10 = {r["id"] for r in ranked[:10]}
    assert "P20" not in top10 and "P21" not in top10
    assert {r["id"] for r in ranked[10:]} == {"P20", "P21"}
    assert any("not allowed in the top 10" in s["reason"] for s in skips)


def test_cliff_gate_off_when_not_configured(rcfg):
    rcfg = {**rcfg, "min_cliff_top10": None}
    eps = {20: episode(20)}
    ranked, _, _ = rank([cand("A", ep=20)], {"A": js("A", cliff=1)}, eps, rcfg)
    assert ranked[0]["rank"] == 1


def test_cliff_gate_fills_spots_when_too_few_pass(rcfg):
    eps = {n: episode(n) for n in (20, 21)}
    ranked, _, _ = rank([cand("A", ep=20), cand("B", ep=21)], {"A": js("A", cliff=2), "B": js("B", cliff=2)}, eps, rcfg)
    assert len(ranked) == 2          # nothing is removed; order falls back to score
