from pathlib import Path

import joblib

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models/question_classifier.joblib"


def main():
    if not MODEL_PATH.exists():
        raise SystemExit("Model not found. Run: python scripts/train_baseline.py")
    classifier = joblib.load(MODEL_PATH)
    print("Welcome to HealthQuery!")
    print("Classify medical information questions. Type 'quit' to exit.")

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


if __name__ == "__main__":
    main()
