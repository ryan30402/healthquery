import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer

BASE_DIR = Path(__file__).resolve().parent.parent
input_path = BASE_DIR / "data/processed/questions.jsonl"
with input_path.open(encoding="utf-8") as file:
    rows = [json.loads(line) for line in file if line.strip()]

records = []
seen = set()
skipped_empty = 0
skipped_url = 0
duplicates = 0

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
    raise SystemExit("No source-linked answers are available for indexing.")
texts = [f"{row['question']} {row['focus']}" for row in records]
vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), norm="l2")
matrix = vectorizer.fit_transform(texts)

metadata = {
    "index_version": "lexical_v1",
    "dataset_revision": (BASE_DIR / "data/medquad_revision.txt").read_text().strip(),
    "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
    "sklearn_version": sklearn.__version__,
    "input_records": len(rows),
    "skipped_empty_question_or_answer": skipped_empty,
    "skipped_invalid_source_url": skipped_url,
    "duplicate_records_removed": duplicates,
    "indexed_records": len(records),
    "indexed_question_types": sorted({row["question_type"] for row in records}),
    "unique_source_urls": len({row["source_url"] for row in records}),
    "vocabulary_size": len(vectorizer.vocabulary_),
    "indexed_text": "question + focus",
    "deduplication": "normalized question + whitespace-normalized answer + source URL",
    "source_links_checked_online": False,
}
index = {"vectorizer": vectorizer, "matrix": matrix, "records": records, "metadata": metadata}
model_dir = BASE_DIR / "models"
report_dir = BASE_DIR / "reports"
model_dir.mkdir(exist_ok=True)
report_dir.mkdir(exist_ok=True)
joblib.dump(index, model_dir / "retrieval_index.joblib")
with (report_dir / "retrieval_index.json").open("w", encoding="utf-8") as file:
    json.dump(metadata, file, ensure_ascii=False, indent=2)

print(f"Input records: {len(rows)}")
print(f"Skipped empty questions or answers: {skipped_empty}")
print(f"Skipped invalid source URLs: {skipped_url}")
print(f"Duplicate records removed: {duplicates}")
print(f"Indexed records: {len(records)}")
print(f"Question types with indexed answers: {len(metadata['indexed_question_types'])}")
print(f"Unique source URLs: {metadata['unique_source_urls']}")
print(f"Vocabulary size: {metadata['vocabulary_size']}")
print("Saved index: models/retrieval_index.joblib")
print("Saved report: reports/retrieval_index.json")
