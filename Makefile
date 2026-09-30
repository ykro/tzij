# Tzij — Spanish <-> K'iche'. Run `make help` for the list.
SHELL := /bin/bash
-include .env
export

UV ?= uv
REVIEW_CSV ?=

.PHONY: help data data-cloud data-pull index review-test apply-review fertility datasheet test up reset

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

data: ## Run the data pipeline locally -> data/processed/<version>/ + data/DATASHEET.md
	$(UV) run python -m pipeline.run --gcs-uri ""

data-cloud: ## Run the pipeline as a Cloud Run Job, writing a versioned dataset to the tzij-data bucket
	bash infra/10-data-job.sh

data-pull: ## Download the latest dataset produced by the Cloud Run Job
	$(UV) run python -m pipeline.pull

index: ## Build the offline retrieval index (EmbeddingGemma via Ollama + sqlite-vec)
	$(UV) run python -m rag.build_index

review-test: ## Export the test set as CSV for the native speaker -> data/review/
	$(UV) run python -m pipeline.review

apply-review: ## Apply the native speaker's verdicts: make apply-review REVIEW_CSV=path.csv
	@test -n "$(REVIEW_CSV)" || (echo "usage: make apply-review REVIEW_CSV=data/review/<file>.csv" && exit 1)
	$(UV) run python -m pipeline.apply_review "$(REVIEW_CSV)"

fertility: ## Token fertility of K'iche' vs Spanish in Gemma's tokenizer -> evals/fertility.md
	$(UV) run python -m evals.fertility

datasheet: ## Re-render data/DATASHEET.md from the latest manifest
	$(UV) run python -m pipeline.datasheet data/processed/$$(cat data/processed/LATEST)/manifest.json

test: ## Run the test suite (offline; Ollama-only tests skip when it isn't running)
	MOCK_AI=1 $(UV) run pytest -q

up: ## (Phase 2) start Ollama, the duel service and both views. For now: checks Ollama.
	@curl -sf $${OLLAMA_HOST:-http://localhost:11434}/api/tags >/dev/null \
	  && echo "Ollama is up. The duel service and views arrive in Phase 2." \
	  || (echo "Ollama is not running: start it with 'ollama serve'." && exit 1)

reset: ## (Phase 2) clear rounds and verdicts. Nothing to clear yet.
	@echo "Nothing to reset yet: rounds and verdicts arrive with the duel service (Phase 2)."
