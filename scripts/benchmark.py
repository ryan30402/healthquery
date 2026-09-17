import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import build_opener, ProxyHandler, Request

BASE_DIR = Path(__file__).resolve().parent.parent


def fingerprint(path):
    with path.open("rb") as file:
        return {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(file, "sha256").hexdigest()}


def main():
    parser = argparse.ArgumentParser(description="Measure sequential warm API requests over local HTTP.")
    parser.add_argument("--queries", type=Path, default=BASE_DIR / "evaluation/retrieval_dev_v1.jsonl")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--output", type=Path, default=BASE_DIR / "reports/latency_local.json")
    args = parser.parse_args()
    if args.repeats < 1 or args.warmup < 0:
        parser.error("repeats must be positive and warmup must be nonnegative.")
    rows = [json.loads(line) for line in args.queries.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or any(not isinstance(row.get("question"), str) or not row["question"].strip() for row in rows):
        parser.error("The query file must contain nonempty string questions.")
    artifacts = {name: fingerprint(BASE_DIR / name) for name in (
        "models/question_classifier.joblib", "models/retrieval_index.joblib", "api.py", "retrieval.py",
    )}
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))
    latencies = []
    with tempfile.TemporaryFile(mode="w+t") as server_log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
            cwd=BASE_DIR, stdout=server_log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None or time.monotonic() >= deadline:
                    server_log.seek(0)
                    raise RuntimeError("Benchmark server did not start.\n" + server_log.read())
                try:
                    with opener.open(base_url + "/health", timeout=0.5) as response:
                        health = json.load(response)
                    if health.get("status") == "ready":
                        break
                except (URLError, TimeoutError):
                    pass
                time.sleep(0.1)
            total = args.warmup + len(rows) * args.repeats
            for iteration in range(total):
                question = rows[(iteration - args.warmup) % len(rows)]["question"]
                start = time.perf_counter()
                body = json.dumps({"question": question, "top_k": 3}).encode("utf-8")
                request = Request(base_url + "/api/query", data=body, headers={"Content-Type": "application/json"})
                with opener.open(request, timeout=30) as response:
                    result = json.load(response)
                elapsed_ms = (time.perf_counter() - start) * 1000
                if result.get("question") != question.strip() or not isinstance(result.get("results"), list):
                    raise RuntimeError("The API returned an unexpected response.")
                if iteration >= args.warmup:
                    latencies.append(elapsed_ms)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    metrics = {
        "p50": statistics.median(latencies),
        "p95": statistics.quantiles(latencies, n=100, method="inclusive")[94] if len(latencies) > 1 else latencies[0],
        "mean": statistics.mean(latencies), "min": min(latencies), "max": max(latencies),
    }
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "measurement": "One sequential client over loopback HTTP; new connection per request; top_k=3.",
        "includes": "Client JSON encoding/decoding, local HTTP, validation, classification, retrieval, server JSON serialization.",
        "excludes": "Server startup, model loading, warmup, browser rendering, remote network, concurrent load.",
        "limitation": "Local development benchmark; not a production capacity test or a latency guarantee.",
        "percentile_method": "p50 median; p95 linear interpolation (inclusive).",
        "samples": len(latencies), "unique_queries": len({row["question"] for row in rows}),
        "repeats": args.repeats, "warmup_requests": args.warmup, "indexed_records": health["indexed_records"],
        "latency_ms": metrics, "samples_ms": latencies,
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "logical_cpu_count": os.cpu_count(),
            "packages": {name: version(name) for name in ("fastapi", "uvicorn", "scikit-learn", "numpy", "scipy", "joblib")},
            "thread_settings": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")},
        },
        "artifacts": artifacts, "queries": fingerprint(args.queries),
        "benchmark_code": fingerprint(Path(__file__)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Sequential warm HTTP requests: {len(latencies)}; indexed records: {health['indexed_records']}")
    print(f"Latency (ms): p50={metrics['p50']:.2f}, p95={metrics['p95']:.2f}, mean={metrics['mean']:.2f}")
    print("Local single-client measurement; startup excluded; not a capacity test.")
    print(f"Saved report: {args.output}")


if __name__ == "__main__":
    main()
