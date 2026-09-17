from contextlib import asynccontextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from textwrap import shorten
from urllib.parse import urlsplit

import joblib
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel, ConfigDict, Field
from retrieval import search
from service_guard import ServiceGuard, Settings

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("HEALTHQUERY_MODEL_DIR", BASE_DIR / "models"))
MODEL_PATH = MODEL_DIR / "question_classifier.joblib"
INDEX_PATH = MODEL_DIR / "retrieval_index.joblib"
WEB_DIR = BASE_DIR / "web"
VERSION = "2.0.0"
NOTICE = "Excerpts are from archived MedQuAD data; source links have not been checked for current information."
access_logger = logging.getLogger("healthquery.access")
if not access_logger.handlers:
    access_logger.addHandler(logging.StreamHandler())
access_logger.setLevel(logging.INFO)


class QueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=5)


class SourceCandidate(BaseModel):
    source_id: str
    question: str
    question_type: str
    excerpt: str
    source_url: str
    lexical_similarity: float


class QueryResponse(BaseModel):
    question: str
    predicted_type: str
    results: list[SourceCandidate]
    notice: str
    elapsed_ms: float


class SourceDetail(BaseModel):
    source_id: str
    question: str
    question_type: str
    answer: str
    source_url: str
    answer_truncated: bool


def source_id(record):
    identity = record.get("id") or json.dumps(
        [record["question"], record["answer"], record["source_url"]], ensure_ascii=False,
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def validate_index(index):
    if not isinstance(index, dict) or not index.get("records"):
        raise RuntimeError("Index has no records; rebuild the retrieval index.")
    for vectorizer_key, matrix_key in (("vectorizer", "matrix"), ("answer_vectorizer", "answer_matrix")):
        if vectorizer_key == "answer_vectorizer" and not ({vectorizer_key, matrix_key} & index.keys()):
            continue
        if vectorizer_key not in index or matrix_key not in index:
            raise RuntimeError("Index is missing a vectorizer or matrix; rebuild it.")
        if index[vectorizer_key].norm != "l2" or index[matrix_key].shape[0] != len(index["records"]):
            raise RuntimeError("Index normalization or record count is incompatible.")
        if index[matrix_key].shape[1] != len(index[vectorizer_key].vocabulary_):
            raise RuntimeError("Index vocabulary and matrix dimensions do not match.")
    sources = {}
    for record in index["records"]:
        if any(not isinstance(record.get(key), str) or not record[key].strip() for key in ("question", "question_type", "answer", "source_url")):
            raise RuntimeError("An indexed source is incomplete; rebuild the index.")
        parsed = urlsplit(record["source_url"])
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise RuntimeError("An indexed source has an unsafe URL.")
        identifier = source_id(record)
        if identifier in sources and sources[identifier] != record:
            raise RuntimeError("Conflicting source identifiers; rebuild the index.")
        sources[identifier] = record
    return sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL_PATH.is_file():
        raise RuntimeError("Model not found. Run: python -m scripts.train_baseline")
    if not INDEX_PATH.is_file():
        raise RuntimeError("Index not found. Run: python -m scripts.build_index")
    classifier = joblib.load(MODEL_PATH)
    index = joblib.load(INDEX_PATH)
    sources = validate_index(index)
    classifier.predict(["What causes asthma?"])
    search(index, "What causes asthma?", top_k=1)
    app.state.classifier = classifier
    app.state.index = index
    app.state.sources = sources
    app.state.info = {
        "name": "HealthQuery", "version": VERSION,
        "indexed_records": len(index["records"]),
        "source_urls": len({row["source_url"] for row in index["records"]}),
        "question_types": len({row["question_type"] for row in index["records"]}),
        "dataset_revision": index.get("metadata", {}).get("dataset_revision", "unavailable"),
        "index_mode": "dual" if "answer_vectorizer" in index else ("combined" if index.get("metadata", {}).get("mode") == "combined" else "question"),
    }
    try:
        yield
    finally:
        for name in ("classifier", "index", "sources", "info"):
            delattr(app.state, name)


app = FastAPI(title="HealthQuery", version=VERSION, lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(ServiceGuard, settings=Settings.from_env())
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Use a question of 1 to 1,000 characters and a result count from 1 to 5."})


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/health")
def health():
    return {"status": "ready", "indexed_records": len(app.state.index["records"])}


@app.get("/ready")
def ready():
    if not all(hasattr(app.state, name) for name in ("classifier", "index", "sources")):
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready", "version": VERSION}


@app.get("/api/info")
def collection_info():
    return app.state.info


@app.get("/api/sources/{record_id}", response_model=SourceDetail)
def source_detail(record_id: str):
    record = app.state.sources.get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="This archived source is unavailable. Run the search again.")
    return SourceDetail(
        source_id=record_id, question=record["question"], question_type=record["question_type"],
        answer=record["answer"][:20000], source_url=record["source_url"],
        answer_truncated=len(record["answer"]) > 20000,
    )


@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest, response: Response):
    started = time.perf_counter()
    response.headers["Cache-Control"] = "no-store"
    predicted_type = str(app.state.classifier.predict([payload.question])[0])
    matches = search(app.state.index, payload.question, top_k=payload.top_k)
    results = [SourceCandidate(
        source_id=source_id(match), question=match["question"], question_type=match["question_type"],
        excerpt=shorten(match["answer"], width=360, placeholder=" ..."),
        source_url=match["source_url"], lexical_similarity=match["lexical_similarity"],
    ) for match in matches]
    return QueryResponse(
        question=payload.question, predicted_type=predicted_type, results=results, notice=NOTICE,
        elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
    )
