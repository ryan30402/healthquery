import argparse
import json
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEDQUAD_REVISION = "577bd37b96c02d1833b2c9eed2de9f96964e96cb"


def element_text(element):
    return "" if element is None else "".join(element.itertext()).strip()


def parse_document(path, source):
    root = ET.parse(path).getroot()
    relative_path = path.relative_to(source).as_posix()
    records = []
    skipped = 0
    for position, pair in enumerate(root.findall(".//QAPair"), start=1):
        question = pair.find("Question")
        text = element_text(question)
        label = "" if question is None else question.get("qtype", "").strip()
        if not text or not label:
            skipped += 1
            continue
        question_id = question.get("qid", "").strip() or str(position)
        records.append({
            "id": f"{relative_path}::{question_id}",
            "question": text,
            "question_type": label,
            "answer": element_text(pair.find("Answer")),
            "source_url": root.get("url", "").strip(),
            "source_file": relative_path,
            "focus": element_text(root.find("Focus")),
        })
    return records, skipped


def prepare_data(source, output):
    source = Path(source).resolve()
    output = Path(output).resolve()
    paths = sorted(source.rglob("*.xml"))
    if not paths:
        raise ValueError(f"No XML files found in {source}. Clone the pinned MedQuAD repository first.")
    records = []
    skipped = 0
    for path in paths:
        parsed, count = parse_document(path, source)
        records.extend(parsed)
        skipped += count
    if not records:
        raise ValueError("No usable question records found; the existing output was not changed.")
    if len({row["id"] for row in records}) != len(records):
        raise ValueError("Duplicate record IDs found; the existing output was not changed.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as file:
            temporary = Path(file.name)
            for row in records:
                file.write(json.dumps(row, ensure_ascii=False) + "\n")
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    types = Counter(row["question_type"] for row in records)
    unique_questions = {" ".join(row["question"].lower().split()) for row in records}
    return {
        "xml_files": len(paths),
        "question_records": len(records),
        "question_types": len(types),
        "records_with_answers": sum(bool(row["answer"]) for row in records),
        "repeated_question_records": len(records) - len(unique_questions),
        "skipped_records": skipped,
        "top_question_types": types.most_common(10),
    }


def verify_revision(source):
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != MEDQUAD_REVISION:
        raise ValueError(f"Expected MedQuAD revision {MEDQUAD_REVISION}; found {revision}.")
    changes = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True)
    if changes.strip():
        raise ValueError("The MedQuAD checkout has local changes. Use a clean checkout for reproducible data.")
    return revision


def main():
    parser = argparse.ArgumentParser(description="Convert the pinned MedQuAD XML corpus to question records.")
    parser.add_argument("--source", type=Path, default=BASE_DIR / "data/raw/MedQuAD")
    parser.add_argument("--output", type=Path, default=BASE_DIR / "data/processed/questions.jsonl")
    args = parser.parse_args()
    try:
        if not args.source.is_dir():
            raise ValueError(f"Source directory does not exist: {args.source}")
        revision = verify_revision(args.source)
        report = prepare_data(args.source, args.output)
    except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        parser.exit(status=1, message=f"Data preparation failed: {error}\n")
    print(f"MedQuAD revision: {revision}")
    for name, value in report.items():
        if name != "top_question_types":
            print(f"{name.replace('_', ' ').capitalize()}: {value}")
    print(f"Saved to: {args.output.resolve()}")
    print("Top 10 question types:")
    for label, count in report["top_question_types"]:
        print(f"  {label}: {count}")


if __name__ == "__main__":
    main()
