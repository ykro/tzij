# Tzij — Spanish <-> K'iche'. Run `make help` for the list.
SHELL := /bin/bash
-include .env
export

UV ?= uv
REVIEW_CSV ?=
DUEL_PORT ?= 8787
OLLAMA ?= $(if $(OLLAMA_URL),$(OLLAMA_URL),http://127.0.0.1:11434)

.PHONY: help data data-cloud data-pull index review-test apply-review fertility datasheet eval human-eval-sheet web duel test up reset screenshots

help: ## Show targets
	@grep -hE '^[a-z-]+:.*## ' Makefile | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

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

eval: ## Compare every available variant on the test set -> evals/report.md
	$(UV) run python -m evals.run_eval $(EVAL_ARGS)

human-eval-sheet: ## Blind 50-item rating sheet from the latest eval run (see evals/human_eval.md)
	$(UV) run python -m evals.human_eval_sheet

web: ## Build the presenter and validator views (static export; needs internet once for fonts)
	cd web && npm ci --silent && npm run build

duel: ## Run only the duel service (API + built views) on the LAN
	$(UV) run uvicorn tzij_duel.main:create_app --factory --app-dir duel --host 0.0.0.0 --port $(DUEL_PORT)

test: ## Python + web tests (offline; Ollama-only tests skip when it isn't running)
	MOCK_AI=1 $(UV) run pytest -q
	@if [ -d web/node_modules ]; then cd web && npx vitest run; else echo "(web: npm ci in web/ to run its tests)"; fi

up: ## Start Ollama, warm David, build the views if needed and serve everything on the LAN
	@curl -sf $(OLLAMA)/api/version >/dev/null || (ollama serve >/tmp/tzij-ollama.log 2>&1 &) ; \
	  for i in $$(seq 1 40); do curl -sf $(OLLAMA)/api/version >/dev/null && break; sleep 0.25; done
	@if [ "$(MOCK_AI)" != 1 ]; then \
	  curl -sf $(OLLAMA)/api/chat -d '{"model":"$(LOCAL_MODEL_TAG)","messages":[],"keep_alive":"30m","options":{"num_ctx":$(or $(OLLAMA_NUM_CTX),4096)}}' >/dev/null \
	    || echo "!! David ($(LOCAL_MODEL_TAG)) no está en Ollama: ollama pull $(LOCAL_MODEL_TAG)"; \
	  curl -sf $(OLLAMA)/api/embed -d '{"model":"$(EMBEDDING_MODEL)","input":["hola"],"keep_alive":"30m"}' >/dev/null \
	    || echo "!! $(EMBEDDING_MODEL) no está en Ollama: ollama pull $(EMBEDDING_MODEL)"; \
	  test -f $(RAG_INDEX) || echo "!! Falta el índice de recuperación: make index"; \
	fi
	@test -f web/out/index.html || $(MAKE) web
	@echo "Presentador: http://127.0.0.1:$(DUEL_PORT)/presentador/   (validador: el QR en pantalla)"
	$(MAKE) duel

reset: ## Clear rounds and verdicts (running service or state file), in well under 10 seconds
	@curl -sf -X POST http://127.0.0.1:$(DUEL_PORT)/api/reset >/dev/null && echo "Marcador reiniciado (servicio en marcha)." \
	  || (rm -f $(or $(DUEL_STATE_PATH),duel/state/rounds.json) && echo "Marcador reiniciado (archivo de estado borrado).")

screenshots: ## Playwright screenshots of both views at 1920x1080 and 390x844 (service must be running)
	cd web && node tests/screenshots.mjs
