# HealthQuery v2 product release

## User experience

The English interface is now a responsive information workspace with a persistent navigation rail on desktop, a compact mobile navigation bar, a search composer, collection metadata, and source cards. Text sizes and touch targets were increased for readability. All styling and scripts are served locally.

Users can choose three or five results, insert example questions, submit with Command/Ctrl+Enter, cancel a pending request, read archived source text in a keyboard-accessible dialog, copy a source citation, and revisit or clear the five most recent questions in the current page's memory. Empty, disconnected, throttled, overloaded, and timed-out states have separate messages. Corpus counts come from the loaded index.

Archive labels remain visible. Classification is placed in a secondary expandable area and explicitly described as experimental. Full archived records are capped at 20,000 characters in the reader, with a truncation notice. Opening the original URL is a separate action; links have not been checked for current content.

## Engineering changes

- Streamed query body limit and arrival deadline; validation responses omit input values.
- Bounded per-peer rate counters and active-query admission limits, with Retry-After responses.
- Generated support IDs and structured completion logs without query text or IP addresses.
- Content Security Policy, no-referrer/nosniff headers, and no-store API responses.
- Artifact checks and prediction/search warmup before readiness; incompatible or conflicting records fail startup.
- Stable record identifiers connect search cards to their archived text.
- Compose configuration for non-root, read-only operation, capability removal, resource budgets, rotating logs, and process restart.
- Browser checks in addition to Python tests; CI configuration now exercises a built container using synthetic artifacts.

## Upgrade

Back up the existing project first, then overlay this release. Existing compatible model artifacts can be reused; this release does not change the retrieval scoring formula or retrain the classifier. Restart the service to load the new runtime code. Run `python -m scripts.finalize` only if you also want to rebuild and rerun the complete ML pipeline.

Install Python requirements and run the tests before starting:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --no-proxy-headers
```

Node/Playwright are development tools for browser verification; they are not needed to serve the application. See [OPERATIONS.md](OPERATIONS.md) for verification and deployment commands.

## Scope

This release strengthens the actual application and its operational controls. It does not establish current medical content, a high-quality independent benchmark, an uptime commitment, cloud capacity, or clinical suitability. The archived-data quality work and real-host validation described in the operations guide remain necessary for a broad commercial launch.
