#!/bin/sh
# Ollama on localhost, the David service on Cloud Run's port. The service warms up the models in
# the background and says so on /health.
ollama serve &
exec /opt/venv/bin/uvicorn tzij_duel.david_app:create_app --factory --host 0.0.0.0 --port "${PORT:-8080}"
