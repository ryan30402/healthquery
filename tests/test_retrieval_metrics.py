import pytest

from retrieval_metrics import score_ranking, summarize


@pytest.mark.parametrize("retrieved, expected", [
    (["r", "x", "y"], (1, 1, 1.0)),
    (["x", "r", "y"], (0, 1, 0.5)),
    (["x", "y", "r"], (0, 1, 1.0 / 3)),
    (["x", "y", "z", "r"], (0, 0, 0.0)),
    ([], (0, 0, 0.0)),
])
def test_rank_and_cutoff(retrieved, expected):
    result = score_ranking(retrieved, ["r"])
    assert result["hit_at_1"] == expected[0]
    assert result["hit_at_3"] == expected[1]
    assert result["rr_at_3"] == pytest.approx(expected[2])


def test_multiple_relevant_records_use_the_first_hit():
    result = score_ranking(["x", "b", "a"], ["a", "b"])
    assert result["rr_at_3"] == 0.5


def test_mean_metrics():
    scores = [score_ranking(ids, ["r"]) for ids in (["r"], ["x", "r"], [])]
    result = summarize(scores)
    assert result["hit_at_1"] == pytest.approx(1.0 / 3)
    assert result["hit_at_3"] == pytest.approx(2.0 / 3)
    assert result["mrr_at_3"] == 0.5


def test_missing_judgments_are_rejected():
    with pytest.raises(ValueError, match="known relevant"):
        score_ranking(["r"], [])


def test_empty_evaluation_is_rejected():
    with pytest.raises(ValueError, match="empty evaluation"):
        summarize([])
