# Repository structure

What runs where and where each piece lives in the code. Back to the [README](../README.en.md). [Versión en español](ESTRUCTURA.md).

## Architecture

![Architecture: offline laptop vs Google Cloud](diagrams/architecture.png)

*The diagrams are labeled in Spanish, like the UI.*

- **On the laptop, inside the offline boundary:** the duel service (FastAPI on `:8787`) serves the API, the event stream (SSE) and both built views (`/presentador/` and `/validar/`). David runs in Ollama (`tzij-2026-10-mix-s7`, a LoRA on Gemma 4 E4B). The index is a SQLite file with `sqlite-vec` (EmbeddingGemma vectors) and FTS5 (BM25).
- **On the LAN (optional):** if there is a validator, their phone opens the QR code on the presenter view and votes from there. The whole demo works without one: evaluation rounds are scored automatically with chrF++.
- **On Google Cloud:** Goliath (`gemini-3.8-flash` on Vertex AI, `global`) and two Cloud Run Jobs, one for the data and one for the GPU fine-tune. Their outputs land in Cloud Storage. The laptop only downloads datasets and models while preparing, never during the talk.

Diagram sources: [`diagrams/`](diagrams/) (HTML, SVG and PNG).

## Pipeline

![From licensed data to the variant that goes on stage](diagrams/pipeline.png)

## Repo map

```
data/          normalize.py (orthography), SOURCES.md, DATASHEET.md (generated)
pipeline/      run.py → sources/ (one per source) → clean.py → split.py → manifest/datasheet
               validate_test.py (automatic validation), review.py / apply_review.py (optional native review)
               train_set.py (chat JSONL, RAFT), monolingual.py + back_translate.py (back-translation), distill.py (distillation)
               Dockerfile + cloudbuild.yaml (image for the data Cloud Run Job)
rag/           embedder.py (EmbeddingGemma via Ollama), store.py (sqlite-vec),
               build_index.py, retrieve.py (hybrid BM25 + vectors with RRF, examples + glossary)
duel/
  duel_core/   Ollama and Gemini clients, parallel duel, chrF++, cost, connectivity
  tzij_duel/   FastAPI service: variants.py, prompts.py, deck.py, rounds.py, model_card.py, lan.py; warmup.py and preflight.py (talk day)
evals/         run_eval.py → report.md, tune_retrieval.py → tuning.md, fertility.py → fertility.md, human_eval.md
train/         train_lora.py (TRL + PEFT → merge → GGUF), submit_job.py (Cloud Run Job), chain.sh (chunks that continue the previous adapter),
               finish_local.py, train_local.py, pull_model.sh, colab.ipynb, runs/
infra/         env.sh, 01-train-service-account.sh, 02-train-image.sh, 03-train-job.sh, 10-data-job.sh
web/           Next.js: app/presentador, app/validar, components/, lib/, tests/
tests/         pipeline, normalization, retrieval and fertility tests
docs/          ONBOARDING.md, DEMO.md, BITACORA.md, DECISIONES.md, COMANDOS.md, ESTRUCTURA.md, CREDITOS.md,
               diagrams/, screenshots/ (every translation in a screenshot is unvalidated model output)
MODEL_CARD.md  what David is, its data, results and limits
```

Generated files that are not committed: `data/raw/`, `data/processed/`, `data/review/`, `data/train/`, `rag/index/`, `evals/runs/`, `models/`, `web/out/`.
