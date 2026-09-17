import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def run(module, *arguments):
    command = [sys.executable, "-m", module, *arguments]
    print("\nRunning: " + " ".join(command), flush=True)
    subprocess.run(command, cwd=BASE_DIR, check=True)


def main():
    if not (BASE_DIR / "data/processed/questions.jsonl").is_file():
        raise SystemExit("Prepare MedQuAD first: follow the data setup in README.md.")
    report_path = BASE_DIR / "reports/release_check.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps({"status": "in_progress"}), encoding="utf-8")
    run("scripts.train_baseline")
    run("scripts.evaluate_challenge")
    for mode in ("question", "combined", "dual"):
        index_path = "models/retrieval_index.joblib" if mode == "dual" else f"models/retrieval_index_{mode}.joblib"
        index_report = "reports/retrieval_index.json" if mode == "dual" else f"reports/retrieval_index_{mode}.json"
        run("scripts.build_index", "--mode", mode, "--output", index_path, "--report", index_report)
        run("scripts.evaluate_retrieval", "--index", index_path, "--output", f"reports/retrieval_dev_v1_{mode}.json")
    run("pytest", "-q")
    run("scripts.benchmark")
    report = {
        "status": "passed",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "checks": ["classifier_training", "classification_challenge", "three_retrieval_candidates", "pytest", "loopback_http_benchmark"],
        "selected_index": "dual",
        "docker_build_verified_by_this_script": False,
        "remote_ci_verified_by_this_script": False,
        "public_deployment_verified_by_this_script": False,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nLocal release checks passed. Docker, remote CI, and public deployment are separate checks.")


if __name__ == "__main__":
    main()
