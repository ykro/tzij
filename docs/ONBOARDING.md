# Onboarding — Tzij

Guía para montar Tzij desde cero en Google Cloud, preparar los datos y los modelos, medir y llegar al día de la charla sin sorpresas. Todo corre en la nube: en la laptop no corre ningún modelo. La visión general está en el [README](../README.md) y las decisiones técnicas en [DECISIONES.md](DECISIONES.md).

Contenido:

1. [Requisitos](#1-requisitos)
2. [Instalación](#2-instalación)
3. [Credenciales: ADC y el token de Hugging Face](#3-credenciales-adc-y-el-token-de-hugging-face)
4. [Google Cloud: `make deploy` y los scripts `infra/`](#4-google-cloud-make-deploy-y-los-scripts-infra)
5. [Datos, índice, entrenamiento y evaluación](#5-datos-índice-entrenamiento-y-evaluación)
6. [La página y David en la nube](#6-la-página-y-david-en-la-nube)
7. [Las frases de ejemplo](#7-las-frases-de-ejemplo)
8. [Revisión con hablantes nativos (opcional)](#8-revisión-con-hablantes-nativos-opcional)
9. [Pruebas](#9-pruebas)
10. [Recorrido por el código: una traducción](#10-recorrido-por-el-código-una-traducción)
11. [Solución de problemas](#11-solución-de-problemas)
12. [El día de la charla](#12-el-día-de-la-charla)

![Pipeline: datos, entrenamiento y evaluación](diagrams/pipeline.png)

## 1. Requisitos

Versiones con las que se verificó el proyecto (6 de octubre de 2026):

| Herramienta | Versión | Para qué |
| --- | --- | --- |
| Python | 3.12 (`.python-version`; `pyproject.toml` pide `>=3.12,<3.13`) | Pipeline, servicios, evals y pruebas |
| uv | 0.8.22 | Entornos y dependencias de Python. Nunca `pip` global. |
| Node.js / npm | 24.21.0 / 12.0.2 | La página en Next.js 16.3.8 y sus pruebas (vitest, Playwright 1.63.0 para `make screens`) |
| Google Cloud SDK (`gcloud`) | 587.0.0 | ADC, Cloud Run, Cloud Build, Cloud Batch, Cloud Storage, Secret Manager |
| Cuenta de Hugging Face | — | Aceptar los términos de BOUQuET; su token va a Secret Manager |
| Cuota de GPU | 1× NVIDIA L4 sin redundancia zonal en `europe-west4` (Cloud Run) | David y el entrenamiento. El proyecto tiene 4. |

No hace falta Ollama, Docker ni una GPU local: las imágenes se construyen con Cloud Build y los modelos viajan del bucket a la imagen de David sin pasar por la laptop.

## 2. Instalación

```bash
git clone <repo> tzij && cd tzij
cp .env.example .env        # .env está en .gitignore; nunca subas un token
uv sync                     # crea .venv con Python 3.12 y las dependencias (incluye pytest)
cd web && npm ci && cd ..   # para las pruebas de la página y `make screens`
```

Todo se configura en `.env`; el `Makefile` lo carga y exporta. Las variables más importantes:

| Variable | Valor actual | Qué controla |
| --- | --- | --- |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Goliath |
| `GEMINI_INPUT_USD_PER_M` / `GEMINI_OUTPUT_USD_PER_M` | `0.75` / `3.75` | Costo de Gemini en los reportes de `make eval`. Desde el 1 de enero de 2027 la tarifa de lista sube a `1.50` / `7.50`. |
| `LOCAL_MODEL_TAG` | `tzij-2026-10-mix-s7` | David (siempre con recuperación): el modelo que `infra/20-david.sh` mete en la imagen de David |
| `FINETUNED_MODEL_TAGS`, `BASE_MODEL_TAGS` | `tzij-2026-10-mix-s7`, vacío | Lo que compara `make eval`; tiene que estar en la imagen de David |
| `GEMMA_BASE_MODEL` | `gemma-4-E4B-it` | Checkpoint base del fine-tune y tokenizador de `make fertility` |
| `EMBEDDING_MODEL` | `embeddinggemma` | Embeddings del índice. El índice y las consultas tienen que usar el mismo. |
| `RAG_INDEX`, `RAG_K` | `rag/index/tzij.sqlite`, `6` | Índice y cuántos ejemplos y entradas de glosario recibe David |
| `RAG_MODE`, `RAG_ORDER`, `RAG_FUZZY` | `hybrid`, `best_last`, `1` | Búsqueda híbrida BM25 + vectores, ejemplo más cercano al final, glosario difuso. Ajustados con `make tune-retrieval` en dev. |
| `DAVID_MBR`, `MBR_SAMPLES` | `1`, `4` | Decodificación MBR en el servicio de David (`0` = una sola muestra) |
| `OLLAMA_URL`, `OLLAMA_NUM_CTX` | `http://127.0.0.1:11434`, `4096` | Dónde está Ollama dentro del servicio de David. En tu máquina el Makefile lo cambia a `http://127.0.0.1:11435` (`DAVID_PROXY_PORT`), donde `make david-proxy` abre el David de la nube y el contexto de Gemma |
| `TRAIN_FINISH` | `later` | El job de GPU solo entrena el adapter; el merge de E4B corre con `make train-finish` en Cloud Batch |
| `MOCK_AI` | `0` | `1` evita la nube y la GPU (pruebas) |

`.env` solo pone valores por defecto: lo que pases por la línea de comandos o el entorno gana. El `Makefile` convierte cada `CLAVE=valor` de `.env` en `CLAVE ?= valor` (archivo `.env.mk`, ignorado por git).

## 3. Credenciales: ADC y el token de Hugging Face

### ADC

No hay claves de API en el repo. Gemini (Vertex AI), Cloud Storage y Secret Manager usan Application Default Credentials, y `make examples`, `make eval` y `make david-proxy` usan tu cuenta de `gcloud` para llamar al David privado:

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

## 4. Google Cloud: `make deploy` y los scripts `infra/`

Proyecto: `ai-experiments-487722`. El job de datos vive en `us-central1` y las imágenes en el Artifact Registry `charlas2027` (`us-central1`). David, la página, el entrenamiento y el merge corren en `europe-west4`, donde el proyecto tiene la cuota de L4.

### 4.1 Todo desde cero: `make deploy`

```bash
HF_TOKEN=hf_... make deploy   # HF_TOKEN solo la primera vez, para crear el secreto hf-token
make page-url                 # la dirección pública de la página
```

`make deploy`, en este orden: `infra/00-project.sh` (habilita las APIs, crea el Artifact Registry `charlas2027`, los buckets `…-tzij-data`, `…-tzij-models` y `…-train-eu`, y el secreto `hf-token` si le pasas `HF_TOKEN`), el Cloud Run Job de datos sin ejecutarlo (`DEPLOY_ONLY=1 infra/10-data-job.sh`), la cuenta de servicio de entrenamiento, el Cloud Run Job `tzij-train` con su imagen, el servicio de David (`infra/20-david.sh`) y la página (`infra/21-page.sh`). Todo es idempotente: se puede volver a correr.

Lo único que no se puede automatizar: aceptar los términos de BOUQuET con tu cuenta de Hugging Face (antes de crear el token) y la cuota de L4 para Cloud Run en `europe-west4`.

### 4.2 Los scripts

Todos cargan `infra/env.sh` (proyecto, regiones, Artifact Registry, nombres de servicio) e `infra/app.env` (`APP=tzij`).

| Script | Qué hace | ¿Quién lo llama? |
| --- | --- | --- |
| `infra/00-project.sh` | Habilita APIs; crea Artifact Registry, los tres buckets y el secreto `hf-token` (si recibe `HF_TOKEN`). | `make deploy` |
| `infra/01-train-service-account.sh` | Crea la cuenta de servicio `tzij-train` con acceso al bucket de modelos, al de staging, a Artifact Registry y a `hf-token`. | `make deploy` |
| `infra/02-train-image.sh` | Construye la imagen de entrenamiento con Cloud Build. La etiqueta es un hash del `Dockerfile`, `requirements.txt`, `train_lora.py` y `finish.py`, así que una receta sin cambios no se reconstruye (la primera vez tarda unos 15 min). | `make train`, `make train-finish` |
| `infra/03-train-job.sh` | Crea o actualiza los Cloud Run Jobs `tzij-train` (1× L4, 8 vCPU, 32 GiB, 1 h) y `tzij-finish` (CPU), con el bucket de staging montado en `/mnt/work` (caché de pesos base). | `make deploy`, `make train` |
| `infra/04-finish-batch.sh <tag>` | Merge + GGUF de un adapter de E4B en una VM de Cloud Batch (`n2-highmem-8`, 64 GB, 200 GB de disco) con la imagen de entrenamiento; publica en el bucket de modelos y la VM se borra al terminar. Habilita la API de Batch y da a `tzij-train` los roles que necesita. | `make train-finish` |
| `infra/10-data-job.sh` | Crea la cuenta de servicio `tzij-data-job` con acceso solo al bucket de datos (y a `hf-token`), construye la imagen (`pipeline/cloudbuild.yaml`), despliega el job `tzij-data` (2 vCPU, 4 GiB, 1 h) y lo ejecuta (con `DEPLOY_ONLY=1`, solo despliega). | `make data-cloud`, `make deploy` |
| `infra/20-david.sh` | Crea la cuenta de servicio `tzij-david` (sin acceso a nada) y, en tres pasos: (1) construye con Cloud Build la imagen base de David (`david/cloudbuild.yaml`: copia el GGUF y el Modelfile de `LOCAL_MODEL_TAG` del bucket de modelos, y del bucket de datos el índice y los pares de prueba con licencia del dataset de `LATEST`; `ollama create` y `ollama pull embeddinggemma` dentro de la imagen); (2) la corre una vez en el Cloud Run Job `tzij-david-warm` con una L4 (`david/warm_cache.py`), que hace que CUDA compile sus kernels y los sube a `gs://…-train-eu/tzij/david-cache/`; (3) construye la imagen final con esos kernels (`david/cloudbuild-cache.yaml`) y despliega `tzij-david`: 1× L4, 4 vCPU, 16 GiB, mínimo 0 y máximo 1 instancia, privado. Las imágenes van a Artifact Registry de `europe-west4`, junto al servicio. Unos 30 minutos. | `make deploy`, `make deploy-david` |
| `infra/21-page.sh` | Crea la cuenta de servicio `tzij-page` con `aiplatform.user` y `run.invoker` sobre `tzij-david`, construye la imagen de la página (`page/Dockerfile`: compila `web/` y le pone el servicio de Python) y despliega `tzij`, pública, con `DAVID_URL`. | `make deploy`, `make deploy-page` |

## 5. Datos, índice, entrenamiento y evaluación

### 5.1 `make data` o `make data-cloud`

```bash
make data-cloud   # recomendado: Cloud Run Job → gs://…-tzij-data/datasets/<versión>/ + LATEST
make data-pull    # lo baja a data/processed/<versión>/ y actualiza data/processed/LATEST
# o, el mismo pipeline en tu máquina (solo datos, ningún modelo):
make data         # descarga a data/raw/, escribe data/processed/<versión>/ y data/DATASHEET.md
```

`make data-pull` baja el dataset publicado, `20261002-173447`, que ya trae `test_niche.jsonl` (Firefox Focus fuera de train y del índice, más los glosarios de CLDR y FLORES-Mayas). Con un dataset nuevo sin `test_niche.jsonl` (de `make data` o `make data-cloud`), `make niche-data` primero corre `python -m pipeline.niche build` sobre el dataset base `20261002-022500` y crea una versión nueva.

El pipeline (`pipeline/run.py`) hace: descarga por fuente (`pipeline/sources/*.py`, con caché cruda) → normalización (`data/normalize.py`) → limpieza con motivo de descarte (`pipeline/clean.py`) → etiquetas de dominio → deduplicación → split por fuente con chequeo de fugas y tope religioso (`pipeline/split.py`) → `train.jsonl` / `dev.jsonl` / `test.jsonl` (un registro por par y dirección) → `manifest.json` y datasheet. El job escribe el datasheet junto al dataset en GCS; para regenerar el del repo, usa `make datasheet` después de `make data-pull`.

Dataset actual: `20261002-173447` (derivado de `20261002-022500` con `make niche-data`). Train 8,453 pares (2,541 oraciones y 5,912 entradas de diccionario y glosario), dev 115, prueba 1,654 (300 de Bloom, 1,354 de BOUQuET), nicho 144 (Firefox Focus, solo español → Kʼicheʼ). Proporción religiosa en las oraciones de train: 30.0 %.

### 5.2 `make index`

```bash
make david-proxy   # en otra terminal: el Ollama del David de la nube en 127.0.0.1:11435
make index         # construye rag/index/tzij.sqlite y lo publica en gs://…-tzij-data/index/<dataset>/
make deploy-david  # la imagen nueva de David lleva el índice nuevo
```

Indexa solo el split `train` (`pipeline.split.RETRIEVAL_SPLITS`) y se niega a indexar cualquier otro. Guarda el modelo de embeddings y la versión del dataset dentro del índice. El índice actual es del dataset `20261002-173447` y tiene 16,906 entradas (8,453 por dirección). Los embeddings se cachean en `rag/.cache/embeddings.sqlite`, así que reconstruir es rápido.

### 5.3 `make fertility` (opcional)

Mide tokens por palabra con el `tokenizer.json` de `google/<GEMMA_BASE_MODEL>`. Escribe `evals/fertility.md`, que `make eval` copia dentro del reporte.

### 5.4 `make train`

```bash
make train TAG=tzij-YYYY-MM TRAIN_ARGS="…"   # una tarea de Cloud Run con TRAIN_DATA; los argumentos van a train/train_lora.py
```

Sin `TRAIN_DATA`, `make train` entrena con los datos del David de la página (`data/train/chat-raft-bt-both-dst2409-new30.jsonl`, que arma `make train-data` si falta). La receta completa de `tzij-2026-10-mix-s7`, con los 8 trozos encadenados, está más abajo.

El primer David ajustado (`tzij-2026-10-raft-bt-s3`) se entrenó con RAFT + retrotraducción, en 4 trozos de 1/4 de época para no pasar el límite de 1 h:

```bash
make monolingual && make back-translate   # una vez: 405 oraciones → 399 pares, $0.12
make train-data-raft-bt                   # 5,579 ejemplos con contexto recuperado
A="--epochs=1 --batch-size=2 --grad-accum=8 --max-length=1024"
make train TAG=tzij-2026-10-raft-bt-s0 TRAIN_DATA=data/train/chat-raft-bt.jsonl TRAIN_ARGS="$A --shard=0/4"
make train TAG=tzij-2026-10-raft-bt-s1 TRAIN_DATA=data/train/chat-raft-bt.jsonl \
  TRAIN_ARGS="$A --shard=1/4 --init-adapter=gs://…-train-eu/tzij/runs/tzij-2026-10-raft-bt-s0/adapter"
# … igual para s2 y s3; después make train-finish TAG=tzij-2026-10-raft-bt-s3
```

El David actual (`tzij-2026-10-mix-s7`) continúa el adaptador `tzij-2026-10-tm-a-e2-s4` (2 épocas, sin Firefox Focus) con datos en el dominio de la prueba ([bitácora, sección 11](BITACORA.md)):

```bash
make monolingual && make back-translate   # incluye los libros de Bloom solo en K'iche' (1,998 pares nuevos)
make distill                              # español de Gemini → K'iche' filtrado: data/train/distilled/
make train-data   # = python -m pipeline.train_set --raft --bt --bt-both --distilled 2409 --only-new 0.3
#   → data/train/chat-raft-bt-both-dst2409-new30.jsonl: datos nuevos en las dos direcciones + 30 % de los pares web
#   (--distilled 2409 = los primeros 2,409 pares de pairs.jsonl: la primera tanda, `make distill LIMIT=6000`)
train/chain.sh tzij-2026-10-mix data/train/chat-raft-bt-both-dst2409-new30.jsonl 0 7 8 tzij-2026-10-tm-a-e2-s4 --seed=2031
#   → 8 jobs de Cloud Run (uno por octavo), cada uno sigue el adapter del anterior
make train-finish TAG=tzij-2026-10-mix-s7
```

Los hiperparámetros de cada trozo quedan en `train/runs/<tag>.json`. Las decisiones entre ejecuciones se toman con `make eval EVAL_ARGS="--split dev_domain --out evals/dev_domain_report.md"`, no con la prueba.

1. `make train-data` arma los datos del David de la página: el 30 % de los pares web de `train`, la retrotraducción en las dos direcciones y los primeros 2,409 pares destilados, cada uno con el mismo prompt y el mismo contexto recuperado que recibe David al traducir (RAFT). Vuelve a comprobar el tope religioso. Salen 10,692 ejemplos. (Sin `--raft`, `python -m pipeline.train_set` arma la versión sin contexto de `tzij-2026-09`, el callejón sin salida de la [bitácora, sección 2](BITACORA.md).)
2. `train/submit_job.py` sube el JSONL a `gs://…-train-eu/tzij/data/<tag>/`, construye o reutiliza la imagen (`02`), actualiza el job (`03`), lo ejecuta con `--epochs`, etc., espera y escribe `train/runs/<tag>.json` con duración, máquina y costo estimado.
3. Dentro del job, `train/train_lora.py` baja los pesos (`GEMMA_WEIGHTS_URI=hf://google`, con caché en el bucket), entrena la LoRA (r=16, alpha=32, lr 2e-4, solo el decodificador de texto) y guarda el adapter en el volumen.

Límites que hay que respetar: **1 h por tarea de GPU** en Cloud Run (por eso se usa `--epochs=1`; 1.5 épocas no cabían) y **32 GiB** de memoria (por eso el merge de E4B no cabe en el job). La ejecución `tzij-2026-09` entrenó bien (324 pasos, 22 min) y después el job terminó con *"The configured memory limit was reached"* al guardar el modelo fusionado. Por eso `.env` trae `TRAIN_FINISH=later`: el job de GPU solo entrena el adapter y el merge corre con `make train-finish` (§5.5).

### 5.5 `make train-finish`

```bash
make train-finish TAG=tzij-2026-10-mix-s7   # adapter del bucket → merge → GGUF → Q4_K_M → gs://…-tzij-models/<tag>/
make deploy-david MODEL_TAG=tzij-2026-10-mix-s7   # o pon el tag en LOCAL_MODEL_TAG y `make deploy-david`
```

`train-finish` corre `train/finish.py` en una VM de Cloud Batch (`infra/04-finish-batch.sh`): baja los pesos base de la caché del bucket, hace el merge, convierte a GGUF f16 en disco y cuantiza a Q4_K_M (unos 5.3 GB). Tarda unos 10 minutos y la VM se borra sola. El `Modelfile` usa el renderer y el parser de `gemma4`, así que el modelo ajustado se pide igual que su base.

### 5.6 `make eval`

```bash
make david-proxy                                      # en otra terminal, mientras corren las mediciones
make eval                                             # todas las variantes de .env, 150 pares por fuente y dirección
make eval EVAL_ARGS="--limit 20"                      # prueba rápida
make eval EVAL_ARGS="--run final-20261002 --only tzij-2026-10-mix-s7+hybrid+mbr4"  # agrega variantes a una ejecución
make eval EVAL_ARGS="--split dev_domain --run dev-domain --out evals/dev_domain_report.md"  # decisiones en el dominio de la prueba, sin tocarla
```

Necesita ADC para las variantes de Gemini y, en el Ollama del David de la nube, los tags de `BASE_MODEL_TAGS` y `FINETUNED_MODEL_TAGS` (la imagen de David trae `LOCAL_MODEL_TAG` y `embeddinggemma`). Las predicciones se guardan en `evals/runs/<run>/<variante>.jsonl`, así que una ejecución interrumpida se retoma con `--run`. Las latencias de un `make eval` son de la GPU de la nube más el viaje por el túnel; las de `final-20261002` se midieron en una laptop. Si cambias de David, revisa también los ejemplos con `make examples`.

## 6. La página y David en la nube

La página (`make page-url`) tiene:

- **El cuadro para escribir** y el botón **Traducir** (o `Enter`). El botón ⇄ cambia la dirección: español → Kʼicheʼ o Kʼicheʼ → español.
- **Las frases de ejemplo** de Firefox Focus (`duel/examples.json`). Al tocar una, se llena el cuadro, se traduce y arriba aparece la traducción correcta, con su fuente y su licencia.
- **Dos columnas:** David y Goliath. Cada una pide su traducción por separado (`POST /api/translate` con `side`) y se llena en cuanto su modelo responde, con lo que tardó y lo que costó esa traducción (`cost` en la respuesta: los segundos de GPU de David × `DAVID_*_USD_PER_S`, o los tokens de Gemini × el precio del día, `GEMINI_NEXT_PRICE`). En los ejemplos, cada columna muestra además «Se parece a la correcta»: chrF++ contra la traducción correcta, en porcentaje.
- **Una frase escrita:** el servicio de la página le pregunta a David (`POST /reference`) si la frase está, tal cual, en los pares de prueba con licencia (`rag/index/references.jsonl` en su imagen, sin BOUQuET), en su memoria de traducción o en el diccionario; si está, se mide como un ejemplo. Si no, cuando las dos columnas terminan la página pide `POST /api/evidence` (David, `duel/tzij_duel/evidence.py`): las 3 frases más parecidas de la memoria de traducción y, por columna, qué palabras aparecen también en esas traducciones hechas por personas.
- **En teléfonos y tabletas:** una sola columna, David arriba; los ejemplos se deslizan de lado. `make screens` toma capturas en 1920×1080, 1280×800, 768×1024, 414×896 y 375×812, y falla si la página se sale de lado de la pantalla.

Las traducciones no se guardan en ningún lado.

**Límites de costo** (`duel/tzij_duel/limits.py`): por IP, 30 traducciones y 40 consultas de estado por minuto (si se pasan, la página lo dice: «espera un momento»); por día, 2,000 llamadas a Gemini y 12 encendidas de David (después, la columna dice que se acabaron por hoy); y una pestaña abierta deja de mantener despierto a David 45 minutos después de su última traducción: la página dice «David descansa» y la siguiente traducción lo despierta. Se cambian con `LIMIT_TRANSLATE_PER_MIN`, `LIMIT_CHECKS_PER_MIN`, `LIMIT_GEMINI_PER_DAY`, `LIMIT_DAVID_WAKES_PER_DAY` y `KEEPALIVE_MAX_MIN` en el servicio `tzij`.

**Despertar a David.** `tzij-david` tiene mínimo 0 instancias: la GPU se apaga sola unos 15 minutos después de la última petición, y entonces no cobra. Al abrir la página, el navegador pregunta `GET /api/david` cada 3 s; la página llama a `/health` de David con su token, y esa llamada lo despierta. Mientras arranca (unos 40 s (39 s medido con la GPU apagada; antes, 3 min 24 s) desde la página: la instancia, el modelo de 5.3 GB a la GPU, EmbeddingGemma, el índice y una traducción de prueba; los kernels de GPU ya vienen compilados en la imagen), la página dice «Preparando a David…» y no deja traducir. Cuando David contesta `ready`, dice «David listo». Después pregunta una vez por minuto mientras la pestaña está visible: eso lo mantiene despierto. Si pasan 6 minutos sin que despierte, dice «David no responde: recarga la página».

**Costo.** Mientras está despierto, `tzij-david` cobra $0.0002907 por segundo (L4 + 4 vCPU + 16 GiB), $1.05 por hora, traduzca o no. Cerrar la página deja que se apague solo. La página cobra lo mínimo de Cloud Run y Gemini sus tokens.

**Medir tiempo, costo y capacidad.** `uv run python david/bench.py` traduce los ejemplos 3 veces con los dos y mide cuántas traducciones por hora da la L4 con 1, 2, 4, 8 y 16 frases a la vez; escribe `david/bench-results.json`, de donde salen las proyecciones del README. Para medir sin que otras peticiones (por ejemplo un `make eval`) frenen a David, despliega una copia con la misma imagen (`gcloud run deploy tzij-david-bench --image <imagen de tzij-david> …`, mismas banderas que `infra/20-david.sh`), usa `--david-service tzij-david-bench` y bórrala al terminar.

## 7. Las frases de ejemplo

`make examples` traduce cada ejemplo 3 veces con el David de la nube y con Goliath, como lo hace la página (`Page.side` en `duel/tzij_duel/page.py`, con tu token de `gcloud`), y guarda en `duel/examples.json` solo los que, las 3 veces, David dejó cerca de la traducción correcta (chrF++ de 50 o más) y por lo menos 15 puntos más cerca que Goliath, con las salidas, los puntajes y los tiempos. Con `IDS=pair_id,…` prueba otras frases de `test_niche` (español → Kʼicheʼ). Necesita el dataset (`make data-pull`), no modelos. Después, `make deploy-page`: la página lleva `examples.json` adentro.

## 8. Revisión con hablantes nativos (opcional)

Nada de esta sección es requisito: el conjunto de prueba ya llega `auto_validated` desde el pipeline (`pipeline/validate_test.py`) y la demo corre completa sin intervención humana.

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

### Evaluación humana a ciegas (`evals/human_eval.md`)

Opcional, solo si hay una persona hablante disponible; la demo no depende de ella. 50 frases por modelo, adecuación y fluidez de 1 a 5.

```bash
make eval
make human-eval-sheet VARIANTS="tzij-2026-10-mix-s7+hybrid+mbr4,gemini-3.8-flash"   # RUN=<id> para otra ejecución
# sin VARIANTS incluye todas las variantes de la ejecución
```

Escribe `evals/runs/<run>/human_eval_sheet.csv` (sin nombres de modelo, filas mezcladas) y `human_eval_key.json` (letra → modelo, que no se comparte hasta terminar). `VARIANTS` usa los nombres de variante del reporte (los mismos de `make eval`); si alguno no tiene resultados en la ejecución, el comando lo dice y no genera la hoja. La hoja muestra el texto original, así que aplica la misma regla de privacidad para BOUQuET.

## 9. Pruebas

```bash
make test      # Python (MOCK_AI=1: sin red, sin GPU) + la página (tsc y vitest)
make screens   # usa la página en vivo y deja capturas en docs/demo/ (Playwright)
```

Las pruebas de Python usan modelos simulados: David responde con el mejor ejemplo recuperado de un índice pequeño de pares con licencia (`duel/mock_data/`, embeddings por hashing) y Goliath devuelve el texto de entrada, así que nunca aparece Kʼicheʼ inventado. Cubren la página (`duel/tests/test_page.py`: las dos columnas, cada lado por separado, ejemplos con traducción correcta, David caído, el token de identidad) y el servicio de David (`duel/tests/test_david_service.py`). Las que necesitan Ollama de verdad están marcadas `@pytest.mark.ollama` y se saltan si no hay Ollama.

## 10. Recorrido por el código: una traducción

De tocar un ejemplo a las dos columnas llenas:

1. **Entrada.** La página (`web/app/page.tsx`) hace dos `POST /api/translate`, uno con `side: "david"` y otro con `side: "goliath"`, con `{text, direction, example}`. `Page.translate_text` (`duel/tzij_duel/page.py`) busca el ejemplo en `duel/examples.json` (`examples.py`) para tener la traducción correcta; si el texto ya no es el del ejemplo, lo trata como frase escrita, sin referencia.
2. **David.** `RemoteDavid.translate` (`duel/tzij_duel/remote.py`) pide un token de identidad al servidor de metadatos de Cloud Run y llama a `POST /translate` de `tzij-david`. Ahí, `David.translate` (`duel/tzij_duel/david_app.py`) llama a `translate(variant, …)` (`variants.py`) con el retriever.
3. **Goliath.** La página llama a la misma `translate(variant, …)` con la variante de Gemini, sin retriever.
4. **Normalizar.** `translate` normaliza la entrada con `normalize_kiche` o `normalize_spanish` (`data/normalize.py`): todos los saltillos pasan a `'`, se unifican espacios, comillas y guiones, y se pliegan las vocales con diéresis.
5. **Recuperar (solo David).** `Retriever.retrieve` (`rag/retrieve.py`) combina BM25 (SQLite FTS5) con la búsqueda por vectores de EmbeddingGemma en `sqlite-vec` (`rag/embedder.py`, el Ollama del mismo contenedor), fusionadas con Reciprocal Rank Fusion y filtradas por dirección:
   - **ejemplos:** los `RAG_K` pares de oraciones más cercanos, con el más parecido al final;
   - **glosario:** coincidencias exactas y difusas, y luego las entradas de diccionario más cercanas.

   `as_prompt_context()` arma el bloque `Glosario:` / `Ejemplos:`.
6. **Prompt.** `translation_messages` (`duel/tzij_duel/prompts.py`) arma el mensaje de sistema (traductor cuidadoso, ortografía ALMG, apóstrofo para el saltillo, solo la traducción) y el de usuario. Si hay contexto, le antepone el encabezado del material de referencia.
7. **Modelo.**
   - David: con `DAVID_MBR=1`, `_mbr` pide 4 traducciones a temperatura 0.7 a Ollama (`duel/duel_core/ollama_client.py`, `POST /api/chat`, `num_ctx` 4096; `OLLAMA_NUM_PARALLEL=16` corre a la vez las 4 de cada frase, para hasta 4 frases, en la L4) y se queda con la de mayor chrF++ promedio contra las otras.
   - Goliath: `GeminiClient.complete` (`gemini_client.py`) llama a Vertex AI con `google-genai`, `thinking_level=low` y 20 s de timeout.

   `run_duel` (`duel/duel_core/duel.py`) nunca deja que un modelo que falla tumbe al otro.
8. **Limpiar y medir.** `clean_translation` (`duel_core/prompts.py`) se queda con la primera línea y quita prefijos tipo "Traducción:" y comillas. `normalize_output` aplica la misma normalización que a las referencias. Con un ejemplo, `chrf_pp` (`duel_core/metrics.py`, sacrebleu `CHRF(word_order=2)`) mide contra la traducción correcta: es el «Se parece a la correcta».
9. **Mostrar.** Cada respuesta llena su columna (`Column` en `page.tsx`); los helpers (porcentaje, tiempo, costo, estado de David) están en `web/lib/translator.ts`.

`make eval` usa exactamente la misma función `translate` con cada variante (`evals/run_eval.py`), pero puntúa con chrF++ a nivel corpus en vez de por oración.

## 11. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
| --- | --- | --- |
| La página dice «Preparando a David…» más de 5 minutos | La GPU no arrancó (cuota, o un error en la imagen) | `gcloud run services logs read tzij-david --region europe-west4 --project ai-experiments-487722 --limit 50`; busca `David listo` |
| Una columna dice «No pudo traducir esta frase» | David o Gemini respondieron con error | Logs de `tzij` y de `tzij-david`; para Gemini, permisos de `tzij-page` (`aiplatform.user`) |
| `make examples` o `make eval` dice `DAVID_URL is not set` o 403 | Tu cuenta no puede llamar a `tzij-david`, o falta el servicio | `gcloud auth login`; `make deploy-david` |
| `make eval` o `make index` no conectan a `127.0.0.1:11435` | No está corriendo `make david-proxy` | Ábrelo en otra terminal |
| `index built with 'X' but queries use 'Y'` | El índice se construyó con otro `EMBEDDING_MODEL` | `make index` con el modelo de `.env` y `make deploy-david` |
| `!! Missing gs://…/index/<dataset>/tzij.sqlite` en `infra/20-david.sh` | El dataset de `LATEST` no tiene índice publicado | `make data-pull`, `make david-proxy` y `make index` |
| `bouquet: skipped (needs HF_TOKEN …)` en el pipeline | No hay token ni acceso al secreto | §3: acepta los términos, crea `hf-token`, vuelve a correr `infra/10-data-job.sh` |
| Errores 429 de Hugging Face en Cloud Run | Descargas anónimas desde IPs compartidas | Mismo arreglo: el token |
| `make train` termina en `JOB_STATE_FAILED` por memoria | `TRAIN_FINISH` no es `later` y el merge de E4B no cabe en 32 GiB | `TRAIN_FINISH=later` y `make train-finish TAG=…` |
| El job de entrenamiento no termina en 1 h | Demasiadas épocas para el límite de GPU de Cloud Run | `TRAIN_ARGS="--epochs=1"` o trozos con `train/chain.sh` |
| `make eval` termina con `No retrieval index` / `No dataset` | Falta `make data-pull` / `make index` | Córrelos primero |

## 12. El día de la charla

No hay nada que correr.

- [ ] **Unos 5 minutos antes:** abre la página (`make page-url` imprime la dirección) en Chrome, en pantalla completa (`⌃⌘F`). Espera a que diga «David listo».
- [ ] Toca un ejemplo: las dos columnas se llenan y aparece «Se parece a la correcta».
- [ ] Deja la página abierta durante la charla: así David no se apaga.
- [ ] **Al terminar:** cierra la pestaña. David se apaga solo unos 15 minutos después.

La semana anterior, si cambió algo (otro modelo, otro índice, otros precios de Gemini): `make examples` y `make deploy-page`.
