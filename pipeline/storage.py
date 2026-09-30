"""Where pipeline files live: local disk, mirrored to the tzij-data bucket.

The raw cache is synced both ways so the Cloud Run Job doesn't re-download a
1.4 GB Wiktionary dump on every run, and versioned outputs are uploaded under
datasets/<version>/ with a LATEST pointer. Raw files stay out of git because
some licenses allow use but not redistribution.
"""

from __future__ import annotations

from pathlib import Path


def _bucket_and_prefix(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"expected gs:// URI, got {uri}")
    bucket, _, prefix = uri[5:].partition("/")
    return bucket, prefix.strip("/")


def _client():
    from google.cloud import storage  # imported lazily: local runs don't need GCP

    return storage.Client()


def pull_tree(uri: str, local: Path) -> int:
    """Download every object under uri that isn't already on disk."""
    bucket_name, prefix = _bucket_and_prefix(uri)
    bucket = _client().bucket(bucket_name)
    count = 0
    for blob in bucket.list_blobs(prefix=prefix + "/" if prefix else None):
        relative = blob.name[len(prefix) + 1:] if prefix else blob.name
        dest = local / relative
        if not relative or dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(dest)
        count += 1
    return count


def push_tree(local: Path, uri: str, *, only_new: bool = True) -> int:
    bucket_name, prefix = _bucket_and_prefix(uri)
    bucket = _client().bucket(bucket_name)
    existing = {b.name for b in bucket.list_blobs(prefix=prefix + "/" if prefix else None)} if only_new else set()
    count = 0
    for path in sorted(local.rglob("*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue
        name = f"{prefix}/{path.relative_to(local).as_posix()}" if prefix else path.relative_to(local).as_posix()
        if name in existing:
            continue
        bucket.blob(name).upload_from_filename(path)
        count += 1
    return count


def write_text(uri: str, text: str) -> None:
    bucket_name, name = _bucket_and_prefix(uri)
    _client().bucket(bucket_name).blob(name).upload_from_string(text)


def read_text(uri: str) -> str:
    bucket_name, name = _bucket_and_prefix(uri)
    return _client().bucket(bucket_name).blob(name).download_as_text()
