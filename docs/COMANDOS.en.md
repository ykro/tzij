# Commands

The step-by-step setup and every `Makefile` command. `make help` lists them with their description. Back to the [README](../README.en.md). [Versión en español](COMANDOS.md).

## Step-by-step setup

Prerequisites and details are in [ONBOARDING.md](ONBOARDING.md) (Spanish). With Python 3.12, `uv`, Node 24, Ollama and `gcloud` installed:

```bash
cp .env.example .env                       # models, buckets and ports; .env is never committed
uv sync                                    # Python dependencies
ollama pull gemma4:e4b && ollama pull embeddinggemma
gcloud auth application-default login      # ADC for Vertex AI and Cloud Storage

make data-pull     # download the latest dataset from the bucket (or `make data` to build it here)
make index         # retrieval index with EmbeddingGemma + sqlite-vec + FTS5
make pull-model TAG=tzij-2026-10-raft-bt-s3   # the fine-tuned David (or LOCAL_MODEL_TAG=gemma4:e4b)
make web           # build the views (needs internet once, for the fonts)
make up            # Ollama + warmed-up David + service + views on the LAN
```

Open `http://127.0.0.1:8787/presentador/`. Scan the QR code with a phone. Press `E` for an evaluation phrase or `/` to type a live phrase.

To rehearse without the cloud or a GPU: `make up MOCK_AI=1`. Pass variables **after** `make`, because `.env` overrides environment variables. In mock mode David returns its best retrieved example from the licensed data and never makes up K'iche'. It still needs Ollama with `embeddinggemma` and the index.

## Every command

| Command | What it does |
| --- | --- |
| `make help` | Lists the commands. |
| `make data` | Runs the data pipeline locally: download, clean, normalize, dedupe, tag domains, split by source. Writes `data/processed/<version>/` and regenerates `data/DATASHEET.md`. |
| `make data-cloud` | Runs the same pipeline as a Cloud Run Job (`infra/10-data-job.sh`) and writes a versioned dataset to `gs://…-tzij-data/datasets/`. |
| `make data-pull` | Downloads the latest dataset the job produced. |
| `make index` | Builds `rag/index/tzij.sqlite` from the `train` split only, with EmbeddingGemma via Ollama. |
| `make review-test` | (Optional) Exports the test set to `data/review/test_review_<version>.csv` for a native review. |
| `make apply-review REVIEW_CSV=…` | Applies the verdicts (`ok` / `fix` / `reject`) to the test set. |
| `make fertility` | Measures K'iche' vs Spanish token fertility and writes `evals/fertility.md`. |
| `make datasheet` | Regenerates `data/DATASHEET.md` from the latest manifest. |
| `make tune-retrieval` | Tunes retrieval (mode, k, order, fuzzy glossary) on the dev split only and writes `evals/tuning.md`. |
| `make eval [EVAL_ARGS=…]` | Compares every available variant and writes `evals/report.md`. |
| `make human-eval-sheet` | Builds a blind human-evaluation sheet (50 sentences) from the latest eval run; `VARIANTS="gemma4:e4b+rag,gemini-3.8-flash"` picks variants. |
| `make train-data` | Renders the `train` sentences as chat JSONL (`data/train/chat.jsonl`). |
| `make train-data-raft` | Like `train-data`, but with retrieved context in every prompt, excluding the pair itself (RAFT): `data/train/chat-raft.jsonl`. |
| `make monolingual` | Licensed monolingual K'iche', from training-side sources only: `data/monolingual/quc.jsonl`. |
| `make back-translate` | Gemini translates that K'iche' into Spanish once and records the cost: `data/train/back_translated_gemini.jsonl`. |
| `make train-data-raft-bt` | RAFT data + back-translated pairs (Spanish → K'iche' only): `data/train/chat-raft-bt.jsonl`. |
| `make train TAG=tzij-YYYY-MM [TRAIN_ARGS=…]` | LoRA fine-tune as a Cloud Run Job on one L4. Records duration and cost in `train/runs/<tag>.json`. |
| `make train-local TAG=…` | The same training on the Mac (MPS), for when no cloud GPU is available. |
| `make train-finish TAG=…` | Merges a cloud-trained adapter and converts it to GGUF on the Mac, then publishes it to the models bucket. |
| `make pull-model TAG=…` | Downloads the GGUF from the bucket and registers it in Ollama. |
| `make web` | Builds the presenter and validator views (static export). |
| `make duel` | Runs only the duel service on `0.0.0.0:$DUEL_PORT`. |
| `make up` | (`MOCK_AI=1 make up`: no Ollama, index or dataset needed.) Starts Ollama if needed, warms David and EmbeddingGemma, builds the views if missing and serves everything on the LAN. |
| `make reset` | Clears rounds and verdicts, whether the service is running or not, in under 10 s. |
| `make test` | Python tests (`MOCK_AI=1`, no network) and web tests (vitest). |
| `make deploy` | Deploys the cloud parts (project, data job, training job and image). The duel and views stay on the laptop. |
| `make emulator` | Opens the validator in Chrome on the Android emulator (`10.0.2.2`) and fails if a vote takes more than 1 s to reach the screen. |
| `make screenshots` | Playwright screenshots of both views at 1920×1080 and 390×844 (the service must be running). |
| `make niche RUN=niche DAVID=<variant>` | David vs Goliath on the niche (held-out Pontoon product, translation memory): `evals/niche_results.md`. |
| `make synthetic` | Gemini synthetic pairs, anchored to the dictionary and UD, round-trip filtered: `data/train/synthetic/`. They are not used for training ([logbook, section 7](BITACORA.md), Spanish). |
| `make train-data-raft-bt-syn` | RAFT + back-translation + synthetic pairs capped at `SYN`: `data/train/chat-raft-bt-syn<N>.jsonl`. |
| `make llama-server` | llama.cpp server for the `@llama` eval variants (logit bias, 8 parallel slots) on the GGUF of `LLAMA_SERVER_MODEL` from Ollama. |
| `make demo-screens` | Screenshots for [DEMO.md](DEMO.md) (Spanish), driven with the stage keys (needs `make up` with the stage variant; `EMULATOR=0` skips the phone). |

`make deploy` deploys only what lives in the cloud: project setup (APIs, Artifact Registry, buckets, `hf-token` secret) via `infra/00-project.sh`, the data Cloud Run Job, and the training job with its image. **The duel service and the views are not deployed, on purpose:** they run on the laptop because the talk is about what works without internet.
