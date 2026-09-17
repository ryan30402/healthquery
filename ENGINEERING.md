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

The GitHub Actions workflow runs tests under Python 3.13 and then builds the
container image on pushes, pull requests, and manual runs. A successful image
build checks packaging; it does not prove that your real models load in the
container. The local run below checks that integration separately.

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
The Docker health check calls `/health`; it does not check source links or
retrieval relevance. Plain Docker marks failed checks as unhealthy; it does not
automatically restart the container because of that status.

The image tag and transitive dependencies are not fully locked. This setup is a
development baseline; it does not promise byte-identical builds. Model quality,
retrieval evaluation, source freshness, performance measurements, and hosted
deployment remain separate work.
