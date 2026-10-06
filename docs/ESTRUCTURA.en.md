# Repository structure

What runs where and where each piece lives in the code. Back to the [README](../README.en.md). [Versión en español](ESTRUCTURA.md).

## Architecture

![Architecture: offline laptop vs Google Cloud](diagrams/architecture.png)

*The diagrams are labeled in Spanish, like the UI.*

- **On the laptop, inside the offline boundary:** the Tzij service (FastAPI on `:8787`) serves the translator page (`/traductor/`, the demo) and its API. Each sentence goes to David and, with internet, to Goliath. David runs in Ollama (`tzij-2026-10-mix-s7`, a LoRA on Gemma 4 E4B). The index is a SQLite file with `sqlite-vec` (EmbeddingGemma vectors) and FTS5 (BM25).
- **The duel view** (`/presentador/` and `/validar/`, from an earlier version of the talk) is still in the service, but it is not part of the demo.
- **On Google Cloud:** Goliath (`gemini-3.8-flash` on Vertex AI, `global`) and two Cloud Run Jobs, one for the data and one for the GPU fine-tune. Their outputs land in Cloud Storage. The laptop only downloads datasets and models while preparing, never during the talk.

Diagram sources: [`diagrams/`](diagrams/) (HTML, SVG and PNG).

## Pipeline

![From licensed data to the variant that goes on stage](diagrams/pipeline.png)

## Repo map

```
data/          normalize.py (orthography), SOURCES.md, DATASHEET.md (generated)
pipeline/      run.py → sources/ (one per source) → clean.py → split.py → manifest/datasheet
               validate_test.py (automatic validation), review.py / apply_review.py (optional native review)
               train_set.py (chat JSONL, RAFT), monolingual.py + back_translate.py (back-translation), distill.py (distillation),
               niche.py (the specialty: Firefox Focus out of train, `make niche-data`)
               Dockerfile + cloudbuild.yaml (image for the data Cloud Run Job)
rag/           embedder.py (EmbeddingGemma via Ollama), store.py (sqlite-vec),
               build_index.py, retrieve.py (hybrid BM25 + vectors with RRF, examples + glossary)
duel/
  duel_core/   Ollama and Gemini clients, the two translations in parallel, chrF++, cost, connectivity
  tzij_duel/   FastAPI service (main.py: /api/translate and /api/examples for the translator): variants.py, prompts.py, examples.py, model_card.py; deck.py, rounds.py and lan.py (duel view); warmup.py and preflight.py (talk day)
  examples.json  example phrases of /traductor/ (`make examples`), checked live with David and Goliath
evals/         run_eval.py → report.md, tune_retrieval.py → tuning.md, fertility.py → fertility.md, human_eval.md
train/         train_lora.py (TRL + PEFT → merge → GGUF), submit_job.py (Cloud Run Job), chain.sh (chunks that continue the previous adapter),
               finish_local.py, train_local.py, pull_model.sh, colab.ipynb, runs/
infra/         env.sh, 01-train-service-account.sh, 02-train-image.sh, 03-train-job.sh, 10-data-job.sh
web/           Next.js: app/traductor (the demo; lib/translator.ts), app/presentador and app/validar (duel view), components/, lib/, tests/
tests/         pipeline, normalization, retrieval and fertility tests
docs/          ONBOARDING.md, DEMO.md (+ .en), BITACORA.md, DECISIONES.md, COMANDOS.md, ESTRUCTURA.md, CREDITOS.md,
               diagrams/, demo/ (every translation in a screenshot is unvalidated model output)
MODEL_CARD.md  what David is, its data, results and limits
```

Generated files that are not committed: `data/raw/`, `data/processed/`, `data/review/`, `data/train/`, `rag/index/`, `evals/runs/`, `models/`, `web/out/`.
