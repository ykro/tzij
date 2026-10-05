# Estructura del repositorio

Qué corre dónde y dónde está cada cosa en el código. Volver al [README](../README.md). [English version](ESTRUCTURA.en.md).

## Arquitectura

![Arquitectura: laptop sin internet frente a Google Cloud](diagrams/architecture.png)

- **En la laptop, dentro del límite sin internet:** el servicio de duelo (FastAPI en `:8787`) sirve la API, el flujo de eventos (SSE) y las dos vistas compiladas (`/presentador/` y `/validar/`). David corre en Ollama (`tzij-2026-10-mix-s7`, LoRA sobre Gemma 4 E4B). El índice es un archivo SQLite con `sqlite-vec` (vectores de EmbeddingGemma) y FTS5 (BM25).
- **En la LAN (opcional):** si hay una persona validadora, su teléfono abre el QR de la vista del presentador y vota desde ahí. El demo completo funciona sin ella: las rondas de evaluación se califican solas con chrF++.
- **En Google Cloud:** Goliath (`gemini-3.8-flash` en Vertex AI, `global`) y dos Cloud Run Jobs, uno para los datos y otro para el fine-tune en GPU. Sus salidas quedan en Cloud Storage. La laptop solo baja datasets y modelos mientras se prepara, no durante la charla.

Fuente de los diagramas: [`diagrams/`](diagrams/) (HTML, SVG y PNG).

## Pipeline

![De los datos con licencia a la variante que sube al escenario](diagrams/pipeline.png)

## Mapa del repositorio

```
data/          normalize.py (ortografía), SOURCES.md, DATASHEET.md (generado)
pipeline/      run.py → sources/ (una por fuente) → clean.py → split.py → manifest/datasheet
               validate_test.py (validación automática), review.py / apply_review.py (revisión nativa opcional)
               train_set.py (JSONL de chat, RAFT), monolingual.py + back_translate.py (retrotraducción), distill.py (destilación)
               Dockerfile + cloudbuild.yaml (imagen del Cloud Run Job de datos)
rag/           embedder.py (EmbeddingGemma vía Ollama), store.py (sqlite-vec),
               build_index.py, retrieve.py (híbrida BM25 + vectores con RRF, ejemplos + glosario)
duel/
  duel_core/   clientes de Ollama y Gemini, duelo en paralelo, chrF++, costo, conectividad
  tzij_duel/   servicio FastAPI: variants.py, prompts.py, deck.py, rounds.py, model_card.py, lan.py
evals/         run_eval.py → report.md, tune_retrieval.py → tuning.md, fertility.py → fertility.md, human_eval.md
train/         train_lora.py (TRL + PEFT → merge → GGUF), submit_job.py (Cloud Run Job),
               finish_local.py, train_local.py, pull_model.sh, colab.ipynb, runs/
infra/         env.sh, 01-train-service-account.sh, 02-train-image.sh, 03-train-job.sh, 10-data-job.sh
web/           Next.js: app/presentador, app/validar, components/, lib/, tests/
tests/         pruebas del pipeline, normalización, recuperación y fertilidad
docs/          ONBOARDING.md, DEMO.md, BITACORA.md, DECISIONES.md, COMANDOS.md, ESTRUCTURA.md, CREDITOS.md,
               diagrams/, screenshots/ (toda traducción en una captura es salida del modelo, sin validar)
MODEL_CARD.md  qué es David, con qué datos, resultados y límites
```

Archivos generados que no se suben a git: `data/raw/`, `data/processed/`, `data/review/`, `data/train/`, `rag/index/`, `evals/runs/`, `models/`, `web/out/`.
