# syntax=docker/dockerfile:1.7
# David's GPU service: Ollama with the fine-tuned Gemma and EmbeddingGemma baked in, plus the
# retrieval index and the Python service (duel/tzij_duel/david_app.py) that does retrieval + MBR.
# Built by Cloud Build (david/cloudbuild.yaml), which first copies the GGUF, its Modelfile and the
# index from Cloud Storage into build/david/. Nothing is downloaded at start: a cold start only
# loads files that are already in the image. infra/20-david.sh then runs david/warm_cache.py on an L4
# with this image and adds the compiled GPU kernels on top (david/Dockerfile.cache).
ARG OLLAMA_IMAGE=ollama/ollama:0.35.0

FROM ${OLLAMA_IMAGE} AS models
ARG MODEL_TAG
ARG EMBEDDING_MODEL=embeddinggemma
ENV OLLAMA_MODELS=/models
COPY build/david/model/ /build/
RUN ollama serve >/tmp/ollama.log 2>&1 & \
    for i in $(seq 1 60); do ollama list >/dev/null 2>&1 && break; sleep 1; done; \
    cd /build && ollama create "${MODEL_TAG}" -f Modelfile && ollama pull "${EMBEDDING_MODEL}" && ollama list

FROM ${OLLAMA_IMAGE}
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV OLLAMA_MODELS=/models \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_KEEP_ALIVE=-1 \
    OLLAMA_MAX_LOADED_MODELS=2 \
    OLLAMA_NUM_PARALLEL=16 \
    OLLAMA_VULKAN=0 \
    CUDA_CACHE_PATH=/cuda-cache \
    CUDA_CACHE_MAXSIZE=4294967296 \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONPATH=/app:/app/duel \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY --from=models /models /models
COPY data/__init__.py data/normalize.py data/
COPY rag/ rag/
COPY duel/ duel/
COPY .env.example .env
COPY build/david/index/tzij.sqlite rag/index/tzij.sqlite
COPY build/david/index/references.jsonl rag/index/references.jsonl
COPY david/warm_cache.py /warm_cache.py
COPY david/start.sh /start.sh
ENTRYPOINT ["/bin/sh", "/start.sh"]
