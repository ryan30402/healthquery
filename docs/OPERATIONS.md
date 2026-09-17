# Operating HealthQuery v2

## Intended deployment

This release is a single-process English medical-information discovery workspace for research and education. The UI and service have operational protections, but the archived corpus and experimental classifier have not been validated for clinical decisions or broad consumer reliance. Software controls alone do not establish product-market fit or medical reliability.

The served content is the existing MedQuAD archive. The reader exposes more of a retrieved record; it does not refresh the original website or improve retrieval accuracy. Public record IDs identify archived records and do not anonymize user data.

## Start locally

```bash
source .venv/bin/activate
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --no-proxy-headers
```

The app logs a generated request ID, normalized route, HTTP method, status, elapsed time, and exception class when needed. It does not log question bodies, IP addresses, arbitrary paths, or URL query strings. The flags above disable Uvicorn's separate access log and prevent forwarded client headers from rewriting the peer address used for local quotas. Hosting platforms and reverse proxies have separate logging policies that must be checked before using real user queries.

The browser keeps up to five recent questions in this page's memory, with a Clear action. It does not put questions in localStorage, sessionStorage, or the URL. Reloading or closing the page clears this history. Requests still travel to the server for processing.

## Service settings

Set these environment variables before starting the process. Invalid numeric settings stop startup.

| Variable | Default | Behavior |
|---|---:|---|
| `HEALTHQUERY_MODEL_DIR` | `models` beside the application | Directory containing the two trusted, locally built artifacts |
| `HEALTHQUERY_BODY_LIMIT_BYTES` | 8192 | Maximum streamed body size for POST `/api/query`; the whole body also has a five-second arrival deadline |
| `HEALTHQUERY_RATE_LIMIT` | 60 | Shared query/archived-reader requests allowed per peer per window |
| `HEALTHQUERY_RATE_WINDOW_SECONDS` | 60 | Fixed-window duration |
| `HEALTHQUERY_MAX_INFLIGHT` | 4 | Active POST `/api/query` requests per worker, including body receipt and processing |

Rate limits return 429 with Retry-After. Excess active queries return 503 with Retry-After. Body-size and arrival limits return 413 and 408. Browser cancellation stops waiting for a response; an already-running CPU inference may still complete on the server. The browser's 15-second deadline is not a hard server-side CPU timeout.

The rate counter is bounded to 4,096 recently used client addresses. It is process-local and resets on restart; it is not DDoS protection, distributed billing, or an authenticated user quota. An attacker controlling many addresses can churn this cache. Keep one worker for this deployment model; adding replicas requires a coordinated edge/shared quota implementation.

With proxy-header trust disabled, many users behind a hosting reverse proxy may share one quota. Before inviting multiple external users, configure global limits and trusted client identity at the gateway, then deliberately decide how the app quota should behave. Do not enable trust for arbitrary forwarded headers. Hugging Face hosting is useful for public demonstrations but does not resolve these decisions automatically.

## Container configuration

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail 100 -f
```

Compose publishes only `127.0.0.1:8000`, mounts model files read-only, makes the root filesystem read-only, supplies a small writable `/tmp`, drops Linux capabilities, disables privilege escalation, and sets a starting CPU/memory budget. Logs rotate at 10 MB with three files. The service runs as a non-root user. Validate the configured 1 GiB budget on the actual deployment machine.

`restart: unless-stopped` restarts a process that exits; an unhealthy Docker health check alone does not trigger a restart. Readiness failures need monitoring and an operator response. A public deployment additionally needs a managed TLS endpoint and appropriate gateway body/header/time limits.

For a model-inclusive deployment, use `python -m scripts.export_space --output ../healthquery-space-v2`, then the instructions in [DEPLOYMENT.md](DEPLOYMENT.md). Always export again after changing runtime code or models. Old exported directories are not automatically synchronized.

## Readiness and support

- `/ready` returns 200 only after models load, index shape/norm/URL checks pass, and a prediction/search warmup succeeds.
- `/health` retains the earlier readiness/count response for compatibility.
- `/api/info` reports actual loaded corpus counts and index mode.
- `/openapi.json` provides the API schema. Hosted Swagger/ReDoc pages are disabled; the interface loads its scripts and styles locally under a restrictive CSP.
- Every HTTP response receives X-Request-ID. Use this identifier to find the corresponding structured log entry.

The content security policy permits only this origin's scripts/styles and explicitly permits embedding from `https://huggingface.co`. Change the embedding policy deliberately for another host. API responses, including errors, carry `Cache-Control: no-store`; the HTML shell requests cache revalidation.

A successful readiness probe says nothing about clinical quality, source-link freshness, or all possible model inputs. It is a runtime check, not an integrity signature or quality certificate.

## Incident and rollback procedure

1. Check container state and `/ready`. If startup fails, read the startup error and confirm the two model files and the dependency versions match the intended release. Load only artifacts produced by trusted project code.
2. For 429, inspect request counts at the gateway before changing quotas. For 503, inspect saturation or artifact readiness. Increasing limits without a load measurement can worsen latency or memory pressure.
3. For a failed deployment, restore the preceding source release and its matching model artifacts from the backup/export, then rebuild the image and check `/ready` and a public example query. Do not point old code at unverified new artifacts.
4. Retain the deployment's `export_manifest.json` and evaluation reports with the release record. Compare hashes to the deployed files when investigating a mismatch.
5. After recovery, record the incident, impact, root cause, and preventive action without storing users' medical questions in the incident log.

## Release verification

```bash
python -m pytest -q
python -m scripts.benchmark --output reports/product_v2_latency_local.json
npm ci
npx playwright install chromium
npm run test:browser
```

The browser check expects the service to be running at `http://127.0.0.1:8000`; override `HEALTHQUERY_BASE_URL` for another local port. It drives Chromium, tests user flows and error states, and writes screenshots/report output under `artifacts/browser`. It does not certify all assistive technologies or all browsers.

The latency benchmark always serves the fingerprinted artifacts in this repository's `models/` directory, even if your normal service uses a custom model directory. It starts a separate local server with an explicitly reported higher request quota so its 120 requests measure service latency rather than deliberate throttling. It retains all other service code and constraints. It is not a concurrent-load or cloud performance test.

CI is configured to run unit/API checks, build the container, mount a temporary synthetic corpus, and exercise the UI against that container. The synthetic corpus validates software integration; the browser tests in this release were also run locally against the real corpus. Verify the actual GitHub Actions run after pushing. Docker and hosted CI results are not implied by local Python/browser checks.

## Commercial launch acceptance work

| Area | Concrete acceptance work before a broad launch |
|---|---|
| Audience and value | Define the first research/education workflow, test it with prospective users, and agree on usefulness criteria. |
| Content maintenance | Establish permitted content sources, update ownership, checked-at timestamps, versioned ingestion, broken-link handling, and review of the content shown. |
| Retrieval quality | Collect a larger independently labeled set, include paraphrases and unsupported topics, evaluate full-record and preview relevance, and set launch thresholds before selecting a model. Current development Hit@3 is 15/24. |
| Classification | Improve or remove unreliable labels based on task evidence. The existing paraphrase challenge accuracy is 11/32. |
| Public infrastructure | Provide TLS, coordinated quotas, deployment secrets/configuration management, concurrent-load measurements, alerts, and a tested restore procedure. |
| User data and access | Decide whether accounts, saved work, or sensitive inputs are needed; implement access and retention controls for that actual requirement, including hosting logs. |
| Ownership | Assign who responds to failures and who reviews data/model changes. Complete the deployment and rollback checks on the real host. |

These items are not marked complete by adding UI polish or passing synthetic tests. This repository now supplies a stronger product and service baseline with explicit evidence for what has been implemented.
