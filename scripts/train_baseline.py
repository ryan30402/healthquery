import json
import platform
from itertools import combinations
from pathlib import Path

import joblib
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from threadpoolctl import threadpool_limits

BASE_DIR = Path(__file__).resolve().parent.parent
SEED = 42


def normalize(text):
    return " ".join(text.lower().split())


parents = {}


def find_group(key):
    parents.setdefault(key, key)
    while parents[key] != key:
        parents[key] = parents[parents[key]]
        key = parents[key]
    return key


input_path = BASE_DIR / "data/processed/questions.jsonl"
with input_path.open(encoding="utf-8") as file:
    raw_rows = [json.loads(line) for line in file if line.strip()]

for row in raw_rows:
    document = "file:" + row["source_file"]
    for kind, value in (("focus", normalize(row["focus"])), ("url", row["source_url"].strip())):
        if value:
            parents[find_group(document)] = find_group(kind + ":" + value)

unique = {}
for row in raw_rows:
    key = normalize(row["question"])
    if key in unique and unique[key]["question_type"] != row["question_type"]:
        raise ValueError(f"Conflicting labels for question: {key}")
    row["group"] = find_group("file:" + row["source_file"])
    unique.setdefault(key, row)
rows = list(unique.values())
labels = sorted({row["question_type"] for row in rows})


def split_rows(records, folds):
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=SEED)
    groups = [row["group"] for row in records]
    targets = [row["question_type"] for row in records]
    left, right = next(splitter.split(records, targets, groups))
    return [records[i] for i in left], [records[i] for i in right]


train, holdout = split_rows(rows, 5)
validation, test = split_rows(holdout, 2)
splits = {"train": train, "validation": validation, "test": test}

for name, records in splits.items():
    if {row["question_type"] for row in records} != set(labels):
        raise ValueError(f"Missing classes in {name}; inspect the split before training.")
for left, right in combinations(splits.values(), 2):
    for field in ("group", "source_file", "source_url"):
        overlap = {row[field] for row in left if row[field]} & {row[field] for row in right if row[field]}
        if overlap:
            raise ValueError(f"Data leakage detected in {field}.")

split_dir = BASE_DIR / "data/processed/splits"
split_dir.mkdir(parents=True, exist_ok=True)
for name, records in splits.items():
    with (split_dir / f"{name}.jsonl").open("w", encoding="utf-8") as file:
        for row in records:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")

X_train = [row["question"] for row in train]
y_train = [row["question_type"] for row in train]
X_validation = [row["question"] for row in validation]
y_validation = [row["question_type"] for row in validation]

classifier = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=30000)),
    ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
])
models = {"majority": DummyClassifier(strategy="most_frequent"), "tfidf_logreg": classifier}
results = {}
for name, model in models.items():
    print(f"Training {name}...", flush=True)
    with threadpool_limits(limits=1):
        model.fit(X_train, y_train)
    predictions = model.predict(X_validation)
    accuracy = accuracy_score(y_validation, predictions)
    macro_f1 = f1_score(y_validation, predictions, labels=labels, average="macro", zero_division=0)
    results[name] = {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": classification_report(y_validation, predictions, labels=labels, output_dict=True, zero_division=0),
    }
    print(f"Validation {name}: accuracy={accuracy:.4f}, macro_f1={macro_f1:.4f}")

model_dir = BASE_DIR / "models"
report_dir = BASE_DIR / "reports"
model_dir.mkdir(exist_ok=True)
report_dir.mkdir(exist_ok=True)
joblib.dump(classifier, model_dir / "question_classifier.joblib")

revision_path = BASE_DIR / "data/medquad_revision.txt"
report = {
    "dataset_revision": revision_path.read_text().strip(),
    "python_version": platform.python_version(),
    "sklearn_version": sklearn.__version__,
    "seed": SEED,
    "raw_records": len(raw_rows),
    "unique_questions": len(rows),
    "duplicates_removed": len(raw_rows) - len(rows),
    "classes": labels,
    "split_sizes": {name: len(records) for name, records in splits.items()},
    "split_policy": "Connected file/focus/URL groups; stratified 5-fold holdout, then stratified 2-fold validation/test.",
    "evaluation_split": "validation",
    "test_evaluated": False,
    "results": results,
}
with (report_dir / "baseline_validation.json").open("w", encoding="utf-8") as file:
    json.dump(report, file, ensure_ascii=False, indent=2)

print(f"\nUnique questions: {len(rows)}; classes: {len(labels)}")
for name, records in splits.items():
    print(f"{name}: {len(records)} records")
print("Test set saved without evaluation.")
print("Saved model: models/question_classifier.joblib")
print("Saved report: reports/baseline_validation.json")
for question in ["What is diabetes?", "What causes asthma?", "How is diabetes treated?"]:
    print(f"{question} -> {classifier.predict([question])[0]}")
