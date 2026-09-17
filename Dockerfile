FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-baseline.txt requirements-web.txt ./
RUN python -m pip install --no-cache-dir -r requirements-web.txt
RUN useradd --create-home --uid 10001 appuser
RUN mkdir /app/models
COPY api.py retrieval.py ./
COPY web/ ./web/
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).close()"]
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
