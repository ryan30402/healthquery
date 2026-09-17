# Engineering checks and local containers

HealthQuery is an English medical-information research demo. Its classifier and
lexical retrieval remain experimental; passing software tests does not measure
clinical validity or natural-language accuracy.

## Automated tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests create small synthetic scikit-learn artifacts in pytest temporary folders.
They exercise loading, request validation, retrieval behavior, source formatting,
and startup errors without downloading MedQuAD or using your real model files.
These fixtures are software test data, not a medical evaluation dataset.

The GitHub Actions workflow runs tests under Python 3.13, builds the container image, and uses Chromium to check that container with temporary synthetic artifacts on pushes, pull requests, and manual runs. A successful image
build checks packaging; it does not prove that your real models load in the
container. The local run below checks real-artifact integration separately.

## Build and run locally

Install and start Docker Desktop first. Run these commands from the project root.
The `models` directory must contain your previously built
`question_classifier.joblib` and `retrieval_index.joblib`.

```bash
docker build --tag healthquery:local .
docker run --rm --name healthquery -p 127.0.0.1:8000:8000 --mount "type=bind,source=$(pwd)/models,target=/app/models,readonly" healthquery:local
```

Visit `http://127.0.0.1:8000` and search for `What causes asthma?`.
Stop an existing local Uvicorn server first if it already uses port 8000.
Press Control+C in the Docker terminal to stop this container.

The image contains the application and runtime dependencies. Models are mounted
read-only at startup rather than copied into the image. The image is therefore
not self-contained: every deployment must provide compatible model artifacts.
The container runs as a non-root user and is published only on local loopback.
The Docker health check calls `/ready`; it does not check source links or
retrieval relevance. Plain Docker marks failed checks as unhealthy; it does not
automatically restart the container because of that status.

Direct ML, numerical, and web dependencies are pinned. Some transitive dependencies and the base-image tag can change; builds are not promised to be byte-identical. Rebuild artifacts after changing the numerical environment. The pinned NumPy version avoids the NumPy 2.5/joblib shape-deprecation warnings seen during development; the third-party Starlette/AnyIO deprecation warning can still appear.

Run `python -m scripts.finalize` for the complete local training, three-candidate retrieval evaluation, tests, and loopback HTTP benchmark. It stops on a failing command. A passing release check means these commands succeeded, not that retrieval meets a clinical quality threshold or that a public service is running. Restart any running API/container after rebuilding models because they are loaded once at startup.

See [deployment instructions](docs/DEPLOYMENT.md) for a standalone container export containing the evaluated model artifacts, and [results](docs/RESULTS.md) for measured quality and latency. Remote Actions and Docker builds must be checked in their actual environments.

## Product v2

See [OPERATIONS.md](docs/OPERATIONS.md) for request limits, logging/privacy boundaries, model readiness, Docker Compose, browser verification, and concrete launch acceptance work. The default deployment uses one worker and disables proxy-header trust; quotas are process-local and can be shared by users behind a proxy.
