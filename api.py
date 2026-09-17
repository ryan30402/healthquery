from contextlib import asynccontextmanager
from pathlib import Path
from textwrap import shorten

import joblib
from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from retrieval import search

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models/question_classifier.joblib"
INDEX_PATH = BASE_DIR / "models/retrieval_index.joblib"
WEB_DIR = BASE_DIR / "web"
NOTICE = "Excerpts are from archived MedQuAD data; source links have not been checked for current information."


class QueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", strict=True)
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=5)


class SourceCandidate(BaseModel):
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL_PATH.is_file():
        raise RuntimeError("Model not found. Run: python scripts/train_baseline.py")
    if not INDEX_PATH.is_file():
        raise RuntimeError("Index not found. Run: python scripts/build_index.py")
    app.state.classifier = joblib.load(MODEL_PATH)
    app.state.index = joblib.load(INDEX_PATH)
    yield
    del app.state.classifier
    del app.state.index


app = FastAPI(title="HealthQuery", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ready", "indexed_records": len(app.state.index["records"])}


@app.post("/api/query", response_model=QueryResponse)
def query(payload: QueryRequest, response: Response):
    response.headers["Cache-Control"] = "no-store"
    predicted_type = str(app.state.classifier.predict([payload.question])[0])
    matches = search(app.state.index, payload.question, top_k=payload.top_k)
    results = []
    for match in matches:
        results.append(SourceCandidate(
            question=match["question"],
            question_type=match["question_type"],
            excerpt=shorten(match["answer"], width=360, placeholder=" ..."),
            source_url=match["source_url"],
            lexical_similarity=match["lexical_similarity"],
        ))
    return QueryResponse(
        question=payload.question,
        predicted_type=predicted_type,
        results=results,
        notice=NOTICE,
    )
