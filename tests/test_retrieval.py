import pytest

from retrieval import search


def test_ranking_deduplicates_sources_and_preserves_ties(tiny_index):
    results = search(tiny_index, "What causes asthma?", top_k=5)
    assert [row["source_url"] for row in results] == [
        "https://example.org/asthma",
        "https://example.org/asthma-second",
        "https://example.org/asthma-overview",
    ]
    scores = [row["lexical_similarity"] for row in results]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == pytest.approx(scores[1])
    assert all(score > 0 for score in scores)


@pytest.mark.parametrize("question", ["", " \t\n ", "zzzzqxxyy"])
def test_empty_or_unknown_terms_return_no_results(tiny_index, question):
    assert search(tiny_index, question) == []


def test_top_k_limits_results(tiny_index):
    results = search(tiny_index, "  What causes asthma?  ", top_k=1)
    assert len(results) == 1
    assert results[0]["source_url"] == "https://example.org/asthma"


@pytest.mark.parametrize("top_k", [0, -1])
def test_nonpositive_top_k_is_rejected(tiny_index, top_k):
    with pytest.raises(ValueError, match="top_k must be at least 1"):
        search(tiny_index, "asthma", top_k=top_k)
