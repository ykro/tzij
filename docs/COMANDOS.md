# Comandos

El arranque paso a paso y todos los comandos del `Makefile`. `make help` los lista con su descripción. Volver al [README](../README.md). [English version](COMANDOS.en.md).

## Arranque paso a paso

Requisitos y detalles en [ONBOARDING.md](ONBOARDING.md). Con Python 3.12, `uv`, Node 24, Ollama y `gcloud` instalados:

```bash
cp .env.example .env                       # modelos, buckets y puertos; nunca se sube .env
uv sync                                    # dependencias de Python
ollama pull gemma4:e4b && ollama pull embeddinggemma
gcloud auth application-default login      # ADC para Vertex AI y Cloud Storage

make data-pull     # baja el último dataset del bucket (o `make data` para generarlo aquí)
make index         # índice de recuperación con EmbeddingGemma + sqlite-vec + FTS5
make pull-model TAG=tzij-2026-10-mix-s7   # el David ajustado (o LOCAL_MODEL_TAG=gemma4:e4b)
make web           # compila las vistas (necesita internet una vez, por las tipografías)
make up            # Ollama + David precargado + servicio + vistas en la LAN
```

Abre `http://127.0.0.1:8787/presentador/`. Escanea el QR con el teléfono. Pulsa `E` para una frase de evaluación o `/` para escribir una frase en vivo.

Para ensayar sin la nube ni GPU: `make up MOCK_AI=1` (o `MOCK_AI=1 make up`: lo que pases por la línea de comandos o el entorno gana sobre `.env`). En modo simulado David devuelve el mejor ejemplo recuperado de un índice pequeño de pares con licencia (`mock_data/`, embeddings por hashing) y nunca inventa K'iche'. No necesita Ollama, el índice ni el dataset.

## Día de la charla

```bash
make up                                          # terminal 1: se queda corriendo
make stage-on && make warmup && make preflight   # terminal 2: modelos cargados, todo en [ok]
make reset                                       # marcador en cero
# … la charla …
make stage-off                                   # igual que en los otros repos (aquí no hay nada en la nube)
```

## Todos los comandos

| Comando | Qué hace |
| --- | --- |
| `make help` | Lista los comandos. |
| `make data` | Corre el pipeline de datos en local: descarga, limpia, normaliza, deduplica, etiqueta dominios y separa por fuente. Escribe en `data/processed/<versión>/` y regenera `data/DATASHEET.md`. |
| `make data-cloud` | Corre el mismo pipeline como Cloud Run Job (`infra/10-data-job.sh`) y escribe un dataset versionado en `gs://…-tzij-data/datasets/`. |
| `make data-pull` | Baja el último dataset que produjo el job. |
| `make index` | Construye `rag/index/tzij.sqlite` solo con el split `train`, usando EmbeddingGemma vía Ollama. |
| `make review-test` | (Opcional) Exporta el conjunto de prueba a `data/review/test_review_<versión>.csv` para una revisión nativa. |
| `make apply-review REVIEW_CSV=…` | Aplica los veredictos (`ok` / `fix` / `reject`) al conjunto de prueba. |
| `make fertility` | Mide la fertilidad de tokens de K'iche' vs español y escribe `evals/fertility.md`. |
| `make datasheet` | Vuelve a generar `data/DATASHEET.md` desde el último manifest. |
| `make tune-retrieval` | Ajusta la recuperación (modo, k, orden, glosario difuso) solo con el split dev y escribe `evals/tuning.md`. |
| `make eval [EVAL_ARGS=…]` | Compara todas las variantes disponibles y escribe `evals/report.md`. Con `EVAL_ARGS="--split dev_domain --out evals/dev_domain_report.md"` mide en el split `dev_domain` (párrafos de BOUQuET y páginas de Bloom fuera de la muestra de prueba), donde se toman las decisiones entre ejecuciones. |
| `make human-eval-sheet` | Genera una hoja de evaluación humana a ciegas (50 frases) de la última ejecución; `VARIANTS="gemma4:e4b+rag,gemini-3.8-flash"` elige variantes. |
| `make train-data` | Convierte las oraciones de `train` en JSONL de chat (`data/train/chat.jsonl`). |
| `make train-data-raft` | Como `train-data`, pero con el contexto recuperado en cada prompt, excluyendo el propio par (RAFT): `data/train/chat-raft.jsonl`. |
| `make monolingual` | K'iche' monolingüe con licencia, solo de fuentes de entrenamiento (incluye los libros de Bloom solo en K'iche'): `data/monolingual/quc.jsonl`. |
| `make back-translate` | Gemini traduce ese K'iche' al español una sola vez y registra el costo: `data/train/back_translated_gemini.jsonl`. |
| `make train-data-raft-bt` | Datos RAFT + pares retrotraducidos (solo español → K'iche'): `data/train/chat-raft-bt.jsonl`. |
| `make train TAG=tzij-AAAA-MM [TRAIN_ARGS=…]` | Fine-tune LoRA como Cloud Run Job con una L4. Registra duración y costo en `train/runs/<tag>.json`. |
| `make train-local TAG=…` | El mismo entrenamiento en la Mac (MPS), por si no hay GPU en la nube. |
| `make train-finish TAG=…` | Hace el merge y el GGUF del adapter entrenado en la nube, en la Mac, y lo publica en el bucket de modelos. |
| `make pull-model TAG=…` | Baja el GGUF del bucket y lo registra en Ollama. |
| `make web` | Compila las vistas del presentador y del validador (export estático). |
| `make duel` | Levanta solo el servicio de duelo en `0.0.0.0:$DUEL_PORT`. |
| `make up` | (`MOCK_AI=1 make up`: sin Ollama, índice ni dataset.) Arranca Ollama si hace falta, precarga David y EmbeddingGemma, compila las vistas si faltan y sirve todo en la LAN. |
| `make reset` | Borra rondas y veredictos, con el servicio corriendo o no, en menos de 10 s. |
| `make stage-on` / `make stage-off` | No hacen nada en la nube: Tzij no tiene servicios que escalar (todo lo que sale en escena corre en la laptop). Existen para que la secuencia del día de la charla sea la misma en todos los repos. |
| `make warmup` | Carga David (con el `num_ctx` de las rondas) y EmbeddingGemma en Ollama, y hace una traducción de David con recuperación (+ MBR si `MBR_ON_STAGE=1`) y una llamada a Goliath, como en escena. No se registra en el marcador. |
| `make preflight` | Revisión antes de subir: Ollama con `LOCAL_MODEL_TAG` y el modelo de embeddings; que David no haya entrenado con Firefox Focus; que el índice exista y sea del dataset de `LATEST`; frases para las rondas de evaluación y de especialidad (`test_niche`); `/api/health` del duelo si está corriendo; Gemini (una llamada mínima); 10 GB libres en disco; y una traducción de David cronometrada dentro del presupuesto p50 de 5 s. Una línea `[ok]` o `[FALLA]` por revisión, con el arreglo; el código de salida es el número de fallas. |
| `make test` | Pruebas de Python (`MOCK_AI=1`, sin red) y de la web (vitest). |
| `make deploy` | Despliega las partes en la nube (proyecto, job de datos, job e imagen de entrenamiento). El duelo y las vistas se quedan en la laptop. |
| `make emulator` | Abre el validador en Chrome del emulador Android (`10.0.2.2`) y falla si el voto tarda más de 1 s en llegar a la pantalla. |
| `make screenshots` | Capturas de Playwright de ambas vistas a 1920×1080 y 390×844 (el servicio debe estar corriendo). |
| `make niche RUN=niche DAVID=<variante>` | David contra Goliath en el nicho (producto de Pontoon apartado, memoria de traducción): `evals/niche_results.md`. |
| `make distill [LIMIT=N]` | Destilación en los dominios de la prueba: Gemini escribe español cotidiano y lo traduce al K'iche' con el contexto recuperado de David; solo quedan los pares que pasan el alfabeto de la ALMG, la longitud y la ida y vuelta. Escribe `data/train/distilled/` (los rechazos en `rejected.jsonl`, para no pagarlos dos veces). Solo entrenamiento ([bitácora, sección 11](BITACORA.md)). |
| `make synthetic` | Pares sintéticos con Gemini, anclados al diccionario y a UD, filtrados con ida y vuelta: `data/train/synthetic/`. No entran al entrenamiento ([bitácora, sección 7](BITACORA.md)). |
| `make train-data-raft-bt-syn` | RAFT + retrotraducción + sintéticos con tope `SYN`: `data/train/chat-raft-bt-syn<N>.jsonl`. |
| `make llama-server` | Servidor de llama.cpp para las variantes `@llama` de la evaluación (sesgo de logits, 8 ranuras en paralelo) con el GGUF de `LLAMA_SERVER_MODEL` en Ollama. |
| `make demo-screens` | Capturas de [DEMO.md](DEMO.md) con las teclas del escenario (necesita `make up` con la variante de escenario; `EMULATOR=0` omite el teléfono). |

`make deploy` despliega solo lo que vive en la nube: prepara el proyecto (APIs, Artifact Registry, buckets, secreto `hf-token`) con `infra/00-project.sh`, despliega el Cloud Run Job de datos y el job de entrenamiento con su imagen. **El servicio de duelo y las vistas no se despliegan, a propósito:** corren en la laptop porque la charla mide lo que pasa sin internet.
