import pytest
from fastapi.testclient import TestClient

import api


def test_health_and_web(client):
    assert client.get("/health").json() == {"status": "ready", "indexed_records": 5}
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "HealthQuery" in page.text
    for filename in ("style.css", "app.js"):
        response = client.get(f"/static/{filename}")
        assert response.status_code == 200
        assert response.content


@pytest.mark.parametrize("top_k, count", [(1, 1), (3, 3), (5, 3)])
def test_query_returns_source_candidates(client, top_k, count):
    response = client.post("/api/query", json={"question": "  What causes asthma?  ", "top_k": top_k})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["question"] == "What causes asthma?"
    assert body["predicted_type"] == "causes"
    assert "archived MedQuAD" in body["notice"]
    results = body["results"]
    assert len(results) == count
    assert len({row["source_url"] for row in results}) == count
    assert results[0]["source_url"] == "https://example.org/asthma"
    for row in results:
        assert 0 < row["lexical_similarity"] <= 1 + 1e-12
        assert len(row["excerpt"]) <= 360
        assert row["excerpt"].endswith(" ...")
        assert "\n" not in row["excerpt"]


def test_unknown_vocabulary_returns_empty_results(client):
    response = client.post("/api/query", json={"question": "zzzzqxxyy"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_maximum_question_length_and_default_result_count(client):
    question = "asthma " + "x" * 993
    response = client.post("/api/query", json={"question": question})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 3


@pytest.mark.parametrize("payload", [
    {}, {"question": ""}, {"question": " \t\n "}, {"question": "x" * 1001},
    {"question": None}, {"question": 123}, {"question": ["asthma"]},
    {"question": "asthma", "top_k": 0}, {"question": "asthma", "top_k": 6},
    {"question": "asthma", "top_k": True}, {"question": "asthma", "top_k": "3"},
    {"question": "asthma", "top_k": 1.5}, {"question": "asthma", "unexpected": "value"},
])
def test_invalid_input_returns_validation_error(client, payload):
    response = client.post("/api/query", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]


def test_malformed_json_returns_validation_error(client):
    response = client.post("/api/query", content="{broken", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


@pytest.mark.parametrize("position, message", [(0, "Model not found"), (1, "Index not found")])
def test_missing_artifact_prevents_startup(artifacts, position, message):
    artifacts[position].unlink()
    with pytest.raises(RuntimeError, match=message):
        with TestClient(api.app):
            pass
    assert not hasattr(api.app.state, "classifier")
    assert not hasattr(api.app.state, "index")


def test_shutdown_releases_loaded_artifacts(artifacts):
    with TestClient(api.app) as client:
        assert client.get("/health").status_code == 200
    assert not hasattr(api.app.state, "classifier")
    assert not hasattr(api.app.state, "index")
