# Onboarding — Tzij

Guía para montar Tzij desde cero, preparar los datos y los modelos, ensayar el duelo y llegar al día de la charla sin sorpresas. La visión general está en el [README](../README.md) y las decisiones técnicas en [DECISIONES.md](DECISIONES.md).

Contenido:

1. [Requisitos](#1-requisitos)
2. [Instalación local](#2-instalación-local)
3. [Modelos de Ollama](#3-modelos-de-ollama)
4. [Credenciales: ADC y el token de Hugging Face](#4-credenciales-adc-y-el-token-de-hugging-face)
5. [Google Cloud: preparación única y scripts `infra/`](#5-google-cloud-preparación-única-y-scripts-infra)
6. [Datos, índice, entrenamiento y evaluación](#6-datos-índice-entrenamiento-y-evaluación)
7. [Correr el duelo (y sin internet)](#7-correr-el-duelo-y-sin-internet)
8. [El validador (opcional): emulador Android y LAN real](#8-el-validador-opcional-emulador-android-y-lan-real)
9. [Revisión con hablantes nativos (opcional)](#9-revisión-con-hablantes-nativos-opcional)
10. [Pruebas y ensayo](#10-pruebas-y-ensayo)
11. [Recorrido por el código: una traducción](#11-recorrido-por-el-código-una-traducción)
12. [Solución de problemas](#12-solución-de-problemas)
13. [Checklist del día de la charla](#13-checklist-del-día-de-la-charla)

![Pipeline: datos, entrenamiento y evaluación](diagrams/pipeline.png)

## 1. Requisitos

Versiones con las que se verificó el proyecto (30 de septiembre de 2026):

| Herramienta | Versión | Para qué |
| --- | --- | --- |
| macOS en Apple Silicon | — | La laptop del escenario. `make train-local` usa MPS y `train/setup_llama_cpp.sh` baja el `llama-quantize` precompilado para macOS arm64. |
| RAM | `make train-finish` se probó en una Mac de 64 GB | El merge de E4B en bf16 más la conversión a GGUF. Para el duelo basta con lo que necesita Ollama para David (~5.3 GB) y `embeddinggemma`. |
| Python | 3.12 (`.python-version`; `pyproject.toml` pide `>=3.12,<3.13`) | Pipeline, índice, servicio y evals |
| uv | 0.8.22 | Entornos y dependencias de Python. Nunca `pip` global. |
| Node.js / npm | 24.21.0 / 12.0.2 | Vistas en Next.js 16.3.8 y pruebas (vitest, Playwright 1.63.0) |
| Ollama | 0.35.0 | David y EmbeddingGemma |
| Google Cloud SDK (`gcloud`) | 587.0.0 | ADC, Cloud Run Jobs, Cloud Build, Cloud Storage, Secret Manager |
| Android SDK (`adb`, emulador) | `adb` 1.0.41 | Solo para `make emulator` |
| Cuenta de Hugging Face | — | Aceptar los términos de BOUQuET; su token va a Secret Manager |

Espacio en disco aproximado: unos 17 GB para los modelos de Ollama (`gemma4:e4b` 6.6 GB, cada fine-tune `tzij-2026-10-*` 5.3 GB, `embeddinggemma` 621 MB) y espacio temporal para `make train-finish` en `models/.work/`: pesos base (~16 GB, compartidos entre tags), modelo fusionado (~16 GB, se reutiliza si ya existe), GGUF intermedio Q8_0 (~8 GB con `GGUF_OUTTYPE=q8_0`, se borra al final) y Q4_K_M (~5 GB).

## 2. Instalación local

```bash
git clone <repo> tzij && cd tzij
cp .env.example .env        # .env está en .gitignore; nunca subas un token
uv sync                     # crea .venv con Python 3.12 y las dependencias (incluye pytest)
cd web && npm ci && cd ..   # opcional aquí: `make web` lo hace, y `make test` lo necesita para las pruebas web
```

Todo se configura en `.env`; el `Makefile` lo carga y exporta. Las variables más importantes:

| Variable | Valor actual | Qué controla |
| --- | --- | --- |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Goliath |
| `GEMINI_INPUT_USD_PER_M` / `GEMINI_OUTPUT_USD_PER_M` | `0.75` / `3.75` | Costo mostrado en pantalla. Desde el 1 de enero de 2027 la tarifa de lista sube a `1.50` / `7.50` (ver el comentario en `.env.example`). |
| `LOCAL_MODEL_TAG` | `tzij-2026-10-raft-bt-s3` | David (siempre con recuperación) |
| `BASE_MODEL_TAGS` | `gemma4:e4b` | Modelos base que compara `make eval` |
| `FINETUNED_MODEL_TAGS` | `tzij-2026-10-raft-bt-s3,tzij-2026-10-raft-bt-s0,tzij-2026-10-raft-s0` | Modelos con fine-tune que compara `make eval` |
| `GEMMA_BASE_MODEL` | `gemma-4-E4B-it` | Checkpoint base del fine-tune y tokenizador de `make fertility` |
| `EMBEDDING_MODEL` | `embeddinggemma` | Embeddings del índice. El índice y las consultas tienen que usar el mismo. |
| `RAG_INDEX`, `RAG_K` | `rag/index/tzij.sqlite`, `6` | Índice y cuántos ejemplos y entradas de glosario recibe David |
| `RAG_MODE`, `RAG_ORDER`, `RAG_FUZZY` | `hybrid`, `best_last`, `1` | Búsqueda híbrida BM25 + vectores (o `vector`), ejemplo más cercano al final, glosario difuso. Ajustados con `make tune-retrieval` en dev. |
| `MBR_ON_STAGE`, `MBR_SAMPLES` | `1`, `4` | Decodificación MBR en el escenario (`0` = una sola muestra, p50 ~1.7 s en vez de ~4 s) |
| `OLLAMA_NUM_CTX` | `4096` | Contexto de Gemma en Ollama |
| `DUEL_PORT`, `PUBLIC_URL` | `8787`, vacío | Puerto del servicio; URL fija del QR (vacío = IP de la LAN detectada) |
| `FORCE_OFFLINE` | `0` | `1` simula "sin Wi-Fi" para Goliath sin tocar el sistema operativo |
| `REQUIRE_VALIDATED_TEST` | `0` | Opcional: `1` limita las rondas de evaluación a pares que además revisó una persona nativa |
| `MOCK_AI` | `0` | `1` evita la nube y la GPU (pruebas y ensayos) |

`.env` solo pone valores por defecto: lo que pases por la línea de comandos o el entorno gana (`MOCK_AI=1 make up` y `make up MOCK_AI=1` hacen lo mismo). El `Makefile` convierte cada `CLAVE=valor` de `.env` en `CLAVE ?= valor` (archivo `.env.mk`, ignorado por git).

## 3. Modelos de Ollama

```bash
make pull-model TAG=tzij-2026-10-raft-bt-s3   # David (ver §6.5)
ollama pull embeddinggemma      # embeddings del índice (también offline, en el escenario)
ollama pull gemma4:e4b          # base, para `make eval` y como David de respaldo
ollama list
```

`make up` precarga David (`keep_alive` de 30 min, `num_ctx` 4096) y EmbeddingGemma, y avisa con `!!` si falta alguno. El servicio hace lo mismo al arrancar, porque cargar un modelo en frío cuesta segundos en el escenario.

## 4. Credenciales: ADC y el token de Hugging Face

### ADC

No hay claves de API en el repo. Gemini (Vertex AI), Cloud Storage y Secret Manager usan Application Default Credentials:

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project ai-experiments-487722
```

Los scripts de `infra/` fijan el proyecto con `CLOUDSDK_CORE_PROJECT` y no tocan tu configuración global de `gcloud`.

### Token de Hugging Face en Secret Manager (`hf-token`)

BOUQuET tiene acceso restringido. Sin token, el pipeline lo salta con un aviso y sigue con el resto. El token también evita los 429 que Hugging Face devuelve a descargas anónimas desde IPs de Cloud Run.

1. Con tu cuenta de Hugging Face, acepta los términos en <https://huggingface.co/datasets/facebook/bouquet>.
2. Crea un token de lectura en Hugging Face.
3. Guárdalo en Secret Manager, nunca en `.env` del repo:

   ```bash
   printf %s "hf_..." | gcloud secrets create hf-token --project ai-experiments-487722 \
     --replication-policy=automatic --data-file=-
   # para rotarlo:
   printf %s "hf_..." | gcloud secrets versions add hf-token --project ai-experiments-487722 --data-file=-
   ```

Orden de búsqueda (`pipeline/secrets.py`, `train/train_lora.py`): variable `HF_TOKEN` → secreto `hf-token` vía ADC → sin token. Los Cloud Run Jobs lo reciben montado como `HF_TOKEN`. `infra/10-data-job.sh` y `infra/01-train-service-account.sh` dan acceso al secreto a sus cuentas de servicio, siempre que el secreto ya exista. Por eso conviene crearlo **antes** de correr esos scripts.

## 5. Google Cloud: preparación única y scripts `infra/`

Proyecto: `ai-experiments-487722`. Los jobs de datos y las imágenes viven en `us-central1` (Artifact Registry `charlas2027`). El entrenamiento corre en `europe-west4`, donde está la GPU L4.

### 5.1 Todo desde cero: `make deploy`

```bash
HF_TOKEN=hf_... make deploy   # HF_TOKEN solo la primera vez, para crear el secreto hf-token
```

`make deploy` despliega **solo las partes en la nube**, en este orden: `infra/00-project.sh`
(habilita las APIs, crea el Artifact Registry `charlas2027`, los buckets `…-tzij-data`,
`…-tzij-models` y `…-train-eu`, y el secreto `hf-token` si le pasas `HF_TOKEN`), el Cloud Run Job
de datos sin ejecutarlo (`DEPLOY_ONLY=1 infra/10-data-job.sh`), la cuenta de servicio de
entrenamiento y el Cloud Run Job `tzij-train` con su imagen. Todo es idempotente: se puede volver a
correr.

**El servicio de duelo y las dos vistas no se despliegan, a propósito:** corren en la laptop porque
la charla mide lo que pasa sin internet (`make up`).

Lo único que no se puede automatizar: aceptar los términos de BOUQuET con tu cuenta de Hugging Face
(antes de crear el token) y tener cuota de GPU NVIDIA L4 para Cloud Run en `europe-west4`.

### 5.2 Los scripts, en orden

Todos cargan `infra/env.sh` (proyecto, regiones, Artifact Registry) e `infra/app.env` (`APP=tzij`).

| Orden | Script | Qué hace | ¿Quién lo llama? |
| --- | --- | --- | --- |
| 0 | `infra/00-project.sh` | Habilita APIs; crea Artifact Registry, los tres buckets y el secreto `hf-token` (si recibe `HF_TOKEN`). Idempotente. | `make deploy` |
| 1 | `infra/10-data-job.sh` | Crea la cuenta de servicio `tzij-data-job` con acceso solo al bucket de datos (y a `hf-token`), construye la imagen con Cloud Build (`pipeline/cloudbuild.yaml`), despliega el job `tzij-data` (2 vCPU, 4 GiB, 1 h, sin reintentos) y lo ejecuta (con `DEPLOY_ONLY=1`, solo despliega). | `make data-cloud`, `make deploy` |
| 2 | `infra/01-train-service-account.sh` | Crea la cuenta de servicio `tzij-train` con acceso al bucket de modelos, al de staging, a Artifact Registry y a `hf-token`. | `make deploy` |
| 3 | `infra/02-train-image.sh` | Construye la imagen de entrenamiento con Cloud Build. La etiqueta es un hash del `Dockerfile`, `requirements.txt` y `train_lora.py`, así que una receta sin cambios no se reconstruye (la primera vez tarda unos 15 min). | `make train` (vía `train/submit_job.py`) |
| 4 | `infra/03-train-job.sh` | Crea o actualiza el Cloud Run Job `tzij-train` en `europe-west4`: 1× L4, 8 vCPU, 32 GiB, 1 h, el bucket de staging montado en `/mnt/work` (caché de pesos base), `GGUF_OUTTYPE` desde `.env`. | `make deploy`, `make train` (vía `train/submit_job.py`) |

La numeración agrupa los scripts (`0x` entrenamiento, `1x` datos). En el flujo real, los datos van primero. No hay dependencias entre el script 10 y los 01–03.

## 6. Datos, índice, entrenamiento y evaluación

### 6.1 `make data` o `make data-cloud`

```bash
make data-cloud   # recomendado: Cloud Run Job → gs://…-tzij-data/datasets/<versión>/ + LATEST
make data-pull    # lo baja a data/processed/<versión>/ y actualiza data/processed/LATEST
# o, todo en la laptop:
make data         # descarga a data/raw/, escribe data/processed/<versión>/ y data/DATASHEET.md
```

El pipeline (`pipeline/run.py`) hace: descarga por fuente (`pipeline/sources/*.py`, con caché cruda) → normalización (`data/normalize.py`) → limpieza con motivo de descarte (`pipeline/clean.py`) → etiquetas de dominio → deduplicación → split por fuente con chequeo de fugas y tope religioso (`pipeline/split.py`) → `train.jsonl` / `dev.jsonl` / `test.jsonl` (un registro por par y dirección) → `manifest.json` y datasheet. El job escribe el datasheet junto al dataset en GCS; para regenerar el del repo, usa `make datasheet` después de `make data-pull`.

Dataset actual: `20260930-220035`. Train 7,025 pares, dev 111, prueba 1,654 (300 de Bloom, 1,354 de BOUQuET). Proporción religiosa en train: 30.0 %.

### 6.2 `make index`

```bash
make index    # necesita Ollama con embeddinggemma
```

Indexa solo el split `train` (`pipeline.split.RETRIEVAL_SPLITS`) y se niega a indexar cualquier otro. Guarda el modelo de embeddings y la versión del dataset dentro del índice. El índice actual tiene 14,050 entradas (7,025 por dirección). Los embeddings se cachean en `rag/.cache/embeddings.sqlite`, así que reconstruir es rápido.

### 6.3 `make fertility` (opcional)

Mide tokens por palabra con el `tokenizer.json` de `google/<GEMMA_BASE_MODEL>` y verifica contra `prompt_eval_count` de Ollama. Escribe `evals/fertility.md`, que `make eval` copia dentro del reporte.

### 6.4 `make train`

```bash
make train TAG=tzij-2026-09 TRAIN_ARGS="--epochs=1"
```

El David actual se entrenó con RAFT + retrotraducción, en 4 trozos de 1/4 de época para no pasar el límite de 1 h:

```bash
make monolingual && make back-translate   # una vez: 405 oraciones → 399 pares, $0.12
make train-data-raft-bt                   # 5,579 ejemplos con contexto recuperado
A="--epochs=1 --batch-size=2 --grad-accum=8 --max-length=1024"
make train TAG=tzij-2026-10-raft-bt-s0 TRAIN_DATA=data/train/chat-raft-bt.jsonl TRAIN_ARGS="$A --shard=0/4"
make train TAG=tzij-2026-10-raft-bt-s1 TRAIN_DATA=data/train/chat-raft-bt.jsonl \
  TRAIN_ARGS="$A --shard=1/4 --init-adapter=gs://…-train-eu/tzij/runs/tzij-2026-10-raft-bt-s0/adapter"
# … igual para s2 y s3; después make train-finish TAG=tzij-2026-10-raft-bt-s3
```

1. `make train-data` convierte las oraciones de `train` (ambas direcciones) en JSONL de chat con el mismo prompt del duelo, sin contexto de recuperación, y vuelve a comprobar el tope religioso. Salen 5,180 ejemplos.
2. `train/submit_job.py` sube el JSONL a `gs://…-train-eu/tzij/data/<tag>/`, construye o reutiliza la imagen (`02`), actualiza el job (`03`), lo ejecuta con `--epochs`, etc., espera y escribe `train/runs/<tag>.json` con duración, máquina y costo estimado.
3. Dentro del job, `train/train_lora.py` baja los pesos (`GEMMA_WEIGHTS_URI=hf://google`, con caché en el bucket), entrena la LoRA (r=16, alpha=32, lr 2e-4, solo el decodificador de texto) y guarda el adapter en el volumen.

Límites que hay que respetar: **1 h por tarea de GPU** en Cloud Run (por eso se usa `--epochs=1`; 1.5 épocas no cabían) y **32 GiB** de memoria (por eso el merge de E4B no termina en la nube). La ejecución `tzij-2026-09` entrenó bien (324 pasos, 22 min) y después el job terminó con *"The configured memory limit was reached"* al guardar el modelo fusionado. Es lo esperado con E4B: sigue con `make train-finish`.

### 6.5 `make train-finish` y `make pull-model`

```bash
make train-finish TAG=tzij-2026-10-raft-bt-s3   # adapter del bucket → merge → GGUF Q8_0 → Q4_K_M → gs://…-tzij-models/<tag>/
make pull-model  TAG=tzij-2026-10-raft-bt-s3    # baja Modelfile + GGUF + metrics.json a models/<tag>/ y hace `ollama create`
```

`train-finish` usa `uv run --python 3.12 --with-requirements train/requirements.txt --with torch` (un entorno aparte del proyecto) y descarga llama.cpp `b11292` a `train/.llama.cpp/`. El GGUF Q4_K_M resultante pesa unos 5.3 GB. El `Modelfile` usa el renderer y el parser de `gemma4`, así que el modelo ajustado se pide igual que su base.

Si no hay GPU en la nube: `make train-local TAG=… [TRAIN_ARGS="--epochs=1"]` corre el mismo entrenamiento en la Mac (MPS) y publica igual. `train`, `train-local`, `train-finish` y `pull-model` exigen `TAG` y lo dicen si falta.

### 6.6 `make eval`

```bash
make eval                                             # todas las variantes, 150 pares por fuente y dirección
make eval EVAL_ARGS="--limit 20"                      # prueba rápida
make eval EVAL_ARGS="--only gemma4:e4b+hybrid"        # una variante
make eval EVAL_ARGS="--run final-20261002 --only tzij-2026-10-raft-bt-s3+hybrid+mbr4"  # agrega variantes a una ejecución
```

Necesita internet y ADC para las variantes de Gemini, y en Ollama todos los tags de `BASE_MODEL_TAGS` y `FINETUNED_MODEL_TAGS`. Las predicciones se guardan en `evals/runs/<run>/<variante>.jsonl`, así que una ejecución interrumpida se retoma con `--run`. El reporte incluye todas las variantes que tengan resultados en esa ejecución y dice cuál debe subir al escenario: la mejor variante local. Ese tag va en `LOCAL_MODEL_TAG`.

## 7. Correr el duelo (y sin internet)

```bash
make up            # o `make up MOCK_AI=1` para ensayar sin nube ni GPU
```

- Presentador: `http://127.0.0.1:8787/presentador/` (1920×1080). Atajos: `/` escribir una frase en vivo, `E` frase de evaluación, `D` cambiar dirección, `M` ficha del modelo, `Esc` cerrar. La barra de comandos incluye frases sugeridas de los datos, el interruptor "Simular sin Wi-Fi (ensayo)" y "Reiniciar marcador".
- **Rondas de evaluación:** frases de prueba de Bloom (2 a 14 palabras, nunca de BOUQuET) con su referencia; se califican con chrF++.
- **Rondas en vivo (opcionales):** cualquier frase; las califica una persona validadora si la hay. Sin validador, usa rondas de evaluación.
- `make reset` borra rondas y veredictos (`duel/state/rounds.json`).

**Sin internet.** Todo lo que usa David está en la laptop. El servicio comprueba la conectividad cada 3 s con una conexión TCP de 0.8 s a `aiplatform.googleapis.com:443`. Sin red, la pastilla cambia a "Sin conexión", Goliath muestra "Sin conexión" en vez de llamar a Gemini, y David traduce igual. Dos formas de probarlo:

1. **Real:** apaga el Wi-Fi de la laptop (o desconecta la salida a internet del router) y lanza una ronda.
2. **Simulada:** `make up FORCE_OFFLINE=1`, o el interruptor de la barra de comandos. No toca el sistema operativo y deja la LAN intacta para el teléfono.

Requisito previo: `make web` **con** internet al menos una vez, porque `next/font` descarga las tipografías al compilar. Después las vistas no piden nada a internet.

## 8. El validador (opcional): emulador Android y LAN real

### Emulador Android (`10.0.2.2`)

Desde el emulador, `10.0.2.2` es el `localhost` de la laptop.

```bash
emulator -avd <tu_avd> &           # cualquier AVD con Chrome
make up                            # en otra terminal
make emulator                      # ANDROID_SERIAL=emulator-5556 por defecto
make emulator ANDROID_SERIAL=emulator-5554 BASE_URL=http://127.0.0.1:8787
```

`web/tests/emulator.mjs` abre `http://10.0.2.2:8787/validar/` en el Chrome del emulador, lo controla por DevTools (`adb forward tcp:9333`), lanza una ronda en vivo, vota y mide cuánto tarda el voto en aparecer en el presentador. **Falla si tarda más de 1 s.** Las capturas quedan en `web/test-results/screens/`. Para probar a mano, abre `http://10.0.2.2:8787/validar/` en el Chrome del emulador.

### LAN real (un teléfono físico)

1. Laptop y teléfono en la **misma red**. Sirve cualquier LAN aunque no tenga salida a internet: un router de viaje, el hotspot del teléfono con los datos móviles apagados, o Compartir Internet de macOS (`bridge100`).
2. `make up`. El servicio escucha en `0.0.0.0:8787`. Si macOS pregunta, permite conexiones entrantes para Python.
3. Escanea el QR del presentador. Apunta a `http://<IP de la LAN>:8787/validar/`, calculada por `duel/tzij_duel/lan.py`. Si la IP detectada no es la correcta (varias interfaces, VPN), fíjala en `.env` con `PUBLIC_URL=http://<ip>:8787`.
4. El teléfono ve la frase y dos traducciones en orden aleatorio, sin modelo, latencia ni costo, y vota correcta / aceptable / incorrecta. El identificador del votante queda en `localStorage`; cada voto aparece al instante en la pantalla del presentador.

Las redes de eventos suelen aislar a los clientes entre sí (*client isolation*). Si el teléfono no carga la página, usa tu propia red.

## 9. Revisión con hablantes nativos (opcional)

Nada de esta sección es requisito: el conjunto de prueba ya llega `auto_validated` desde el pipeline (`pipeline/validate_test.py`) y el demo corre completo sin intervención humana.

### Conjunto de prueba

```bash
make review-test                          # → data/review/test_review_<versión>.csv
# la persona revisora llena verdict = ok | fix | reject, corrected_kiche y notes
make apply-review REVIEW_CSV=data/review/test_review_<versión>.csv
make eval                                 # vuelve a puntuar con las referencias revisadas
```

- El CSV tiene una fila por par (no por dirección), en UTF-8 con BOM para que Excel y Google Sheets respeten los acentos.
- `ok` → `status=validated`. `fix` → se usa el K'iche' corregido (normalizado) y queda validado. `reject` → el par sale del conjunto de prueba. Sin veredicto → sigue `pending_native_review`.
- `apply-review` reescribe `data/processed/<versión>/test.jsonl` en su lugar. Guarda el CSV: es la única copia de los veredictos.
- El CSV incluye pares de BOUQuET. Sus términos solo permiten redistribución privada: compártelo solo con la persona revisora y nunca lo publiques.
- Con pares validados, `make up REQUIRE_VALIDATED_TEST=1` limita las rondas de evaluación a ellos. Si todavía no hay ninguno validado, el mazo queda vacío y la ronda responde "No quedan frases de evaluación en esta dirección."

### Evaluación humana a ciegas (`evals/human_eval.md`)

Se llena antes de cada evento: 50 frases por modelo, adecuación y fluidez de 1 a 5.

```bash
make eval
make human-eval-sheet VARIANTS="gemma4:e4b+rag,gemini-3.8-flash"   # RUN=<id> para otra ejecución
# sin VARIANTS incluye todas las variantes de la ejecución
```

Escribe `evals/runs/<run>/human_eval_sheet.csv` (sin nombres de modelo, filas mezcladas) y `human_eval_key.json` (letra → modelo, que no se comparte hasta terminar). `VARIANTS` usa los nombres de variante del reporte (los mismos de `make eval`); si alguno no tiene resultados en la ejecución, el comando lo dice y no genera la hoja. La hoja muestra el texto original, así que aplica la misma regla de privacidad para BOUQuET.

## 10. Pruebas y ensayo

```bash
make test        # 113 pruebas de Python (MOCK_AI=1, sin red) + 4 de la web (vitest)
make screenshots # con el servicio corriendo: capturas en web/test-results/screens/
```

Las pruebas que necesitan Ollama de verdad están marcadas `@pytest.mark.ollama` y se saltan si Ollama o el modelo no están. El ensayo completo sin nube ni Ollama es `MOCK_AI=1 make up`: no necesita Ollama, ni `make index`, ni el dataset. Usa `duel/mock_data/` (26 pares con licencia indexados con embeddings de hash y 8 frases de prueba de Bloom). Goliath devuelve el texto de entrada sin cambios y David el mejor ejemplo recuperado, así que todo el K'iche' en pantalla viene de datos con licencia. Sirve para ensayar el flujo, no los números.

## 11. Recorrido por el código: una traducción

Una ronda en vivo, de "Traducir en vivo" a la puntuación:

1. **Entrada.** La vista del presentador (`web/components/presenter/CommandBar.tsx`) hace `POST /api/rounds` con `{kind, direction, text}`. `Service.start_round` (`duel/tzij_duel/main.py`) crea la ronda en `RoundStore` (`rounds.py`), publica el estado por SSE y lanza `run_round` en segundo plano. En una ronda de evaluación, la frase y su referencia salen de `Deck.next` (`deck.py`).
2. **Conectividad.** `run_round` llama a `refresh_online()`. `Connectivity.is_online` (`duel/duel_core/connectivity.py`) abre una conexión TCP a `aiplatform.googleapis.com:443` con 0.8 s de timeout y cachea el resultado 3 s.
3. **En paralelo.** `asyncio.gather` corre `translate(david, …)` con el retriever y `translate(goliath, …)` sin él (`duel/tzij_duel/variants.py`).
4. **Normalizar.** `translate` normaliza la entrada con `normalize_kiche` o `normalize_spanish` (`data/normalize.py`): todos los saltillos pasan a `'`, se unifican espacios, comillas y guiones, y se pliegan las vocales con diéresis.
5. **Recuperar (solo David).** `Retriever.retrieve` (`rag/retrieve.py`) normaliza de nuevo, calcula el embedding con EmbeddingGemma en Ollama (`rag/embedder.py`, prefijo `task: sentence similarity | query: `) y hace dos búsquedas en `sqlite-vec`, filtradas por dirección:
   - **ejemplos:** los `RAG_K` pares de oraciones más cercanos;
   - **glosario:** coincidencias exactas (entrada completa, bigramas, palabras) y luego las entradas de diccionario más cercanas.

   `as_prompt_context()` arma el bloque `Glosario:` / `Ejemplos:`. El tiempo de recuperación se suma a la latencia de David.
6. **Prompt.** `translation_messages` (`duel/tzij_duel/prompts.py`, versión `tzij-translate-v1`) arma el mensaje de sistema (traductor cuidadoso, ortografía ALMG, apóstrofo para el saltillo, solo la traducción) y el de usuario. Si hay contexto, le antepone el encabezado del material de referencia.
7. **Modelo.**
   - David: `OllamaClient.complete` (`duel/duel_core/ollama_client.py`) llama a `POST /api/chat` sin streaming, con `temperature` 0.2, `num_predict` 128, `think: false`, `keep_alive` 30m y `num_ctx` 4096.
   - Goliath: `GeminiClient.complete` (`gemini_client.py`) llama a Vertex AI con `google-genai`, `thinking_level=low` y 20 s de timeout. Un error de red se convierte en estado `offline` y un timeout en `error`.

   `run_duel` (`duel/duel_core/duel.py`) nunca deja que un contendiente que falla tumbe la ronda.
8. **Limpiar y puntuar.** `clean_translation` (`duel_core/prompts.py`) se queda con la primera línea y quita prefijos tipo "Traducción:" y comillas. `normalize_output` aplica la misma normalización que a las referencias. En rondas de evaluación, `chrf_pp` (`duel_core/metrics.py`, sacrebleu `CHRF(word_order=2)`) puntúa contra la referencia. El costo sale de `cost_usd` (tokens × precio de `.env`; David es $0).
9. **Publicar y votar.** `RoundStore.set_results` guarda la ronda y `publish()` envía por SSE dos estados: el del presentador, con nombres, latencia, costo y chrF++; y el del validador, a ciegas (`Round.blind`). El teléfono vota con `POST /api/rounds/{id}/verdicts` y el marcador (`RoundStore.scoreboard`) se actualiza al instante.

`make eval` usa exactamente la misma función `translate` con cada variante (`evals/run_eval.py`), pero puntúa con chrF++ a nivel corpus en vez de por oración.

## 12. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
| --- | --- | --- |
| La vista del presentador dice "Solo desde la laptop del presentador" o las rondas responden 403 | Se abrió con la IP de la LAN en vez de `127.0.0.1` | Abre `http://127.0.0.1:8787/presentador/` en la laptop; el teléfono usa el QR |
| El teléfono dice "Esta traducción ya tiene veredicto" | Una traducción acepta un solo veredicto por ronda | Es lo esperado; espera la siguiente ronda en vivo |
| `!! el índice de recuperación es del dataset …` al arrancar, o `make eval` se niega a correr | El índice se construyó con otra versión del dataset | `make index` |
| `!! David (tzij-2026-10-raft-bt-s3) no está en Ollama` al hacer `make up` | El modelo no está descargado | `make pull-model TAG=tzij-2026-10-raft-bt-s3` (o `LOCAL_MODEL_TAG=gemma4:e4b` y `ollama pull gemma4:e4b`) |
| David responde "índice de recuperación no disponible" | Falta `rag/index/tzij.sqlite`, o el servicio lo desactivó al arrancar (`!! retrieval disabled` en la consola) | `make index`; reinicia `make up` |
| `index built with 'X' but queries use 'Y'` | El índice se construyó con otro `EMBEDDING_MODEL` | `make index` con el modelo de `.env` |
| David responde `recuperación: …` | Ollama no responde a `/api/embed` (EmbeddingGemma no está o Ollama se cayó) | `ollama pull embeddinggemma`; `curl 127.0.0.1:11434/api/version` |
| La primera ronda tarda varios segundos | Modelo frío, o `num_ctx` distinto al de la precarga (fuerza una recarga) | Usa `make up` (precarga); no cambies `OLLAMA_NUM_CTX` en caliente |
| Goliath sale "Sin conexión" con internet | `FORCE_OFFLINE=1` o el interruptor de ensayo activado; o la red bloquea `aiplatform.googleapis.com:443` | Revisa `.env` y la barra de comandos; prueba `nc -z aiplatform.googleapis.com 443` |
| Goliath sale con error (no "sin conexión") | ADC vencido, permisos de Vertex AI o timeout de 20 s | `gcloud auth application-default login`; revisa `GEMINI_MODEL` |
| `/` responde `Web views not built: run make web` | Falta `web/out/` | `make web` (con internet, por las tipografías) |
| El teléfono no abre el QR | Otra red, aislamiento de clientes, firewall de macOS o IP equivocada | Misma red; permite Python en el firewall; fija `PUBLIC_URL` |
| `make emulator` no encuentra la pestaña o falla por más de 1 s | Serial equivocado, Chrome sin abrir, o pestañas viejas con conexiones SSE abiertas | `adb devices`; `make emulator ANDROID_SERIAL=…`; el script cierra las pestañas viejas, vuelve a correrlo |
| "Hay una ronda en curso." (409) | La ronda anterior sigue traduciendo | Espera a que termine |
| "No quedan frases de evaluación en esta dirección." (404) | Se usaron todas, o `REQUIRE_VALIDATED_TEST=1` sin pares validados | `make reset`, cambia de dirección (`D`) o aplica la revisión nativa |
| `bouquet: skipped (needs HF_TOKEN …)` en el pipeline | No hay token ni acceso al secreto | §4: acepta los términos, crea `hf-token`, vuelve a correr `infra/10-data-job.sh` para dar acceso a la cuenta de servicio |
| Errores 429 de Hugging Face en Cloud Run | Descargas anónimas desde IPs compartidas | Mismo arreglo: el token |
| `make train` termina en `JOB_STATE_FAILED` por memoria | Esperado con E4B: el entrenamiento terminó, el merge no cabe en 32 GiB | Revisa `train/runs/<tag>.json` (`training: succeeded`) y corre `make train-finish TAG=…` |
| El job de entrenamiento no termina en 1 h | Demasiadas épocas para el límite de GPU de Cloud Run | `TRAIN_ARGS="--epochs=1"` |
| `make eval` termina con `No retrieval index` / `No dataset` | Falta `make index` / `make data-pull` | Córrelos primero |

## 13. Checklist del día de la charla

**La semana anterior**

- [ ] `git pull`, `uv sync`, `make test` en verde.
- [ ] Dataset y modelos al día: `make data-pull`, `make index`, `ollama list` (con `LOCAL_MODEL_TAG` y `embeddinggemma`).
- [ ] `LOCAL_MODEL_TAG` coincide con la mejor variante local de `evals/report.md`.
- [ ] Precios de Gemini en `.env` vigentes para la fecha de la charla. Desde el 1 de enero de 2027: `GEMINI_INPUT_USD_PER_M=1.50`, `GEMINI_OUTPUT_USD_PER_M=7.50`.
- [ ] (Opcional) Si hubo revisión nativa, aplicarla con `make apply-review`. No es requisito: el conjunto de prueba ya está `auto_validated`.
- [ ] `make web` con internet (tipografías) y `make emulator` en verde (voto en menos de 1 s).

**El día, con internet**

- [ ] `gcloud auth application-default print-access-token` funciona (ADC vigente).
- [ ] Energía conectada; suspensión desactivada (`caffeinate -dims` en una terminal); No Molestar activado; pantalla a 1920×1080.
- [ ] `make up`. Sin avisos `!!`. La pastilla dice "En línea".
- [ ] Una ronda de evaluación (`E`) y una en vivo (`/`): David y Goliath responden y se ven latencia y costo.
- [ ] (Opcional, solo si hay validador) El teléfono escanea el QR, vota, y el voto aparece en la pantalla.

**Prueba con el Wi-Fi apagado (obligatoria)**

- [ ] Apaga el Wi-Fi de la laptop. En pocos segundos (el sondeo corre cada 3 s) la pastilla cambia a "Sin conexión".
- [ ] Ronda de evaluación: David traduce con latencia normal y Goliath muestra "Sin conexión". Ninguna pantalla se queda colgada.
- [ ] Ronda en vivo con una frase en español: David responde.
- [ ] Recarga `/presentador/`: carga completa, con tipografías, sin internet.
- [ ] (Opcional) Si el teléfono va a votar durante el segmento sin internet, comprueba que la LAN sigue en pie (router o hotspot sin salida a internet). Si no, usa el interruptor "Simular sin Wi-Fi", que deja la LAN intacta.
- [ ] Vuelve a encender el Wi-Fi y comprueba que la pastilla regresa a "En línea".

**Justo antes de empezar**

- [ ] `make reset` (marcador en cero).
- [ ] El interruptor "Simular sin Wi-Fi" está apagado.
- [ ] Pestaña del presentador en pantalla completa; la barra de comandos cerrada (`Esc`).
- [ ] Plan B si se cae la red del evento: el segmento sin internet *es* la demo. David sigue traduciendo.
