# syntax=docker/dockerfile:1.7
# The demo page: the static export of web/ and the Python service that calls David and Gemini.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv PYTHONPATH=/app:/app/duel PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project --python-preference only-system
COPY data/__init__.py data/normalize.py data/
COPY rag/ rag/
COPY duel/ duel/
COPY .env.example .env
COPY --from=web /web/out web/out
CMD ["sh", "-c", "exec /opt/venv/bin/uvicorn tzij_duel.page:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}"]
