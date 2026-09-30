"""Secrets for the pipeline: the Hugging Face token for gated datasets.

Order: HF_TOKEN env var (local runs, or the Cloud Run Job, which mounts the
secret as that env var) -> Secret Manager secret `hf-token` -> none. Without a
token, gated sources are skipped with a message; the rest of the pipeline runs.
"""

from __future__ import annotations

import functools
import os

SECRET_NAME = "hf-token"


@functools.lru_cache(maxsize=1)
def hf_token() -> str | None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if token:
        return token
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "ai-experiments-487722")
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project}/secrets/{SECRET_NAME}/versions/latest"
        return client.access_secret_version(name=name).payload.data.decode().strip() or None
    except Exception as exc:  # no ADC, no permission, no secret: gated sources are skipped
        print(f"  (no Hugging Face token: {type(exc).__name__}; gated sources will be skipped)")
        return None
