import argparse
import hashlib
import json
from pathlib import Path

import joblib

from retrieval import search
from retrieval_metrics import score_ranking, summarize

BASE_DIR = Path(__file__).resolve().parent.parent


def read_jsonl(path):
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def normalize(text):
    return " ".join(text.casefold().split())


def validate_examples(examples, records, corpus):
    if not examples:
        raise ValueError("The retrieval evaluation set is empty.")
    seen_ids = set()
    seen_questions = set()
    corpus_questions = {normalize(row["question"]) for row in corpus}
    for row in examples:
        for key in ("id", "question", "topic", "intent", "relevance_note"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"A retrieval example has an invalid {key} field.")
        question = normalize(row["question"])
        if row["id"] in seen_ids or question in seen_questions:
            raise ValueError(f"Duplicate evaluation ID or question: {row['id']}")
        if question in corpus_questions:
            raise ValueError(f"Evaluation question duplicates MedQuAD: {row['id']}")
        relevant = row.get("relevant_record_ids")
        if not isinstance(relevant, list) or not relevant:
            raise ValueError(f"Missing relevance judgments: {row['id']}")
        if any(not isinstance(record_id, str) or record_id not in records for record_id in relevant):
            raise ValueError(f"Unknown relevant record ID: {row['id']}")
        if len(relevant) != len(set(relevant)):
            raise ValueError(f"Duplicate relevance judgments: {row['id']}")
        seen_ids.add(row["id"])
        seen_questions.add(question)


def describe(record):
    return {key: record[key] for key in ("id", "question", "question_type", "source_url")}


def main():
    parser = argparse.ArgumentParser(description="Evaluate known relevant records in the top three sources.")
    parser.add_argument("--queries", type=Path, default=BASE_DIR / "evaluation/retrieval_dev_v1.jsonl")
    parser.add_argument("--index", type=Path, default=BASE_DIR / "models/retrieval_index.joblib")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "reports/retrieval_dev_v1_dual.json")
    args = parser.parse_args()
    examples = read_jsonl(args.queries)
    corpus_path = BASE_DIR / "data/processed/questions.jsonl"
    corpus = read_jsonl(corpus_path)
    index = joblib.load(args.index)
    records = {row["id"]: row for row in index["records"]}
    if len(records) != len(index["records"]):
        raise ValueError("The retrieval index contains duplicate record IDs.")
    validate_examples(examples, records, corpus)
    details = []
    for example in examples:
        results = search(index, example["question"], top_k=3)
        scores = score_ranking([row["id"] for row in results], example["relevant_record_ids"])
        details.append({
            **example,
            "scores": scores,
            "known_relevant_records": [describe(records[record_id]) for record_id in example["relevant_record_ids"]],
            "retrieved": [{**describe(row), "lexical_similarity": row["lexical_similarity"]} for row in results],
        })
    metrics = summarize([row["scores"] for row in details])
    per_intent = {
        intent: summarize([row["scores"] for row in details if row["intent"] == intent])
        for intent in sorted({row["intent"] for row in details})
    }
    report = {
        "evaluation": args.queries.stem,
        "purpose": "Corpus-informed, assistant-authored development queries with partial relevance judgments.",
        "evaluation_unit": "Returned record ID after URL deduplication; not source URL alone.",
        "limitation": "Unjudged results may also be relevant. These scores do not establish clinical correctness.",
        "queries_sha256": hashlib.sha256(args.queries.read_bytes()).hexdigest(),
        "overlap_corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "index_sha256": hashlib.sha256(args.index.read_bytes()).hexdigest(),
        "search_code_sha256": hashlib.sha256((BASE_DIR / "retrieval.py").read_bytes()).hexdigest(),
        "metrics_code_sha256": hashlib.sha256((BASE_DIR / "retrieval_metrics.py").read_bytes()).hexdigest(),
        "evaluator_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "index_metadata": index.get("metadata", {}),
        "examples": len(examples),
        "medquad_exact_question_overlap": 0,
        "metrics": metrics,
        "per_intent": per_intent,
        "details": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Retrieval development queries: {len(examples)}")
    print("MedQuAD exact-question overlap: 0")
    print("Relevance judgments are partial; unjudged records may also be relevant.")
    print(f"Hit@1: {metrics['hit_at_1']:.4f}")
    print(f"Hit@3: {metrics['hit_at_3']:.4f}")
    print(f"MRR@3: {metrics['mrr_at_3']:.4f}")
    print(f"Saved report: {args.output}")
    misses = [row for row in details if not row["scores"]["hit_at_3"]]
    print(f"Queries without a labeled relevant record in top 3: {len(misses)}/{len(examples)}")
    for row in misses[:5]:
        top_question = row["retrieved"][0]["question"] if row["retrieved"] else "No results"
        print(f"- {row['question']} | top result: {top_question}")


if __name__ == "__main__":
    main()
