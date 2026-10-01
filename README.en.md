# Tzij — a Spanish ↔ K'iche' translator that works without internet

[Versión en español](README.md) · [Onboarding (Spanish)](docs/ONBOARDING.md) · [Model card](MODEL_CARD.md) · [Sources](data/SOURCES.md) · [Evaluation report](evals/report.md)

Demo for the talk **"David vs. Goliath: cómo un modelo pequeño le gana a un modelo frontier"** ("David vs. Goliath: how a small model beats a frontier model").

Tzij ("word" in K'iche') translates between Spanish and K'iche' (ISO 639-3 `quc`), Guatemala's most widely spoken Mayan language. **David** is Gemma 4 E4B in Ollama on the laptop, with a retrieval index built only from licensed K'iche' data. **Goliath** is Gemini 3.8 Flash on Vertex AI, used the way anyone would use it. On stage both translate the same phrase in parallel. A native speaker votes from their phone without knowing which model wrote each translation.

**The result, unvarnished:** Goliath translates better. David scores **18.4 chrF++** and Goliath **36.4**. David wins elsewhere: it costs **$0** per translation, the data never leaves the laptop, and it **works without internet**, where Goliath produces nothing. This repo is the half of the talk about *when NOT to fine-tune* and *what retrieval buys you*: retrieval lifts Gemma more than the fine-tune does, and the fine-tune doesn't go on stage.

![Presenter view with Wi-Fi off: David translates on the laptop, Goliath shows as offline](docs/screenshots/real/presenter-06-offline.png)

*Presenter view during an evaluation round with the network cut. The reference comes from a Bloom Library book (MINEDUC, CC BY 4.0); the translations on screen are model outputs, not references.*

## What you'll learn

| Lesson | Where it lives in the code |
| --- | --- |
| **Licensed web data and orthography normalization.** Every record carries `origin=web`, a URL and a license. Sources that don't allow this use are left out. Typographic single quotes, the saltillo `ꞌ`, `ʼ` and the other characters used as a glottal stop are unified to the ASCII apostrophe before indexing, training or evaluating. | [`data/SOURCES.md`](data/SOURCES.md) (10 sources used, 13 needing permission, 24 rejected), [`pipeline/sources/`](pipeline/sources/), [`data/normalize.py`](data/normalize.py), [`tests/test_normalize.py`](tests/test_normalize.py) |
| **Split by source, not by sentence.** A source is either entirely test or entirely training, and any training pair that repeats a test sentence is dropped. A random sentence split would measure memory. | [`pipeline/split.py`](pipeline/split.py), [`pipeline/sources/__init__.py`](pipeline/sources/__init__.py), [`data/DATASHEET.md`](data/DATASHEET.md) |
| **Retrieval vs fine-tuning, decided by `make eval`.** All six variant types (base, base + retrieval, fine-tuned, fine-tuned + retrieval, Gemini, Gemini + retrieval) run on the same 600 sentences. The best local variant wins, even if it isn't the one that took the most work. | [`evals/run_eval.py`](evals/run_eval.py), [`duel/tzij_duel/variants.py`](duel/tzij_duel/variants.py), [`evals/report.md`](evals/report.md) |
| **Token fertility.** In Gemma's tokenizer a K'iche' word costs 2.68 tokens and a Spanish word 1.45. The same sentence takes **1.88×** as many tokens in K'iche'. | [`evals/fertility.py`](evals/fertility.py), [`evals/fertility.md`](evals/fertility.md) |
| **Offline by design.** Model, embeddings, index, service and views all live on the laptop. Fonts are downloaded at build time. A 0.8 s TCP probe decides whether Goliath is online before calling it. | [`duel/duel_core/connectivity.py`](duel/duel_core/connectivity.py), [`rag/embedder.py`](rag/embedder.py), [`web/next.config.ts`](web/next.config.ts), [`duel/tzij_duel/main.py`](duel/tzij_duel/main.py) |
| **Native-speaker validation.** The test set stays `pending_native_review` until a person reviews it. In live rounds a person gives the verdict from their phone, blind. A human-evaluation template is filled before each event. | [`pipeline/review.py`](pipeline/review.py), [`pipeline/apply_review.py`](pipeline/apply_review.py), [`web/app/validar/page.tsx`](web/app/validar/page.tsx), [`evals/human_eval.md`](evals/human_eval.md) |

## Architecture

![Architecture: offline laptop vs Google Cloud](docs/diagrams/architecture.png)

*The diagrams are labeled in Spanish, like the UI.*

- **On the laptop, inside the offline boundary:** the duel service (FastAPI on `:8787`) serves the API, the event stream (SSE) and both built views (`/presentador/` and `/validar/`). David runs in Ollama (`gemma4:e4b`). The index is a SQLite file with `sqlite-vec` and EmbeddingGemma vectors.
- **On the LAN:** the validator's phone opens the QR code shown on the presenter view and votes from there.
- **On Google Cloud:** Goliath (`gemini-3.8-flash` on Vertex AI, `global`) and two Cloud Run Jobs, one for the data and one for the GPU fine-tune. Their outputs land in Cloud Storage. The laptop only downloads datasets and models while preparing, never during the talk.

Diagram sources: [`docs/diagrams/`](docs/diagrams/) (HTML, SVG and PNG).

## Quickstart

Prerequisites and details are in [`docs/ONBOARDING.md`](docs/ONBOARDING.md). With Python 3.12, `uv`, Node 24, Ollama and `gcloud` installed:

```bash
cp .env.example .env                       # models, buckets and ports; .env is never committed
uv sync                                    # Python dependencies
ollama pull gemma4:e4b && ollama pull embeddinggemma
gcloud auth application-default login      # ADC for Vertex AI and Cloud Storage

make data-pull     # download the latest dataset from the bucket (or `make data` to build it here)
make index         # retrieval index with EmbeddingGemma + sqlite-vec
make web           # build the views (needs internet once, for the fonts)
make up            # Ollama + warmed-up David + service + views on the LAN
```

Open `http://127.0.0.1:8787/presentador/`. Scan the QR code with a phone. Press `E` for an evaluation phrase or `/` to type a live phrase.

To rehearse without the cloud or a GPU: `make up MOCK_AI=1`. Pass variables **after** `make`, because `.env` overrides environment variables. In mock mode David returns its best retrieved example from the licensed data and never makes up K'iche'. It still needs Ollama with `embeddinggemma` and the index.

## `make` commands

| Command | What it does |
| --- | --- |
| `make help` | Lists the commands. |
| `make data` | Runs the data pipeline locally: download, clean, normalize, dedupe, tag domains, split by source. Writes `data/processed/<version>/` and regenerates `data/DATASHEET.md`. |
| `make data-cloud` | Runs the same pipeline as a Cloud Run Job (`infra/10-data-job.sh`) and writes a versioned dataset to `gs://…-tzij-data/datasets/`. |
| `make data-pull` | Downloads the latest dataset the job produced. |
| `make index` | Builds `rag/index/tzij.sqlite` from the `train` split only, with EmbeddingGemma via Ollama. |
| `make review-test` | Exports the test set to `data/review/test_review_<version>.csv` for native review. |
| `make apply-review REVIEW_CSV=…` | Applies the verdicts (`ok` / `fix` / `reject`) to the test set. |
| `make fertility` | Measures K'iche' vs Spanish token fertility and writes `evals/fertility.md`. |
| `make datasheet` | Regenerates `data/DATASHEET.md` from the latest manifest. |
| `make eval [EVAL_ARGS=…]` | Compares every available variant and writes `evals/report.md`. |
| `make human-eval-sheet` | Builds a blind human-evaluation sheet (50 sentences) from the latest eval run. |
| `make train-data` | Renders the `train` sentences as chat JSONL (`data/train/chat.jsonl`). |
| `make train TAG=tzij-YYYY-MM [TRAIN_ARGS=…]` | LoRA fine-tune as a Cloud Run Job on one L4. Records duration and cost in `train/runs/<tag>.json`. |
| `make train-local TAG=…` | The same training on the Mac (MPS), for when no cloud GPU is available. |
| `make train-finish TAG=…` | Merges a cloud-trained adapter and converts it to GGUF on the Mac, then publishes it to the models bucket. |
| `make pull-model TAG=…` | Downloads the GGUF from the bucket and registers it in Ollama. |
| `make web` | Builds the presenter and validator views (static export). |
| `make duel` | Runs only the duel service on `0.0.0.0:$DUEL_PORT`. |
| `make up` | Starts Ollama if needed, warms David and EmbeddingGemma, builds the views if missing and serves everything on the LAN. |
| `make reset` | Clears rounds and verdicts, whether the service is running or not, in under 10 s. |
| `make test` | Python tests (`MOCK_AI=1`, no network) and web tests (vitest). |
| `make emulator` | Opens the validator in Chrome on the Android emulator (`10.0.2.2`) and fails if a vote takes more than 1 s to reach the screen. |
| `make screenshots` | Playwright screenshots of both views at 1920×1080 and 390×844 (the service must be running). |

There is no `make deploy`. Nothing in this project is served from the cloud: what runs in the cloud are the two jobs (`make data-cloud`, `make train`).

## Repo map

```
data/          normalize.py (orthography), SOURCES.md, DATASHEET.md (generated)
pipeline/      run.py → sources/ (one per source) → clean.py → split.py → manifest/datasheet
               review.py / apply_review.py (native review), train_set.py (chat JSONL)
               Dockerfile + cloudbuild.yaml (image for the data Cloud Run Job)
rag/           embedder.py (EmbeddingGemma via Ollama), store.py (sqlite-vec),
               build_index.py, retrieve.py (examples + glossary)
duel/
  duel_core/   Ollama and Gemini clients, parallel duel, chrF++, cost, connectivity
  tzij_duel/   FastAPI service: variants.py, prompts.py, deck.py, rounds.py, model_card.py, lan.py
evals/         run_eval.py → report.md, fertility.py → fertility.md, human_eval.md
train/         train_lora.py (TRL + PEFT → merge → GGUF), submit_job.py (Cloud Run Job),
               finish_local.py, train_local.py, pull_model.sh, colab.ipynb, runs/
infra/         env.sh, 01-train-service-account.sh, 02-train-image.sh, 03-train-job.sh, 10-data-job.sh
web/           Next.js: app/presentador, app/validar, components/, lib/, tests/
tests/         pipeline, normalization, retrieval and fertility tests
docs/          ONBOARDING.md, diagrams/, screenshots/
MODEL_CARD.md  what David is, its data, results and limits
```

Generated files that are not committed: `data/raw/`, `data/processed/`, `data/review/`, `data/train/`, `rag/index/`, `evals/runs/`, `models/`, `web/out/`.

## Technical decisions

### What runs on the laptop, and why

| Component | Where | Why |
| --- | --- | --- |
| David (`gemma4:e4b` in Ollama) | Laptop | The talk is about a model that serves a community without connectivity. If David needed internet, there would be no story. |
| Retrieval index (EmbeddingGemma + `sqlite-vec`) | Laptop | Queries run on stage with no network, so the index has to be built with the same embedding model that answers offline. The model name is stored inside the index and checked on every query (`rag/retrieve.py`). |
| Duel service (FastAPI) | Laptop | Calls David and Goliath in parallel, measures latency and cost, and stores rounds and verdicts in a JSON file. If the network drops, Goliath shows "sin conexión" (offline) and David carries on. |
| Presenter and validator views (Next.js, static export) | Laptop, served by the same process | One origin on the LAN: the phone only needs the laptop's IP. Fonts are downloaded at build time (`next/font`), so the page requests nothing from the internet. |
| Goliath (`gemini-3.8-flash`) | Vertex AI, `global` | The frontier model as people use it, with no extra data. It needs internet on purpose. |
| Data pipeline | Cloud Run Job (`us-central1`) | It downloads about 1.5 GB (the Wiktionary dump is streamed and filtered), it has to be reproducible, and it shouldn't depend on the presenter's laptop. It keeps the raw cache and versioned datasets in `gs://…-tzij-data`. `make data` runs the same code locally. |
| LoRA fine-tune | Cloud Run Job with 1× NVIDIA L4 (`europe-west4`) | Serverless, billed per second, nothing left running between retrains, and the same container idea as the pipeline. `TRAIN_RUNTIME=vertex` submits the same container as a Vertex AI Custom Job, and `train/colab.ipynb` wraps the same script for Colab Enterprise. |
| E4B merge and GGUF | Laptop (`make train-finish`) | See below. |

**The validator on the LAN.** The phone opens `http://<laptop IP>:8787/validar/` (the QR code works it out in `duel/tzij_duel/lan.py`, or you can pin it with `PUBLIC_URL`). It receives both translations in random order, with no name, latency or cost, and its vote shows up on the presenter view over SSE. On the Android emulator the laptop is `10.0.2.2`. `make emulator` checks that the vote arrives in under 1 s.

### Why the E4B merge/GGUF finishes on the laptop

A Cloud Run GPU job has at most **32 GiB** of memory, and its filesystem lives in that same memory. Training E4B fits: the LoRA adapter is saved to a Cloud Storage volume. What doesn't fit is saving the 16 GB merged checkpoint and converting it to GGUF. The `tzij-2026-09` run trained 324 steps in 1,316 s (22 min). Then it ran out of memory while saving the merged model (`train/runs/tzij-2026-09.json`, ~30 min of job time, ~$0.70 estimated). `make train-finish` downloads the adapter, merges it and converts it to GGUF Q4_K_M on the laptop with the same functions `train_lora.py` uses, then publishes the result to the models bucket. `make pull-model` doesn't care where the merge happened. A first run at 1.5 epochs was cancelled because, at ~4 s per step, it would not finish within Cloud Run's 1 h limit for a GPU task (`train/runs/failed/`).

### BOUQuET: evaluation only, kept out of git

BOUQuET (Meta) is a multi-domain benchmark with human Spanish → K'iche' translations. It is gated on Hugging Face: you have to accept the terms, and the token lives in Secret Manager as `hf-token`. The terms allow **evaluation only** and private redistribution. So:

- it has the `test` role and never enters training or the index;
- its raw and processed data are gitignored and only exist in the private bucket;
- on-stage evaluation rounds exclude it (`duel/tzij_duel/deck.py`), so its sentences are never projected. `make eval` does use it, along with the Bloom books.

### The 30% cap on religious text

The Totonicapán New Testament contributes about 8,000 verses, far more than all the everyday sentences combined. Without a cap, David would translate "¿Dónde está el mercado?" ("Where is the market?") in the voice of a gospel. `pipeline/split.py` caps religious text at 30% of training sentences. It picks the verses with a stable hash, so the selection is reproducible and spread out, and it never puts religious text in the test set. `pipeline/train_set.py` checks the cap again before fine-tuning. In the current dataset the share is exactly 30.0%.

### No synthetic K'iche'

Gemini does not master K'iche'. If it generated training data, it would teach David its own mistakes. Every record is `origin=web`, with a URL and a license. The sources that pair Spanish and K'iche' through English (Pontoon, GATITOS) are independent human translations, with no machine translation involved. Even mock mode (`MOCK_AI=1`) answers with text from the licensed data, never with made-up K'iche'. `HuggingFaceFW/finetranslations` was rejected because it is machine translation.

### EmbeddingGemma + `sqlite-vec`

- **Why:** they run locally and offline, in a single SQLite file that can be copied and is versioned per dataset. EmbeddingGemma is served by the same Ollama as David. It uses the task prefix `task: sentence similarity | query: ` because it compares input sentences with source sentences in the same language.
- **How:** two lookups per query. **Examples** are the nearest sentence pairs by embedding, filtered by direction. The **glossary** first looks for exact matches of the whole input, its bigrams and its single words, because embeddings are weak on isolated words; then it fills up with the nearest dictionary entries by embedding. David gets `RAG_K=6` of each kind. An on-disk embedding cache (`rag/.cache/`) makes rebuilding cheap.
- **Rejected:** a cloud embedding API. It wouldn't work with the network cut, and the index has to be built with the same model that queries it.

### Other decisions

- **chrF++, not BLEU.** It gives partial credit for character n-grams in an agglutinative language with lots of spelling variation. It is computed at corpus level on normalized text, with the same apostrophe for everyone.
- **Same instructions for every model** (`tzij-translate-v1`). Only the context block changes, so the comparison measures data, not prompting.
- **David's latency includes retrieval**, because the audience waits for it too.
- **`OLLAMA_NUM_CTX=4096`.** The 128k default reserves a huge KV cache and evicts EmbeddingGemma on every request.

## Results

`make eval`, run `full-20260930`, dataset `20260930-220035`. That's 600 test sentences (150 per source and direction, from Bloom and BOUQuET) that are never in the index. References are still `pending_native_review`, so the numbers are provisional.

| Variant | Where | Retrieval | es → quc | quc → es | Both | p50 | Cost / 1,000 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 E2B (`gemma4:e2b-it-qat`) | laptop | no | 8.4 | 11.4 | 9.8 | 0.85 s | $0 |
| Gemma 4 E2B | laptop | yes | 15.1 | 15.9 | 15.4 | 0.84 s | $0 |
| Gemma 4 E4B (`gemma4:e4b`) | laptop | no | 7.4 | 16.3 | 11.5 | 1.20 s | $0 |
| **Gemma 4 E4B — David on stage** | laptop | yes | 18.0 | 18.9 | **18.4** | 1.73 s | $0 |
| `tzij-2026-09` (LoRA on E4B, 1 epoch) | laptop | no | 13.8 | 16.8 | 15.2 | 1.07 s | $0 |
| `tzij-2026-09` | laptop | yes | 17.5 | 17.8 | 17.6 | 1.75 s | $0 |
| **Gemini 3.8 Flash — Goliath** | cloud | no | 32.8 | 40.4 | **36.4** | 1.83 s | $0.26 |
| Gemini 3.8 Flash | cloud | yes | 34.3 | 40.4 | 37.2 | 2.29 s | $1.00 |

![chrF++ per variant](docs/diagrams/results.png)

**The honest takeaway:**

- **Goliath is the better translator.** David trails by 18 points overall and in every slice (length, direction, domain). It beats Goliath on 45 of 598 sentences (8%) and comes within 5 points on 110 (18%).
- **Retrieval is what moves David.** With about 7,000 dictionary entries and example pairs per direction, E4B goes from 11.5 to 18.4 (+60%) and E2B from 9.8 to 15.4. In Spanish → K'iche', the direction a model can't fake, E4B **more than doubles** its score (7.4 → 18.0).
- **Fine-tuning helped less than retrieval.** One LoRA epoch on 2,590 sentence pairs lifts E4B from 11.5 to 15.2 (+3.7), against +6.9 for retrieval. Combined with retrieval it lands 0.8 points *below* E4B + retrieval. It does better on short phrases (13.9 vs 11.2) and worse on long sentences. With fewer than 2,000 non-religious pairs, retrieval is the better investment: the fine-tune stays in the report, not on stage. The dataset does clear the fine-tuning threshold (2,701 clean sentence pairs outside the test set, minimum 2,000). Allowed doesn't mean worth it.
- **Where David wins outright:** cost ($0 vs $0.26 per 1,000 translations, and Gemini's list price doubles from January 1, 2027), privacy (nothing leaves the laptop) and availability. Without internet Goliath produces nothing, and David's numbers don't change.
- Gemini with the same retrieval improves only a little (36.4 → 37.2) and costs almost 4× as much because of the longer prompt.

Breakdowns by source, length, domain and failures are in [`evals/report.md`](evals/report.md). Token fertility is in [`evals/fertility.md`](evals/fertility.md). Data and limitations are in [`MODEL_CARD.md`](MODEL_CARD.md).

## Versions

None of the preview APIs this talk series tracks (AppFunctions, WebMCP, UCP, AP2, A2A, MCP SDK, ADK) is used in this repo. Versions verified on September 30, 2026:

| Piece | Version |
| --- | --- |
| Goliath | `gemini-3.8-flash`, Vertex AI `global`, `thinking_level=low`, `google-genai` SDK 2.25.0 |
| David | `gemma4:e4b` on Ollama 0.35.0 |
| Other `make eval` variants | `gemma4:e2b-it-qat`, `tzij-2026-09` (LoRA on `google/gemma-4-E4B-it`, GGUF Q4_K_M) |
| Embeddings | `embeddinggemma` on Ollama |
| Python | 3.12 with uv 0.8.22: FastAPI 0.142.2, uvicorn 0.54.0, sacrebleu 2.6.0, sqlite-vec 0.1.9, tokenizers 0.23.2, huggingface-hub 1.33.0, google-cloud-storage 3.15.1, pytest 9.1.1 |
| Web | Node 24.21.0, npm 12.0.2, Next.js 16.3.8, React 19.3.0, TypeScript 5.9.3, vitest 3.2.7, Playwright 1.63.0 |
| Training image | torch 2.14.0 (CUDA 12.6), transformers 5.17.0, peft 0.21.1, trl 1.14.1, accelerate 1.15.0, datasets 5.0.1, llama.cpp `b11292` |
| Google Cloud SDK | 587.0.0 |

No model name is hard-coded: every model comes from `.env` (`GEMINI_MODEL`, `LOCAL_MODEL_TAG`, `BASE_MODEL_TAGS`, `FINETUNED_MODEL_TAGS`, `GEMMA_BASE_MODEL`, `EMBEDDING_MODEL`).

## Data: licenses and attribution

Every source, with owner, license, size, domain, orthography and status, is listed in [`data/SOURCES.md`](data/SOURCES.md). Per-source counts and drop reasons are in [`data/DATASHEET.md`](data/DATASHEET.md). Raw data is never committed: some licenses allow use but not redistribution.

| Source | Owner | License | Use |
| --- | --- | --- | --- |
| [Bloom Library K'iche' books](https://bloomlibrary.org/language:quc) (CC BY only) | Mostly Ministerio de Educación de Guatemala / USAID, via SIL Bloom Library | CC BY 4.0 per book; NC/ND books excluded | Test |
| [BOUQuET](https://huggingface.co/datasets/facebook/bouquet) | Meta FAIR and community translators | CC BY 4.0, gated; terms: evaluation only, private redistribution | Test (evaluation only) |
| [UD K'iche'-IU](https://github.com/UniversalDependencies/UD_Kiche-IU) | F. Tyers, R. Henderson (Indiana University) | CC BY-SA 4.0; sentences used with permission of the Academia de Lenguas Mayas de Guatemala and Telma Can Pixabaj | Training / index |
| [COERLL K'iche' course](https://tzij.coerll.utexas.edu/) | COERLL / LLILAS / AILLA, UT Austin | CC BY 4.0 | Training / index |
| [Universal Declaration of Human Rights](https://github.com/eric-muller/udhr) | OHCHR; XML from the UDHR in Unicode project | Free reproduction citing OHCHR as the source | Training / index |
| [Mozilla Pontoon](https://huggingface.co/datasets/ayymen/Pontoon-Translations) | Mozilla localization community; packaged by ayymen | MPL-2.0 | Training / index |
| [New Testament, K'iche' of Totonicapán](https://ebible.org/quctt/) + Biblia Libre para el Mundo | Pioneer Bible Translators (quc); BLM (es) | quc: CC BY 4.0 (© 2022 Pioneer Bible Translators); es: public domain | Training (max 30%) |
| [GATITOS](https://huggingface.co/datasets/google/smol) | Google Research (SMOL/GATITOS) | CC BY 4.0 | Lexicon |
| [PanLex](https://panlex.org/) | PanLex / Long Now Foundation; packaged by cointegrated | CC0 1.0 | Lexicon |
| [Spanish Wiktionary](https://es.wiktionary.org/) via [kaikki.org](https://kaikki.org/eswiktionary/) | Wiktionary contributors | CC BY-SA 4.0 | Lexicon |

Sources that require prior authorization (ALMG publications beyond the permitted examples, PLFM, SIL dictionaries, among others) are marked *needs permission* and are not used. K'iche' data belongs to its speakers and their institutions.
