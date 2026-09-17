from pathlib import Path
from textwrap import shorten

import joblib

from retrieval import search

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models/question_classifier.joblib"
INDEX_PATH = BASE_DIR / "models/retrieval_index.joblib"


def main():
    if not MODEL_PATH.exists():
        raise SystemExit("Model not found. Run: python scripts/train_baseline.py")
    if not INDEX_PATH.exists():
        raise SystemExit("Index not found. Run: python scripts/build_index.py")
    classifier = joblib.load(MODEL_PATH)
    index = joblib.load(INDEX_PATH)
    print("Welcome to HealthQuery!")
    print("Explore related medical information sources. Type 'quit' to exit.")
    print("Excerpts are from archived MedQuAD data; source links have not been checked for current information.")

    while True:
        try:
            question = input("\nEnter a question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if question.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break
        if not question:
            print("Please enter a medical information question.")
            continue

        predicted_type = classifier.predict([question])[0]
        print(f"Predicted question type: {predicted_type}")
        results = search(index, question, top_k=3)
        if not results:
            print("No matching source found. Try a more specific medical topic.")
            continue
        print("\nRelated source candidates:")
        for rank, result in enumerate(results, start=1):
            excerpt = shorten(result["answer"], width=360, placeholder=" ...")
            print(f"\n{rank}. {result['question']}")
            print(f"Source question type: {result['question_type']}")
            print(f"Archived excerpt (preview): {excerpt}")
            print(f"Source: {result['source_url']}")


if __name__ == "__main__":
    main()
