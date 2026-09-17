import joblib
import pytest
from fastapi.testclient import TestClient
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline

import api


@pytest.fixture
def tiny_index():
    rows = [
        ("What causes asthma?", "causes", "asthma"),
        ("What causes asthma?", "causes", "asthma"),
        ("What causes asthma?", "causes", "asthma-second"),
        ("Asthma overview", "information", "asthma-overview"),
        ("Diabetes treatment", "treatment", "diabetes"),
    ]
    records = [
        {
            "question": question,
            "question_type": label,
            "focus": "diabetes" if slug == "diabetes" else "asthma",
            "answer": "Synthetic fixture text.\n" * 40,
            "source_url": f"https://example.org/{slug}",
        }
        for question, label, slug in rows
    ]
    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform([row["question"] for row in records])
    return {"vectorizer": vectorizer, "matrix": matrix, "records": records}


@pytest.fixture
def artifacts(tmp_path, monkeypatch, tiny_index):
    model_path = tmp_path / "classifier.joblib"
    index_path = tmp_path / "index.joblib"
    classifier = make_pipeline(TfidfVectorizer(), DummyClassifier(strategy="most_frequent"))
    classifier.fit(
        [row["question"] for row in tiny_index["records"]],
        [row["question_type"] for row in tiny_index["records"]],
    )
    joblib.dump(classifier, model_path)
    joblib.dump(tiny_index, index_path)
    monkeypatch.setattr(api, "MODEL_PATH", model_path)
    monkeypatch.setattr(api, "INDEX_PATH", index_path)
    return model_path, index_path


@pytest.fixture
def client(artifacts):
    with TestClient(api.app) as test_client:
        yield test_client
