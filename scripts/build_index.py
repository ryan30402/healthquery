import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer

BASE_DIR = Path(__file__).resolve().parent.parent


def build_index(rows, mode):
    records = []
    seen = set()
    skipped_empty = skipped_url = duplicates = 0
    for row in rows:
        question = row["question"].strip()
        answer = row["answer"].strip()
        url = row["source_url"].strip()
        if not question or not answer:
            skipped_empty += 1
            continue
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            skipped_url += 1
            continue
        key = (" ".join(question.lower().split()), " ".join(answer.split()), url)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        records.append({**row, "question": question, "answer": answer, "source_url": url})
    if not records:
        raise ValueError("No source-linked answers are available for indexing.")
    if mode not in {"question", "combined", "dual"}:
        raise ValueError("Unknown index mode.")
    texts = [f"{row['question']} {row['focus']}" for row in records]
    if mode == "combined":
        texts = [f"{text} {row['answer']}" for text, row in zip(texts, records)]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), norm="l2")
    index = {"vectorizer": vectorizer, "matrix": vectorizer.fit_transform(texts), "records": records}
    if mode == "dual":
        answer_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), norm="l2")
        index["answer_matrix"] = answer_vectorizer.fit_transform([row["answer"] for row in records])
        index["answer_vectorizer"] = answer_vectorizer
    index["metadata"] = {
        "index_version": f"lexical_v2_{mode}",
        "mode": mode,
        "sklearn_version": sklearn.__version__,
        "input_records": len(rows),
        "skipped_empty_question_or_answer": skipped_empty,
        "skipped_invalid_source_url": skipped_url,
        "duplicate_records_removed": duplicates,
        "indexed_records": len(records),
        "indexed_question_types": sorted({row["question_type"] for row in records}),
        "unique_source_urls": len({row["source_url"] for row in records}),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "answer_vocabulary_size": len(index["answer_vectorizer"].vocabulary_) if mode == "dual" else 0,
        "scoring": "0.5 * question_focus_cosine + 0.5 * answer_cosine" if mode == "dual" else "single_field_cosine",
        "vector_norm": "l2",
        "deduplication": "normalized question + whitespace-normalized answer + source URL",
        "source_links_checked_online": False,
    }
    return index


def main():
    parser = argparse.ArgumentParser(description="Build a source-linked TF-IDF retrieval index.")
    parser.add_argument("--mode", choices=["question", "combined", "dual"], default="dual")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "models/retrieval_index.joblib")
    parser.add_argument("--report", type=Path, default=BASE_DIR / "reports/retrieval_index.json")
    args = parser.parse_args()
    input_path = BASE_DIR / "data/processed/questions.jsonl"
    with input_path.open(encoding="utf-8") as file:
        rows = [json.loads(line) for line in file if line.strip()]
    index = build_index(rows, args.mode)
    index["metadata"].update({
        "dataset_revision": (BASE_DIR / "data/medquad_revision.txt").read_text().strip(),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(index, args.output, compress=3)
    args.report.write_text(json.dumps(index["metadata"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Mode: {args.mode}; indexed records: {len(index['records'])}")
    print(f"Unique source URLs: {index['metadata']['unique_source_urls']}")
    print(f"Saved index: {args.output}")
    print(f"Saved report: {args.report}")


if __name__ == "__main__":
    main()
