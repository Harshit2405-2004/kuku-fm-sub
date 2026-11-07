"""Metrics tests: IoU (single and multi-segment), matching levels, recall, precision@10, Spearman, Jaccard."""
import pytest

from promo_finder.metrics import (iou, jaccard_matched, match_level, merge, parse_gold_segments, precision_at_k,
                                  recall, spearman)


def test_parse_gold_segments_single_multi_none():
    assert parse_gold_segments("E01 00:11.0-00:41.5") == [(1, 11.0, 41.5)]
    assert parse_gold_segments("E01 01:02.0-01:40.0; E02 00:03.0-00:20.0") == [(1, 62.0, 100.0), (2, 3.0, 20.0)]
    assert parse_gold_segments("NONE") == [] and parse_gold_segments("") == []


def test_iou_single_segment():
    assert iou([(1, 0, 10)], [(1, 5, 15)]) == pytest.approx(5 / 15)
    assert iou([(1, 0, 10)], [(1, 0, 10)]) == 1.0
    assert iou([(1, 0, 10)], [(1, 10, 20)]) == 0.0


def test_iou_ignores_other_episodes_and_handles_multi_segment():
    assert iou([(1, 0, 10)], [(2, 0, 10)]) == 0.0
    a = [(1, 0, 10), (2, 0, 10)]
    b = [(1, 0, 10), (2, 5, 15)]
    assert iou(a, b) == pytest.approx(15 / 25)


def test_overlapping_intervals_in_one_promo_are_merged():
    assert merge([(1, 0, 10), (1, 5, 12)]) == [(1, 0, 12)]
    assert iou([(1, 0, 10), (1, 5, 12)], [(1, 0, 12)]) == 1.0


def test_match_levels():
    gold = [(1, 0, 20)]
    assert match_level([(1, 0, 20)], gold) == "strict"
    assert match_level([(1, 0, 10)], gold) == "strict"          # IoU exactly 0.5
    assert match_level([(1, 0, 7)], gold) == "lenient"          # 0.35
    assert match_level([(1, 0, 5)], gold) is None               # 0.25
    assert match_level([(1, 0, 8)], gold) == "lenient"          # 0.4
    # long tool promo, IoU 0.2, but both gold blocks inside it
    assert match_level([(1, 0, 100)], gold, (1, 2, 3), (1, 18, 19)) == "lenient"
    assert match_level([(1, 0, 100)], gold, (1, 2, 3), (1, 150, 151)) is None


def test_recall_plain_and_weighted():
    assert recall([True, False, True, True]) == 0.75
    assert recall([True, False], [3, 1]) == 0.75
    assert recall([]) is None


def test_precision_at_k_counts_only_top_k():
    assert precision_at_k([2, 2, 0, 1, 2, 0, 0, 0, 0, 0, 2, 2]) == (3, 10)
    assert precision_at_k([2, 1]) == (1, 2)


def test_spearman_known_values():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert spearman([1, 2, 2, 4], [1, 2, 3, 4]) == pytest.approx(0.9486833, abs=1e-5)  # ties share rank
    assert spearman([1, 1, 1], [1, 2, 3]) is None and spearman([1, 2], [1, 2]) is None


def test_jaccard_matched():
    a = [[(1, 0, 10)], [(2, 0, 10)]]
    b = [[(1, 0, 10)], [(3, 0, 10)]]
    assert jaccard_matched(a, b) == pytest.approx(1 / 3)
    assert jaccard_matched(a, a) == 1.0 and jaccard_matched([], []) is None
