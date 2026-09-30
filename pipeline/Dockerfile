# Data pipeline as a Cloud Run Job. Build context: repository root.
#   gcloud builds submit --config pipeline/cloudbuild.yaml .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY data/__init__.py data/normalize.py data/
COPY pipeline/ pipeline/

# DATA_BUCKET_URI is set on the job; raw cache and outputs go to the bucket.
# The datasheet is written next to the dataset in GCS, not into the image.
ENTRYPOINT ["python", "-m", "pipeline.run", "--raw-dir", "/tmp/raw", "--out-dir", "/tmp/processed", "--datasheet", ""]
