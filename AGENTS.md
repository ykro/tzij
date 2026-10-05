# Tzij — Spanish ↔ K'iche' translator

Talk: **David vs. Goliath: cómo un modelo pequeño le gana a un modelo frontier.**

Tzij ("word" in K'iche') is a small Gemma model that translates between Spanish and K'iche' (ISO 639-3 `quc`), Guatemala's most widely spoken Mayan language. It runs on the laptop with no internet and competes live against Gemini. Its advantage comes from K'iche' data gathered from the web, used for retrieval (RAG), fine-tuning, or both — whichever the evals show works best.

## What the talk teaches

| Principle | Where |
| --- | --- |
| Data the big models don't have | `data/SOURCES.md`, licensed web sources only, orthography normalization |
| When NOT to fine-tune | `make eval` compares RAG vs FT vs FT+RAG; 2,000-pair threshold visible |
| Honest evals | split by source, chrF++, native-speaker validation, token fertility |
| AI for communities without connectivity | everything at runtime works offline |

## Components

| Component | Stack | Runs on | Why |
| --- | --- | --- | --- |
| Source research | Web search, documented source list | Coding agent | — |
| Data pipeline (`pipeline/`) | Python: download, clean, normalize, split by source | Cloud Run Job → `gs://ai-experiments-487722-tzij-data` (also runnable locally) | Reproducible, no laptop needed |
| Retrieval index | EmbeddingGemma via Ollama, SQLite + `sqlite-vec` | Laptop | Must be built with the same embedding model used offline at query time |
| Training (`train/`) | Optional LoRA of Gemma, TRL + PEFT, GGUF | Vertex AI Custom Job (L4, europe-west4); notebook for Colab | CUDA stack, billed cost |
| David | Gemma (fine-tuned or base) + retrieval | Laptop (Ollama) | Offline |
| Duel service (`duel/`) | Python, FastAPI, Ollama client, `google-genai`, `sacrebleu` | Laptop | Offline |
| Presenter view + validator view | Next.js served on the laptop's LAN | Laptop | The native speaker's phone reaches it without internet |

## Source research (first task)

- Search the web for Spanish–K'iche' resources: parallel texts, bilingual dictionaries and vocabularies, phrasebooks, grammars, bilingual education and health materials, academic datasets (e.g. Hugging Face, OPUS, AmericasNLP-related corpora, ALMG, universities, NGOs, government health/education material).
- Record every candidate in `data/SOURCES.md`: URL, owner, license or terms, size, domain, orthography, publication date, status (`used`, `needs permission`, `rejected` + reason).
- Only download sources whose license or terms allow this use. Nothing behind a login or forbidden by terms. Uncertain → `needs permission`, left out.
- Tag each item's `domain`. Religious texts: tag `religious`, keep out of the test set, cap at 30% of training data.
- `data/normalize.py`: official K'iche' alphabet (ALMG), unify glottal stop characters (`'`, `’`, `ʼ`) before indexing, training or evaluating. Unit-tested.
- No synthetic K'iche' data: Gemini does not master K'iche' and would teach David its mistakes. Every record has `origin=web`.

## Retrieval or fine-tuning

- Always build the retrieval index: dictionary entries and example sentence pairs; for each input fetch the most relevant ones into David's prompt.
- Fine-tune only if there are at least 2,000 clean parallel sentence pairs outside the test set.
- `make eval` compares every available variant and writes `evals/report.md`: Gemma base, Gemma + retrieval, fine-tuned Gemma, fine-tuned + retrieval, Gemini alone, Gemini + the same retrieval. The best David variant goes on stage; the report shows all results honestly.

## Evaluation

- Test set (target ≥ 200 pairs per direction) from sources not used for training or retrieval, split by source. `status=pending_native_review` until a native speaker validates it (`make review-test` exports a CSV/validator session); rejected pairs are dropped.
- Metric: chrF++.
- `evals/human_eval.md`: blind rating template (adequacy/fluency 1–5, 50 translations per model), filled before each event.
- Report includes token fertility (tokens per word) of K'iche' vs Spanish in Gemma's tokenizer.

## Presenter and validator views

- Presenter: phrase and direction; David and Goliath side by side with translation, latency and cost; scoreboard with chrF++ (evaluation rounds) and native-speaker verdicts (live rounds); model card panel with sources, pair count and data date.
- Validator (phone over LAN, QR on the presenter view): both translations without saying which model made each; mark correct / acceptable / wrong; verdict appears on screen instantly.
- Offline: everything runs without internet; Goliath shows as offline.

## Acceptance criteria

- `data/SOURCES.md` lists every source with license and domain; nothing unlicensed in the repo.
- `make up` starts Ollama, the duel service and both views; the duel works with Wi-Fi off.
- `make eval` produces the full variant comparison in `evals/report.md`.
- `MODEL_CARD.md` documents sources, variant, known limitations and intended use.
- `make reset` clears rounds and verdicts.
- `make test` passes.

## Shared rules (all four demo repos)

These demos are teaching material for a talk. The code, folder names, reports and docs must make the talk's ideas visible. Prefer small files named after the concept they teach, and comments that explain *why*, not *what*.

### Stack

| Layer | Choice |
| --- | --- |
| Web | Next.js (App Router, TypeScript), React |
| Android | Kotlin, Jetpack Compose, Material 3 |
| Cloud models | Gemini via Vertex AI with the Google Gen AI SDK (`@google/genai` / `google-genai`), ADC, `GOOGLE_CLOUD_LOCATION=global` |
| Images | Nano Banana 2 Lite (`IMAGE_MODEL`) via Vertex AI |
| Local models | Gemma served with Ollama; EmbeddingGemma where retrieval is needed |
| Fine-tuning | LoRA with Hugging Face TRL + PEFT as a Vertex AI Custom Job (L4, `europe-west4`); same script wrapped in a Colab notebook; exported to quantized GGUF for Ollama |
| Agents | Agent Development Kit (ADK, Python); MCP for tools; A2A for agent-to-agent |
| Cloud | Google Cloud project `ai-experiments-487722`. Every web app or API runs on **Cloud Run** (`us-central1`, Dockerfile + Cloud Build + Artifact Registry repo `charlas2027`). Firebase services (Auth, Firestore named database per app, FCM, Storage, App Check) are used as SDKs, never Firebase Hosting |
| Local data | JSON/JSONL files or SQLite in the repo |

### Cloud first

Everything runs in the cloud unless the talk requires the laptop (offline model, latency measured on the stage hardware). Every component that runs on the laptop is listed in `docs/DECISIONES.md` with the reason.

### Rules

- No model name or version is hard-coded. Models come from env vars (`GEMINI_MODEL`, `GEMINI_LIVE_MODEL`, `IMAGE_MODEL`, `GEMMA_BASE_MODEL`, `LOCAL_MODEL_TAG`, `EMBEDDING_MODEL`) documented in `.env.example`.
- Preview APIs (AppFunctions with Gemini, WebMCP, UCP, AP2, A2A, MCP SDK, ADK): check the current official docs before implementing (context7 or the web) and record the version used in `docs/DECISIONES.md`.
- `Makefile` targets: `make up` (start everything needed locally), `make reset` (back to the initial state in under 10 seconds), `make test`, `make deploy`, and where it applies `make eval`, `make train`.
- Data: every record carries `origin` (`web` with URL + license, `synthetic` with model + prompt + seed, `human`). Documented in `data/SOURCES.md` and `data/DATASHEET.md`. Fictional seed data is generated by scripts. No secrets in the repo.
- Python uses `uv`. Node uses npm. Code in English; UI in Spanish (Guatemala/LatAm neutral).
- Tests must pass before a task is done (`make test`). Anything that needs the cloud also has a mock mode (`MOCK_AI=1`) so tests and rehearsals run without network.
- No `CLAUDE.md` in the repo.

### UI/UX bar

- Light theme only. No dark mode. Not overloaded: each screen shows what matters and nothing else.
- Production-grade: own brand identity (name, logo mark, palette, typography), consistent components, designed empty/loading/error states, no placeholder text.
- Web: responsive, keyboard accessible, WCAG 2.2 AA contrast, purposeful motion only. Android: Material 3 and platform conventions.
- Every app on stage has a presenter view: a separate route readable from the back of an auditorium (large type, high contrast, 16:9 at 1920×1080), no logins or manual steps during the talk.
- Visual assets (logos, product photos, sample photos) are generated with `IMAGE_MODEL` by a script in `scripts/` and committed; the prompt is kept next to the asset.

### Docs (written at the end, from the finished code)

- `README.md` (Spanish) and `README.en.md`: one screen — what it is, what you'll learn, the result, diagrams, quickstart and links. Everything else lives in `docs/` (es + en): `DECISIONES` (**technical decisions**: what, why, discarded alternatives, where each component runs and why; preview API versions), `COMANDOS` (`make` commands), `ESTRUCTURA` (repo map), `CREDITOS` (data and licenses).
- `docs/ONBOARDING.md`: prerequisites with versions, local setup, credentials/ADC, GCP setup with `infra/NN-*.sh`, run/test/rehearse, code walkthrough, troubleshooting, talk-day checklist.
- `docs/diagrams/`: made with the `diagram-design` skill, exported to SVG and PNG.
- Never describe the project as a deviation from a spec; the docs describe what the project is.
