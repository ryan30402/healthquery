# Deployment

The GitHub repository, reproducible setup, evaluation reports, and a short screen recording are enough for a portfolio submission. A public live demo is optional. This guide prepares a standalone Hugging Face Docker Space using the artifacts that you have already built and evaluated.

## 1. Export the current application

Run in the project directory with its virtual environment active:

```bash
python -m scripts.export_space
```

This creates `../healthquery-space` beside the project. It copies the current runtime code, pinned requirements, attribution, dataset revision, and the two locally generated model files. It also writes a Dockerfile, Space README configuration, and SHA-256 manifest. It neither uploads files nor loads the joblib files.

Only an explicit list of files is exported. Raw XML, training splits, personal configuration, and Git history are excluded. The retrieval artifact includes archived answer text, so retain the copied attribution. Use the model files built by your own trusted project scripts; Python's joblib format is not a safe format for untrusted model files.

Existing output directories are never overwritten. For a later export, use a new name:

```bash
python -m scripts.export_space --output ../healthquery-space-v2
```

## 2. Check the standalone container on your Mac

Docker Desktop must be running. Unlike the development container, this image contains its model files and needs no bind mount.

```bash
docker build --tag healthquery:space ../healthquery-space
docker run --rm --name healthquery-space -p 127.0.0.1:8001:8000 healthquery:space
```

Open `http://127.0.0.1:8001` and try a public example question. Open `http://127.0.0.1:8001/health` to confirm `status` is `ready` and `indexed_records` matches your current index. Press Control-C in the container terminal when finished. Port 8001 on the Mac keeps this check separate from a development server on port 8000.

The exporter and its file-selection behavior have automated tests. A successful local export does not establish that a Docker build or a remote deployment succeeded: verify those with the commands and live checks in this guide.

## 3. Create your Space

Sign in at [Create a Space](https://huggingface.co/new-space). Choose your own account, the name `healthquery`, **Docker** as the SDK, and **Blank** if a Docker template is requested. Choose visibility according to whether you want a public portfolio demo. Review the selected hardware and its displayed price before creating it.

The exported README specifies `sdk: docker` and `app_port: 8000`; the Dockerfile starts Uvicorn on that port with user ID 1000. These settings follow [Hugging Face's Docker Spaces documentation](https://huggingface.co/docs/hub/spaces-sdks-docker).

## 4. Upload only the exported directory

Homebrew installs the Hugging Face CLI outside the project's Python environment:

```bash
brew install hf
hf auth login
hf auth whoami
```

Follow the authentication prompt on your own Mac. Keep any access token private; do not paste it into source files, screenshots, or chat. `whoami` tells you the Hugging Face username to use below; it may differ from your GitHub username.

Replace `YOUR_HF_USERNAME` with that exact username, then run this command from the HealthQuery project directory:

```bash
hf upload YOUR_HF_USERNAME/healthquery ../healthquery-space . --repo-type space
```

The first argument identifies your Space, the second selects the exported local folder, and `.` places its contents at the Space repository root. This command publishes those files to the Space. The authentication, Homebrew installation, and folder-upload commands are documented in the [official Hugging Face CLI guide](https://huggingface.co/docs/huggingface_hub/guides/cli).

## 5. Verify the actual public result

Open the Space page shown after upload. Wait for its build to finish and its status to become Running. If it fails, inspect its build/runtime logs; do not claim deployment success based on upload alone.

In the live app, check a regular English question, blank input, and the source links. Confirm that the archived-data notice and experimental classification label remain visible. A working old source URL does not establish that the excerpt is current medical information.

Add the actual working Space URL to the GitHub repository's About website field and README. Until these live checks pass, use the GitHub repository and a local demo recording as your portfolio links. Do not invent a deployment URL or uptime claim.

The service is a research demo with no authentication, per-user rate limiting, or clinical validation. Use public example questions for demonstrations. Cloud latency, availability, and behavior under concurrent load remain unmeasured until you evaluate the deployed service.
