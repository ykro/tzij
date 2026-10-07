# Commands

Everything runs on Google Cloud; the `make` commands deploy, train and measure. `make help` lists them with their description. Back to the [README](../README.en.md). [Versión en español](COMANDOS.md).

## The demo

Nothing to run on talk day: the page is on Cloud Run. `make page-url` prints its address. Open it a few minutes before: it wakes David up and says «David listo» when he can translate. The script is in [DEMO.en.md](DEMO.en.md).

## Deploy

Requirements and details in [ONBOARDING.md](ONBOARDING.md) (Spanish). With Python 3.12, `uv`, Node 24 and `gcloud` installed:

```bash
cp .env.example .env                       # models, buckets and regions; .env is never committed
uv sync                                    # Python dependencies
gcloud auth login && gcloud auth application-default login
make deploy                                # project, data and training jobs, David (GPU) and the page
make page-url                              # the page's public address
```

No model is downloaded to the laptop: David's GGUF and EmbeddingGemma travel from the bucket into David's image in Cloud Build.

## Measuring against the cloud David

`make eval`, `make tune-retrieval`, `make niche` and `make index` talk to Ollama at `OLLAMA_URL`. To point them at the cloud David, first open an authenticated tunnel and leave it running:

```bash
make david-proxy          # terminal 1: tzij-david's Ollama at http://127.0.0.1:11435
make data-pull            # terminal 2: the cloud dataset (data, not models)
make eval                 # evals/report.md
```

## All commands

| Command | What it does |
| --- | --- |
| `make help` | Lists the commands. |
| `make deploy` | Everything in the cloud: project setup (APIs, Artifact Registry, buckets, `hf-token` secret, `infra/00-project.sh`), the data Cloud Run Job, the training job with its image, David's GPU service (`infra/20-david.sh`) and the page (`infra/21-page.sh`). |
| `make deploy-david` | Rebuilds and deploys David's service: an image with Ollama, `LOCAL_MODEL_TAG` (from the models bucket), EmbeddingGemma, the index of the `LATEST` dataset (from the data bucket) and the code; runs it once in a Cloud Run Job with an L4 so CUDA compiles its kernels, and deploys the image with them (about 30 minutes in all). After a new model or index. `MODEL_TAG=…` deploys another published model. |
| `make deploy-page` | Rebuilds and deploys the page (`web/` and its service). |
| `make page-url` | Prints the page's public address. |
| `make david-proxy` | Opens the cloud David's Ollama at `127.0.0.1:11435` (`DAVID_PROXY_PORT`; it doesn't clash with an Ollama installed on the laptop, which uses 11434) with your `gcloud` account (`gcloud run services proxy`). Used by the measurements and `make index`. |
| `make examples` | Re-checks the page's example sentences (`duel/examples.json`) against the cloud David and Goliath: each one is translated 3 times by both; it stays if every time David scores chrF++ ≥ 50 against the correct translation and at least 15 points above Goliath. `IDS=…` tries other `test_niche` sentences and keeps the ones that pass. |
| `make screens` | Screenshots of the live page for [DEMO.en.md](DEMO.en.md), at 1920×1080 (projector), 1280×800, 768×1024 (tablet), 414×896 and 375×812 (phones): David waking up, the page ready, an example and a typed sentence. Fails if a column doesn't fill or the page is wider than the screen. |
| `make data` | Runs the data pipeline locally: download, clean, normalize, deduplicate, tag domains, split by source. Writes `data/processed/<version>/` and regenerates `data/DATASHEET.md`. |
| `make data-cloud` | Runs the same pipeline as a Cloud Run Job (`infra/10-data-job.sh`) and writes a versioned dataset to `gs://…-tzij-data/datasets/`. |
| `make data-pull` | Downloads the latest dataset the job produced. |
| `make index` | Builds `rag/index/tzij.sqlite` from the `train` split only, with the cloud David's EmbeddingGemma (`make david-proxy`), and publishes it to `gs://…-tzij-data/index/<dataset>/`. David uses it after `make deploy-david`. |
| `make niche-data` | Builds the index. If `LATEST` has no `test_niche.jsonl` (a new dataset from `make data` or `make data-cloud`), it first holds Firefox Focus out of the base dataset `20261002-022500` as `test_niche.jsonl` and removes it from train (`python -m pipeline.niche build`). The published dataset, `20261002-173447`, already has it. |
| `make review-test` | (Optional) Exports the test set to `data/review/test_review_<version>.csv` for a native review. |
| `make apply-review REVIEW_CSV=…` | Applies the review decisions (`ok` / `fix` / `reject`) to the test set. |
| `make fertility` | Measures K'iche' vs Spanish token fertility and writes `evals/fertility.md`. |
| `make datasheet` | Regenerates `data/DATASHEET.md` from the latest manifest. |
| `make tune-retrieval` | Tunes retrieval (mode, k, order, fuzzy glossary) on the dev split only and writes `evals/tuning.md`. |
| `make eval [EVAL_ARGS=…]` | Compares the available variants and writes `evals/report.md`. With `EVAL_ARGS="--split dev_domain --out evals/dev_domain_report.md"` it measures on the `dev_domain` split (BOUQuET paragraphs and Bloom pages outside the test sample), where decisions between runs are made. |
| `make niche RUN=niche DAVID=<variant>` | David vs Goliath on the niche (a held-out Pontoon product, translation memory): `evals/niche_results.md`. |
| `make human-eval-sheet` | Blind human evaluation sheet (50 sentences) from the latest run; `VARIANTS="tzij-2026-10-mix-s7+hybrid+mbr4,gemini-3.8-flash"` picks variants. |
| `make train-data` | The page David's data: RAFT (retrieved context in every prompt, without the pair itself), back-translation both ways, the first 2,409 distilled pairs and 30 % of the web pairs: `data/train/chat-raft-bt-both-dst2409-new30.jsonl` (the default `TRAIN_DATA`). |
| `make train-data-raft` | Only the `train` pairs in RAFT: `data/train/chat-raft.jsonl`. |
| `make monolingual` | Licensed monolingual K'iche', training sources only (includes the K'iche'-only Bloom books): `data/monolingual/quc.jsonl`. |
| `make back-translate` | Gemini translates that K'iche' into Spanish once and records the cost: `data/train/back_translated_gemini.jsonl`. |
| `make train-data-raft-bt` | RAFT data + back-translated pairs (Spanish → K'iche' only): `data/train/chat-raft-bt.jsonl`. |
| `make distill [LIMIT=N]` | Distillation in the test's domains: Gemini writes everyday Spanish and translates it into K'iche' with David's retrieved context; only pairs that pass the ALMG alphabet, length and round-trip checks stay. Writes `data/train/distilled/` (rejects in `rejected.jsonl`, so they're never paid twice). Training only ([logbook, section 11](BITACORA.md), Spanish). |
| `make train TAG=tzij-YYYY-MM [TRAIN_ARGS=…]` | LoRA fine-tune of `TRAIN_DATA` as a Cloud Run Job with one L4. Records duration and cost in `train/runs/<tag>.json`. The page David's chunked recipe is `train/chain.sh` ([ONBOARDING, section 6.4](ONBOARDING.md)). |
| `make train-finish TAG=…` | E4B adapter merge and GGUF on a Cloud Batch VM with 64 GB of RAM and a 200 GB disk (`infra/04-finish-batch.sh`), published to the models bucket. The VM is deleted when it ends. |
| `make test` | Python tests (`MOCK_AI=1`, no network, no GPU) and web tests (`tsc` and vitest). |
