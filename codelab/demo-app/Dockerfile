FROM ollama/ollama:latest

# Instalar Node.js 20 y curl para ejecutar SoporteLocal junto con Ollama (gemma4:e2b) en el mismo contenedor
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

ENV OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODELS=/models \
    OLLAMA_KEEP_ALIVE=-1 \
    GEMMA_MODEL=gemma4:e2b \
    PORT=8080

# Hornear los pesos de gemma4:e2b dentro de la imagen para evitar descargas en cold start
RUN ollama serve & sleep 5 && \
    ollama pull gemma4:e2b && \
    ollama list

WORKDIR /app
COPY package.json server.mjs duel.test.mjs start.sh ./
COPY public ./public
RUN chmod +x /app/start.sh && node --test /app/duel.test.mjs

EXPOSE 8080
ENTRYPOINT ["/app/start.sh"]
