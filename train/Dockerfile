# Training image for the Cloud Run GPU job (NVIDIA L4) and the CPU finish job (finish.py); the same image runs
# as a Vertex AI job. Built with Cloud Build.
# Stage 1 compiles llama.cpp's quantizer (CPU only: quantizing doesn't need the GPU).
ARG LLAMA_CPP_TAG=b11292

FROM python:3.12-slim AS llama
ARG LLAMA_CPP_TAG
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${LLAMA_CPP_TAG} https://github.com/ggml-org/llama.cpp /opt/llama.cpp \
    && cmake -S /opt/llama.cpp -B /opt/llama.cpp/build -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF -DBUILD_SHARED_LIBS=OFF \
    && cmake --build /opt/llama.cpp/build --target llama-quantize -j"$(nproc)"

FROM python:3.12-slim
# gcc + libc headers: Triton (used by torch on CUDA) compiles a small helper at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 ca-certificates gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
# CUDA 12.6 wheels: they run on the L4 drivers of Cloud Run GPUs (>= 550).
RUN uv pip install --system --no-cache --index-url https://download.pytorch.org/whl/cu126 torch==2.14.0
COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt
# llama.cpp: the HF -> GGUF converter (Python, from the same tag) + the compiled quantizer.
COPY --from=llama /opt/llama.cpp/build/bin/llama-quantize /usr/local/bin/llama-quantize
COPY --from=llama /opt/llama.cpp/convert_hf_to_gguf.py /opt/llama.cpp/convert_hf_to_gguf.py
COPY --from=llama /opt/llama.cpp/conversion /opt/llama.cpp/conversion
COPY --from=llama /opt/llama.cpp/gguf-py /opt/llama.cpp/gguf-py
COPY --from=llama /opt/llama.cpp/models /opt/llama.cpp/models
COPY train_lora.py finish.py /app/
ENV LLAMA_CPP_DIR=/opt/llama.cpp WORK_DIR=/tmp/train_lora PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1
ENTRYPOINT ["python", "/app/train_lora.py"]
