import joblib
import pytest
from fastapi.testclient import TestClient

import api


def test_collection_metadata_comes_from_loaded_artifact(client):
    response = client.get("/api/info")
    assert response.status_code == 200
    assert response.json()["indexed_records"] == 5
    assert response.json()["source_urls"] == 4
    assert response.json()["question_types"] == 3
    assert response.json()["dataset_revision"] == "unavailable"
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/ready").json()["version"] == "2.0.0"


def test_search_result_opens_the_same_archived_record(client):
    result = client.post("/api/query", json={"question": "asthma"}).json()
    assert result["elapsed_ms"] >= 0
    first = result["results"][0]
    detail = client.get(f"/api/sources/{first['source_id']}")
    assert detail.status_code == 200
    assert detail.json()["question"] == first["question"]
    assert detail.json()["source_url"] == first["source_url"]
    assert detail.json()["answer"].startswith("Synthetic fixture text.")
    assert detail.json()["answer_truncated"] is False
    assert len(first["source_id"]) == 64


def test_missing_record_returns_a_safe_error(client):
    response = client.get("/api/sources/not-a-record")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"]


def test_reader_bounds_long_answers(artifacts):
    index = joblib.load(artifacts[1])
    index["records"][0]["answer"] = "Archived text. " * 2000
    joblib.dump(index, artifacts[1])
    with TestClient(api.app) as client:
        result = client.post("/api/query", json={"question": "asthma"}).json()["results"][0]
        detail = client.get(f"/api/sources/{result['source_id']}").json()
        assert len(detail["answer"]) == 20000
        assert detail["answer_truncated"] is True


@pytest.mark.parametrize("damage", ["matrix", "norm", "unsafe_url", "duplicate_id"])
def test_incompatible_index_fails_before_readiness(artifacts, damage):
    index = joblib.load(artifacts[1])
    if damage == "matrix":
        index["matrix"] = index["matrix"][:-1]
    elif damage == "norm":
        index["vectorizer"].norm = None
    elif damage == "duplicate_id":
        index["records"][0]["id"] = "shared-id"
        index["records"][2]["id"] = "shared-id"
    else:
        index["records"][0]["source_url"] = "javascript:alert(1)"
    joblib.dump(index, artifacts[1])
    with pytest.raises(RuntimeError):
        with TestClient(api.app):
            pass
    assert not hasattr(api.app.state, "classifier")
    assert not hasattr(api.app.state, "index")


def test_validation_does_not_echo_question_or_extra_data(client):
    response = client.post("/api/query", json={"question": "private question", "unexpected": "private data"})
    assert response.status_code == 422
    assert "private" not in response.text


def test_security_headers_and_local_assets(client):
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "https://huggingface.co" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-request-id"]
