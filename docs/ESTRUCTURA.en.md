# Repository structure

What runs where and where each piece lives in the code. Back to the [README](../README.en.md). [Versión en español](ESTRUCTURA.md).

## Architecture

![Architecture: everything on Google Cloud](diagrams/architecture.png)

*The diagrams are labeled in Spanish, like the UI.*

Everything runs on Google Cloud (project `ai-experiments-487722`); the laptop only opens the page.

- **The page** (Cloud Run `tzij`, `europe-west4`, public): the static export of `web/` and its Python service (`duel/tzij_duel/page.py`). For each sentence it asks David and Goliath separately, so each column fills as soon as its model answers, and it times both from the same place.
- **David** (Cloud Run `tzij-david`, `europe-west4`, private, 1× NVIDIA L4): Ollama with `tzij-2026-10-mix-s7` (a LoRA on Gemma 4 E4B, Q4_K_M) and EmbeddingGemma, the retrieval index (SQLite with `sqlite-vec` and FTS5) and MBR-4 decoding, in one container (`david/Dockerfile`, service `duel/tzij_duel/david_app.py`). Only the page's service account can call it. It scales to zero when nobody uses the page, and the page wakes it when it opens.
- **Goliath:** `gemini-3.8-flash` on Vertex AI (`global`), called from the page's service.
- **Data and training:** a Cloud Run Job builds the datasets in Cloud Storage; the fine-tune runs as a Cloud Run Job with one L4, and E4B's merge + GGUF on a Cloud Batch VM with 64 GB. Models live in the models bucket and David's image carries them inside.

Diagram sources: [`diagrams/`](diagrams/) (HTML, SVG and PNG).

## Pipeline

![From licensed data to the page's model](diagrams/pipeline.png)

## Repository map

```
data/          normalize.py (orthography), SOURCES.md, DATASHEET.md (generated)
pipeline/      run.py → sources/ (one per source) → clean.py → split.py → manifest/datasheet
               validate_test.py (automatic validation), review.py / apply_review.py (optional native review)
               train_set.py (chat JSONL, RAFT), monolingual.py + back_translate.py (back-translation), distill.py (distillation),
               niche.py (the specialty: Firefox Focus held out of train, `make niche-data`)
               Dockerfile + cloudbuild.yaml (image of the data Cloud Run Job)
rag/           embedder.py (EmbeddingGemma via Ollama), store.py (sqlite-vec),
               build_index.py, retrieve.py (hybrid BM25 + vectors with RRF, examples + glossary)
duel/
  duel_core/   Ollama and Gemini clients, chrF++, cost, connectivity
  tzij_duel/   page.py (the page's service), david_app.py (David's GPU service), remote.py (the page calls David with an
               identity token), variants.py, prompts.py, examples.py, settings.py, dataset.py
  examples.json  the page's example sentences (`make examples`), checked against the cloud David and Goliath
david/         Dockerfile (Ollama + models + index + service), cloudbuild.yaml, start.sh
page/          Dockerfile (exported Next.js + the page's service), cloudbuild.yaml
evals/         run_eval.py → report.md, tune_retrieval.py → tuning.md, niche_report.py → niche_results.md,
               fertility.py → fertility.md, human_eval.md
train/         train_lora.py (TRL + PEFT → merge → GGUF), finish.py (adapter → GGUF), submit_job.py (Cloud Run Jobs),
               chain.sh (chunks that continue the previous adapter), colab.ipynb, runs/
infra/         env.sh, 00-project.sh, 01-train-service-account.sh, 02-train-image.sh, 03-train-job.sh,
               04-finish-batch.sh (E4B merge on Cloud Batch), 10-data-job.sh, 20-david.sh, 21-page.sh
web/           Next.js: app/page.tsx (the page), lib/translator.ts, components/Brand.tsx, tests/
tests/         pipeline, normalization, retrieval and fertility tests
docs/          ONBOARDING.md, DEMO.md (+ .en), BITACORA.md, DECISIONES.md, COMANDOS.md, ESTRUCTURA.md, CREDITOS.md,
               diagrams/, demo/ (every translation in a screenshot is model output, not validated)
MODEL_CARD.md  what David is, its data, results and limits
```

Generated files not committed: `data/raw/`, `data/processed/`, `data/review/`, `data/train/`, `rag/index/`, `evals/runs/`, `web/out/`.
