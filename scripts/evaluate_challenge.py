import hashlib
import json
from collections import Counter
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, classification_report, f1_score

BASE_DIR = Path(__file__).resolve().parent.parent
challenge_path = BASE_DIR / "evaluation/challenge_v1.jsonl"
model_path = BASE_DIR / "models/question_classifier.joblib"


def normalize(text):
    return " ".join(text.lower().split())


with challenge_path.open(encoding="utf-8") as file:
    examples = [json.loads(line) for line in file if line.strip()]
if not examples:
    raise ValueError("The challenge set is empty.")

questions = [row["question"].strip() for row in examples]
expected = [row["question_type"] for row in examples]
keys = [normalize(question) for question in questions]
if "" in keys or len(keys) != len(set(keys)):
    raise ValueError("The challenge set contains empty or duplicate questions.")
ids = [row["id"] for row in examples]
if len(ids) != len(set(ids)):
    raise ValueError("The challenge set contains duplicate IDs.")

corpus_path = BASE_DIR / "data/processed/questions.jsonl"
with corpus_path.open(encoding="utf-8") as file:
    corpus_questions = {normalize(json.loads(line)["question"]) for line in file if line.strip()}
if set(keys) & corpus_questions:
    raise ValueError("A challenge question duplicates a MedQuAD question.")

classifier = joblib.load(model_path)
labels = sorted(set(expected))
if not set(labels).issubset(set(classifier.classes_)):
    raise ValueError("The challenge contains labels outside the model's supported classes.")
predictions = classifier.predict(questions).tolist()
accuracy = accuracy_score(expected, predictions)
macro_f1 = f1_score(expected, predictions, labels=labels, average="macro", zero_division=0)

details = []
for row, predicted in zip(examples, predictions):
    details.append({**row, "predicted_type": predicted, "correct": row["question_type"] == predicted})
errors = [row for row in details if not row["correct"]]

report = {
    "evaluation": "challenge_v1",
    "purpose": "AI-authored development challenge; not a final test or clinical validation.",
    "challenge_sha256": hashlib.sha256(challenge_path.read_bytes()).hexdigest(),
    "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
    "examples": len(examples),
    "label_counts": dict(Counter(expected)),
    "model_class_count": len(classifier.classes_),
    "medquad_exact_question_overlap": 0,
    "accuracy": accuracy,
    "macro_f1_over_challenge_labels": macro_f1,
    "per_class": classification_report(expected, predictions, labels=labels, output_dict=True, zero_division=0),
    "errors": errors,
    "predictions": details,
}
report_path = BASE_DIR / "reports/challenge_v1_baseline.json"
report_path.parent.mkdir(parents=True, exist_ok=True)
with report_path.open("w", encoding="utf-8") as file:
    json.dump(report, file, ensure_ascii=False, indent=2)

print(f"Challenge examples: {len(examples)}; labels: {len(labels)}/{len(classifier.classes_)}")
print("MedQuAD exact-question overlap: 0")
print(f"Challenge accuracy: {accuracy:.4f}")
print(f"Challenge macro-F1 over covered labels: {macro_f1:.4f}")
print(f"Incorrect: {len(errors)}/{len(examples)}")
print(f"Saved report: {report_path}")
for row in errors[:5]:
    print(f"- {row['question']} | expected={row['question_type']} | predicted={row['predicted_type']}")
