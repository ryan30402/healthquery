"""Create isolated synthetic models for browser tests, never real project models."""

import argparse
from pathlib import Path

import joblib
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New, isolated model directory; must not exist.")
    output = parser.parse_args().output.resolve()
    if output.exists():
        parser.error(f"Refusing to overwrite an existing path: {output}")
    rows = [
        ("asthma-causes", "What causes asthma?", "causes", "asthma"),
        ("asthma-overview", "What is asthma?", "information", "asthma"),
        ("asthma-treatment", "How is asthma treated?", "treatment", "asthma"),
        ("diabetes-overview", "What is diabetes?", "information", "diabetes"),
    ]
    records = [
        {
            "id": f"browser-fixture::{slug}",
            "question": question,
            "question_type": label,
            "focus": focus,
            "answer": "Synthetic browser-test content. This is not medical information. " * 12,
            "source_url": f"https://example.org/{slug}",
            "source_file": "browser-fixture.xml",
        }
        for slug, question, label, focus in rows
    ]
    texts = [record["question"] for record in records]
    vectorizer = TfidfVectorizer(stop_words="english", norm="l2")
    matrix = vectorizer.fit_transform(texts)
    classifier = make_pipeline(TfidfVectorizer(), DummyClassifier(strategy="most_frequent"))
    classifier.fit(texts, [record["question_type"] for record in records])
    index = {
        "vectorizer": vectorizer,
        "matrix": matrix,
        "records": records,
        "metadata": {"index_version": "lexical_v1", "dataset_revision": "synthetic-browser-fixture"},
    }
    output.mkdir(parents=True, exist_ok=False)
    joblib.dump(classifier, output / "question_classifier.joblib")
    joblib.dump(index, output / "retrieval_index.joblib")
    print(f"Synthetic browser-test models saved to: {output}")


if __name__ == "__main__":
    main()
