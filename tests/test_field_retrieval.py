import pytest
from sklearn.metrics.pairwise import cosine_similarity

from retrieval import search
from scripts.build_index import build_index


@pytest.fixture
def answer_rows():
    return [
        {"id": "a", "question": "Alpha overview", "focus": "alpha", "question_type": "information", "answer": "Amber river", "source_url": "https://example.org/a"},
        {"id": "b", "question": "Beta overview", "focus": "beta", "question_type": "information", "answer": "Violet mountain", "source_url": "https://example.org/b"},
    ]


def test_answer_only_terms_can_retrieve_a_record(answer_rows):
    question_index = build_index(answer_rows, "question")
    dual_index = build_index(answer_rows, "dual")
    assert search(question_index, "violet mountain") == []
    assert search(dual_index, "violet mountain")[0]["id"] == "b"
    assert search(dual_index, "zzzzqxxyy") == []


@pytest.mark.parametrize("mode", ["question", "combined", "dual"])
def test_dot_product_scores_match_cosine_for_normalized_index(answer_rows, mode):
    index = build_index(answer_rows, mode)
    question = "alpha violet mountain"
    vector = index["vectorizer"].transform([question])
    expected = cosine_similarity(vector, index["matrix"]).ravel()
    if mode == "dual":
        answer_vector = index["answer_vectorizer"].transform([question])
        expected = 0.5 * expected + 0.5 * cosine_similarity(answer_vector, index["answer_matrix"]).ravel()
    positions = {row["id"]: i for i, row in enumerate(index["records"])}
    for result in search(index, question):
        assert result["lexical_similarity"] == pytest.approx(expected[positions[result["id"]]])


def test_index_excludes_empty_answers_invalid_urls_and_duplicates(answer_rows):
    rows = answer_rows + [answer_rows[0], {**answer_rows[0], "answer": ""}, {**answer_rows[1], "source_url": "javascript:alert(1)"}]
    index = build_index(rows, "dual")
    assert len(index["records"]) == 2
    assert index["metadata"]["skipped_empty_question_or_answer"] == 1
    assert index["metadata"]["skipped_invalid_source_url"] == 1
    assert index["metadata"]["duplicate_records_removed"] == 1
