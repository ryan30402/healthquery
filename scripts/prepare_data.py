import json
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent.parent
raw_dir = BASE_DIR / "data/raw/MedQuAD"
output_dir = BASE_DIR / "data/processed"

xml_files = sorted(raw_dir.rglob("*.xml"))
if not xml_files:
    raise SystemExit("No XML files found. Download MedQuAD first.")

rows = []
skipped = 0

for path in xml_files:
    document = ET.parse(path).getroot()

    for pair in document.findall(".//QAPair"):
        question_node = pair.find("Question")
        if question_node is None:
            skipped += 1
            continue

        question = "".join(question_node.itertext()).strip()
        label = question_node.get("qtype", "").strip()

        if not question or not label:
            skipped += 1
            continue

        answer_node = pair.find("Answer")
        answer = ""
        if answer_node is not None:
            answer = "".join(answer_node.itertext()).strip()

        source_file = path.relative_to(raw_dir).as_posix()

        rows.append({
            "id": f"{source_file}::{question_node.get('qid', '')}",
            "question": question,
            "question_type": label,
            "answer": answer,
            "source_url": document.get("url", ""),
            "source_file": source_file,
            "focus": document.findtext("Focus", default="").strip(),
        })

output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "questions.jsonl"

with output_path.open("w", encoding="utf-8") as file:
    for row in rows:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")

counts = Counter(row["question_type"] for row in rows)
normalized = [
    " ".join(row["question"].lower().split())
    for row in rows
]
repeated = len(rows) - len(set(normalized))
with_answers = sum(bool(row["answer"]) for row in rows)

print(f"XML files: {len(xml_files)}")
print(f"Question records: {len(rows)}")
print(f"Question types: {len(counts)}")
print(f"Records with answers: {with_answers}")
print(f"Repeated question records: {repeated}")
print(f"Skipped records: {skipped}")
print(f"Saved to: {output_path}")

print("\nTop 10 question types:")
for label, count in counts.most_common(10):
    print(f"  {label}: {count}")
