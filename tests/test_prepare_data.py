import json
import xml.etree.ElementTree as ET

import pytest

from scripts.prepare_data import parse_document, prepare_data


def write_xml(path, pairs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'<Document url="https://example.org/health"><Focus>Example</Focus><QAPairs>{pairs}</QAPairs></Document>',
        encoding="utf-8",
    )


def test_parse_preserves_provenance_and_multiline_answer(tmp_path):
    path = tmp_path / "collection" / "example.xml"
    write_xml(path, '<QAPair><Question qid="q1" qtype="information">What is Example?</Question><Answer>First line\n  Second line.</Answer></QAPair>')
    records, skipped = parse_document(path, tmp_path)
    assert skipped == 0
    assert records == [{
        "id": "collection/example.xml::q1",
        "question": "What is Example?",
        "question_type": "information",
        "answer": "First line\n  Second line.",
        "source_url": "https://example.org/health",
        "source_file": "collection/example.xml",
        "focus": "Example",
    }]


def test_empty_answers_retained_but_invalid_questions_skipped(tmp_path):
    path = tmp_path / "example.xml"
    pairs = [
        '<QAPair><Question qid="q1" qtype="information">Valid question</Question></QAPair>',
        '<QAPair><Question qid="q2" qtype="information">   </Question><Answer>Text</Answer></QAPair>',
        '<QAPair><Question qid="q3">Missing label</Question></QAPair>',
        '<QAPair><Answer>Missing question</Answer></QAPair>',
    ]
    write_xml(path, "".join(pairs))
    records, skipped = parse_document(path, tmp_path)
    assert len(records) == 1
    assert records[0]["answer"] == ""
    assert skipped == 3


def test_sorted_output_and_duplicates_count_without_removal(tmp_path):
    source = tmp_path / "source"
    pair = '<QAPair><Question qid="q1" qtype="information">Repeated question</Question><Answer>Text</Answer></QAPair>'
    write_xml(source / "b.xml", pair)
    write_xml(source / "a.xml", pair)
    output = tmp_path / "processed" / "questions.jsonl"
    report = prepare_data(source, output)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [row["source_file"] for row in rows] == ["a.xml", "b.xml"]
    assert report["question_records"] == 2
    assert report["records_with_answers"] == 2
    assert report["repeated_question_records"] == 1
    assert report["question_types"] == 1


def test_bad_xml_preserves_existing_output(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "bad.xml").write_text("<Document>", encoding="utf-8")
    output = tmp_path / "questions.jsonl"
    output.write_text("existing data\n", encoding="utf-8")
    with pytest.raises(ET.ParseError, match="no element found"):
        prepare_data(source, output)
    assert output.read_text(encoding="utf-8") == "existing data\n"


def test_empty_source_fails_without_output(tmp_path):
    output = tmp_path / "questions.jsonl"
    with pytest.raises(ValueError, match="No XML files"):
        prepare_data(tmp_path / "missing", output)
    assert not output.exists()


def test_duplicate_ids_rejected_without_output(tmp_path):
    pair = '<QAPair><Question qid="same" qtype="information">Question</Question></QAPair>'
    write_xml(tmp_path / "example.xml", pair + pair)
    output = tmp_path / "questions.jsonl"
    with pytest.raises(ValueError, match="Duplicate record IDs"):
        prepare_data(tmp_path, output)
    assert not output.exists()
