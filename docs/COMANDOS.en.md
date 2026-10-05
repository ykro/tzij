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
make niche-data    # build the index (EmbeddingGemma + sqlite-vec + FTS5); the dataset already has the specialty round
make pull-model TAG=tzij-2026-10-mix-s7   # the fine-tuned David (or LOCAL_MODEL_TAG=gemma4:e4b)
make web           # build the views (needs internet once, for the fonts)
make up            # Ollama + warmed-up David + service + views on the LAN
```

Open `http://127.0.0.1:8787/presentador/`. Scan the QR code with a phone. Press `E` for an evaluation phrase or `/` to type a live phrase.

To rehearse without the cloud or a GPU: `make up MOCK_AI=1` (or `MOCK_AI=1 make up`: anything on the command line or in the environment wins over `.env`). In mock mode David returns its best retrieved example from a small index of licensed pairs (`mock_data/`, hashing embeddings) and never makes up K'iche'. It needs no Ollama, index or dataset.

## Talk day

```bash
make up                                          # terminal 1: keeps running
make stage-on && make warmup && make preflight   # terminal 2: models loaded, everything [ok]
make reset                                       # scoreboard to zero
# … the talk …
make stage-off                                   # same as the other repos (nothing in the cloud here)
```

## Every command

| Command | What it does |
| --- | --- |
| `make help` | Lists the commands. |
| `make data` | Runs the data pipeline locally: download, clean, normalize, dedupe, tag domains, split by source. Writes `data/processed/<version>/` and regenerates `data/DATASHEET.md`. |
| `make data-cloud` | Runs the same pipeline as a Cloud Run Job (`infra/10-data-job.sh`) and writes a versioned dataset to `gs://…-tzij-data/datasets/`. |
| `make data-pull` | Downloads the latest dataset the job produced. |
| `make index` | Builds `rag/index/tzij.sqlite` from the `train` split only, with EmbeddingGemma via Ollama. |
| `make niche-data` | Builds the index. If `LATEST` has no `test_niche.jsonl` (a new dataset from `make data` or `make data-cloud`), it first holds Firefox Focus out of the base dataset `20261002-022500` as `test_niche.jsonl` and removes it from train (`python -m pipeline.niche build`). The published dataset, `20261002-173447`, already has it. |
| `make review-test` | (Optional) Exports the test set to `data/review/test_review_<version>.csv` for a native review. |
| `make apply-review REVIEW_CSV=…` | Applies the verdicts (`ok` / `fix` / `reject`) to the test set. |
| `make fertility` | Measures K'iche' vs Spanish token fertility and writes `evals/fertility.md`. |
| `make datasheet` | Regenerates `data/DATASHEET.md` from the latest manifest. |
| `make tune-retrieval` | Tunes retrieval (mode, k, order, fuzzy glossary) on the dev split only and writes `evals/tuning.md`. |
| `make eval [EVAL_ARGS=…]` | Compares every available variant and writes `evals/report.md`. With `EVAL_ARGS="--split dev_domain --out evals/dev_domain_report.md"` it measures on the `dev_domain` split (BOUQuET paragraphs and Bloom pages outside the test sample), where decisions between runs are made. |
| `make human-eval-sheet` | Builds a blind human-evaluation sheet (50 sentences) from the latest eval run; `VARIANTS="tzij-2026-10-mix-s7+hybrid+mbr4,gemini-3.8-flash"` picks variants. |
| `make train-data` | The stage David's data: RAFT (retrieved context in every prompt, without the pair itself), back-translation in both directions, the first 2,409 distilled pairs and 30% of the web pairs: `data/train/chat-raft-bt-both-dst2409-new30.jsonl` (the default `TRAIN_DATA`). |
| `make train-data-raft` | Only the `train` pairs, RAFT: `data/train/chat-raft.jsonl`. |
| `make monolingual` | Licensed monolingual K'iche', from training-side sources only (including the K'iche'-only Bloom books): `data/monolingual/quc.jsonl`. |
| `make back-translate` | Gemini translates that K'iche' into Spanish once and records the cost: `data/train/back_translated_gemini.jsonl`. |
| `make train-data-raft-bt` | RAFT data + back-translated pairs (Spanish → K'iche' only): `data/train/chat-raft-bt.jsonl`. |
| `make train TAG=tzij-YYYY-MM [TRAIN_ARGS=…]` | LoRA fine-tune of `TRAIN_DATA` (by default, the `make train-data` output) as a Cloud Run Job on one L4. Records duration and cost in `train/runs/<tag>.json`. The stage David's chunked recipe is `train/chain.sh` ([ONBOARDING, section 6.4](ONBOARDING.md), Spanish). |
| `make train-local TAG=…` | The same training of `TRAIN_DATA` on the Mac (MPS), for when no cloud GPU is available. |
| `make train-finish TAG=…` | Merges a cloud-trained adapter and converts it to GGUF on the Mac, then publishes it to the models bucket. |
| `make pull-model TAG=…` | Downloads the GGUF from the bucket and registers it in Ollama. |
| `make web` | Builds the presenter and validator views (static export). |
| `make duel` | Runs only the duel service on `0.0.0.0:$DUEL_PORT`. |
| `make up` | (`MOCK_AI=1 make up`: no Ollama, index or dataset needed.) Starts Ollama if needed, warms David and EmbeddingGemma, builds the views if missing and serves everything on the LAN. |
| `make reset` | Clears rounds and verdicts, whether the service is running or not, in under 10 s. |
| `make stage-on` / `make stage-off` | Do nothing in the cloud: Tzij has no services to scale (everything on stage runs on the laptop). They exist so the talk-day sequence is the same in every repo. |
| `make warmup` | Loads David (with the rounds' `num_ctx`) and EmbeddingGemma in Ollama, and makes one David translation with retrieval (+ MBR when `MBR_ON_STAGE=1`) and one Goliath call, as on stage; a call that fails with an error (a timeout, a 5xx) is retried up to 3 times. Nothing is recorded on the scoreboard. |
| `make preflight` | Pre-stage check: Ollama with `LOCAL_MODEL_TAG` and the embedding model; David never trained on Firefox Focus; the index exists and comes from the `LATEST` dataset; phrases for the evaluation and specialty (`test_niche`) rounds; the duel's `/api/health` if it is running; Gemini (one tiny call); 10 GB free disk; and the median of 3 timed David translations within the 5 s p50 budget. One `[ok]` or `[FALLA]` line per check, with the fix; the exit code is the number of failures. |
| `make test` | Python tests (`MOCK_AI=1`, no network) and web tests (vitest). |
| `make deploy` | Deploys the cloud parts (project, data job, training job and image). The duel and views stay on the laptop. |
| `make emulator` | Opens the validator in Chrome on the Android emulator (`10.0.2.2`) and fails if a vote takes more than 1 s to reach the screen. |
| `make screenshots` | Playwright screenshots of both views at 1920×1080 and 390×844 (the service must be running). |
| `make niche RUN=niche DAVID=<variant>` | David vs Goliath on the niche (held-out Pontoon product, translation memory): `evals/niche_results.md`. |
| `make distill [LIMIT=N]` | Distillation in the test's domains: Gemini writes everyday Spanish and translates it into K'iche' with David's retrieved context; only pairs that pass the ALMG alphabet, length and round-trip filters are kept. Writes `data/train/distilled/` (rejections in `rejected.jsonl`, so they are never paid for twice). Training only ([logbook, section 11](BITACORA.md), Spanish). |
| `make demo-screens` | Screenshots for [DEMO.md](DEMO.md) (Spanish), driven with the stage keys (needs `make up` with the stage variant; `EMULATOR=0` skips the phone). |

`make deploy` deploys only what lives in the cloud: project setup (APIs, Artifact Registry, buckets, `hf-token` secret) via `infra/00-project.sh`, the data Cloud Run Job, and the training job with its image. **The duel service and the views are not deployed, on purpose:** they run on the laptop because the talk is about what works without internet.
