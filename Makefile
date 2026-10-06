# Tzij — Spanish <-> K'iche'. Run `make help` for the list.
SHELL := /bin/bash
# .env provides defaults; anything set on the command line or in the environment wins
# (e.g. `MOCK_AI=1 make test`). Each KEY=value line becomes `KEY ?= value`.
ENV_MK := $(shell test -f .env && sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$$/\1 ?= \2/' .env > .env.mk && echo .env.mk)
-include $(ENV_MK)
export

UV ?= uv
# Training data of the stage David (tzij-2026-10-mix-s7): RAFT + Bloom back-translation in both directions
# + the first 2,409 distilled pairs + 30% of the web pairs as replay (make train-data). The stage run continued
# tzij-2026-10-tm-a-e2-s4 in 8 chunks: train/chain.sh, recipe in docs/ONBOARDING.md section 6.4.
TRAIN_DATA ?= data/train/chat-raft-bt-both-dst2409-new30.jsonl
REVIEW_CSV ?=
# The demo runs in Google Cloud: David's GPU service and the page (infra/20-david.sh, infra/21-page.sh).
DEMO_REGION ?= europe-west4

.PHONY: help data deploy deploy-david deploy-page page-url david-proxy data-cloud data-pull index niche-data review-test apply-review fertility datasheet tune-retrieval niche eval human-eval-sheet train-data train-data-raft train-data-raft-bt distill monolingual back-translate train train-finish test examples screens

help: ## Show targets
	@grep -hE '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

data: ## Run the data pipeline locally -> data/processed/<version>/ + data/DATASHEET.md
	$(UV) run python -m pipeline.run --gcs-uri ""

deploy: ## Everything in Google Cloud: project setup, data job, training jobs, David's GPU service and the demo page
	bash infra/00-project.sh
	DEPLOY_ONLY=1 bash infra/10-data-job.sh
	bash infra/01-train-service-account.sh
	bash infra/03-train-job.sh
	bash infra/20-david.sh
	bash infra/21-page.sh

deploy-david: ## Rebuild and redeploy David's GPU service (model, index and code): after a new model or index
	bash infra/20-david.sh

deploy-page: ## Rebuild and redeploy the demo page (web/ and its service)
	bash infra/21-page.sh

page-url: ## Print the demo page's public URL
	@gcloud run services describe tzij --region $(DEMO_REGION) --project $(GOOGLE_CLOUD_PROJECT) --format='value(status.url)'

david-proxy: ## Open David's Ollama in the cloud at localhost:11434 for make eval / index / tune-retrieval (leave it running)
	gcloud run services proxy tzij-david --region $(DEMO_REGION) --project $(GOOGLE_CLOUD_PROJECT) --port 11434

data-cloud: ## Run the pipeline as a Cloud Run Job, writing a versioned dataset to the tzij-data bucket
	bash infra/10-data-job.sh

data-pull: ## Download the latest dataset produced by the Cloud Run Job
	$(UV) run python -m pipeline.pull

index: ## Build the retrieval index (EmbeddingGemma on the cloud David, via make david-proxy) and publish it to the data bucket
	$(UV) run python -m rag.build_index
	gcloud storage cp --project $(GOOGLE_CLOUD_PROJECT) $(RAG_INDEX) $(DATA_BUCKET_URI)/index/$$(cat data/processed/LATEST)/tzij.sqlite
	@echo "Index published. David uses it after: make deploy-david"

niche-data: ## Build the index; if LATEST has no test_niche.jsonl, first hold Firefox Focus out of 20261002-022500 (specialty test)
	@if [ -f "data/processed/$$(cat data/processed/LATEST 2>/dev/null)/test_niche.jsonl" ]; then \
	  echo "data/processed/LATEST ($$(cat data/processed/LATEST)) ya tiene test_niche.jsonl: no se rehace."; \
	else \
	  $(UV) run python -m pipeline.niche build; \
	fi
	$(MAKE) index

review-test: ## Export the test set as CSV for the native speaker -> data/review/
	$(UV) run python -m pipeline.review

apply-review: ## Apply the native speaker's verdicts: make apply-review REVIEW_CSV=path.csv
	@test -n "$(REVIEW_CSV)" || (echo "usage: make apply-review REVIEW_CSV=data/review/<file>.csv" && exit 1)
	$(UV) run python -m pipeline.apply_review "$(REVIEW_CSV)"

fertility: ## Token fertility of K'iche' vs Spanish in Gemma's tokenizer -> evals/fertility.md
	$(UV) run python -m evals.fertility

datasheet: ## Re-render data/DATASHEET.md from the latest manifest
	$(UV) run python -m pipeline.datasheet data/processed/$$(cat data/processed/LATEST)/manifest.json

tune-retrieval: ## Tune retrieval (mode, k, order, fuzzy) on the dev split only -> evals/tuning.md
	$(UV) run python -m evals.tune_retrieval

niche: ## David vs Goliath on the niche (held-out Pontoon product, translation memory) -> evals/niche_results.md: make niche RUN=niche DAVID=<variant>
	@test -n "$(RUN)" -a -n "$(DAVID)" || (echo "usage: make niche RUN=<eval run with --split test_niche> DAVID=<variant> [GOLIATH=gemini-3.8-flash]" && exit 1)
	$(UV) run python evals/niche_report.py --run $(RUN) --david "$(DAVID)" --goliath "$(or $(GOLIATH),$(GEMINI_MODEL))"

eval: ## Compare every available variant on the test set -> evals/report.md
	$(UV) run python -m evals.run_eval $(EVAL_ARGS)

human-eval-sheet: ## Blind 50-item rating sheet from the latest eval run: [VARIANTS="tzij-2026-10-mix-s7+hybrid+mbr4,gemini-3.8-flash"] [RUN=id]
	$(UV) run python -m evals.human_eval_sheet $(if $(VARIANTS),--variants "$(VARIANTS)") $(if $(RUN),--run $(RUN))

train-data: ## Training data of the stage David: RAFT + back-translation (both directions) + 2,409 distilled pairs + 30% web replay -> data/train/chat-raft-bt-both-dst2409-new30.jsonl
	$(UV) run python -m pipeline.train_set --raft --bt --bt-both --distilled 2409 --only-new 0.3

train-data-raft: ## Train split with retrieved context in every prompt (RAFT) -> data/train/chat-raft.jsonl
	$(UV) run python -m pipeline.train_set --raft

train-data-raft-bt: ## RAFT data plus Gemini back-translated pairs (es->quc only) -> data/train/chat-raft-bt.jsonl
	$(UV) run python -m pipeline.train_set --raft --bt

distill: ## Distillation in the test's domains: Gemini Spanish -> K'iche' with David's retrieved context, round-trip filtered (LIMIT=N) -> data/train/distilled/
	$(UV) run python -m pipeline.distill gen
	$(UV) run python -m pipeline.distill translate $(if $(LIMIT),--limit $(LIMIT))

monolingual: ## Licensed monolingual K'iche' (train-side sources only) -> data/monolingual/quc.jsonl
	$(UV) run python -m pipeline.monolingual

back-translate: ## Gemini Spanish for the monolingual K'iche' (one-time, cost recorded) -> data/train/back_translated_gemini.jsonl
	$(UV) run python -m pipeline.back_translate

train: ## LoRA fine-tune of TRAIN_DATA as a Cloud Run GPU Job (L4), record time and cost: make train TAG=tzij-YYYY-MM [TRAIN_ARGS=...]
	@test -n "$(TAG)" || (echo "usage: make train TAG=tzij-YYYY-MM" && exit 1)
	@test -f $(TRAIN_DATA) || $(MAKE) train-data
	$(UV) run python train/submit_job.py --app tzij --tag $(TAG) --data $(TRAIN_DATA) -- $(TRAIN_ARGS)

train-finish: ## Merge + GGUF an E4B adapter in the cloud (Cloud Batch, 64 GB VM) and publish it: make train-finish TAG=...
	@test -n "$(TAG)" || (echo "usage: make train-finish TAG=tzij-YYYY-MM (the tag of a finished cloud training run)" && exit 1)
	bash infra/04-finish-batch.sh $(TAG)

test: ## Python + web tests (mock models: no Ollama, GPU or cloud needed)
	MOCK_AI=1 $(UV) run pytest -q
	@if [ -d web/node_modules ]; then cd web && npx tsc --noEmit && npx vitest run; else echo "(web: npm ci in web/ to run its tests)"; fi

examples: ## Re-check the page's example phrases against the cloud David and Goliath -> duel/examples.json: [IDS=pair_id,...]
	@DAVID_URL=$$(gcloud run services describe tzij-david --region $(DEMO_REGION) --project $(GOOGLE_CLOUD_PROJECT) --format='value(status.url)') \
	  PYTHONPATH=$(CURDIR):$(CURDIR)/duel $(UV) run python -m tzij_duel.examples $(if $(IDS),--ids $(IDS))

screens: ## Screenshots of the live demo page for docs/DEMO.md -> docs/demo/ (the page must be deployed)
	cd web && BASE_URL=$${BASE_URL:-$$(gcloud run services describe tzij --region $(DEMO_REGION) --project $(GOOGLE_CLOUD_PROJECT) --format='value(status.url)')} node tests/translator.mjs
