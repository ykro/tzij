# Comandos

Todo corre en Google Cloud; los comandos de `make` despliegan, entrenan y miden. `make help` los lista con su descripción. Volver al [README](../README.md). [English version](COMANDOS.en.md).

## La demo

No hay que correr nada el día de la charla: la página está en Cloud Run. `make page-url` imprime su dirección. Ábrela unos minutos antes: despierta a David y dice «David listo» cuando puede traducir. El guion está en [DEMO.md](DEMO.md).

## Desplegar

Requisitos y detalles en [ONBOARDING.md](ONBOARDING.md). Con Python 3.12, `uv`, Node 24 y `gcloud` instalados:

```bash
cp .env.example .env                       # modelos, buckets y regiones; nunca se sube .env
uv sync                                    # dependencias de Python
gcloud auth login && gcloud auth application-default login
make deploy                                # proyecto, jobs de datos y de entrenamiento, David (GPU) y la página
make page-url                              # la dirección pública de la página
```

Ningún modelo se baja a la laptop: el GGUF de David y EmbeddingGemma viajan del bucket a la imagen de David en Cloud Build.

## Medir contra el David de la nube

`make eval`, `make tune-retrieval`, `make niche` y `make index` hablan con Ollama en `OLLAMA_URL`. Para que usen el David de la nube, abre antes un túnel autenticado y déjalo corriendo:

```bash
make david-proxy          # terminal 1: el Ollama de tzij-david en http://127.0.0.1:11435
make data-pull            # terminal 2: el dataset de la nube (datos, no modelos)
make eval                 # evals/report.md
```

## Todos los comandos

| Comando | Qué hace |
| --- | --- |
| `make help` | Lista los comandos. |
| `make deploy` | Todo en la nube: prepara el proyecto (APIs, Artifact Registry, buckets, secreto `hf-token`, `infra/00-project.sh`), despliega el Cloud Run Job de datos, el de entrenamiento con su imagen, el servicio de David con GPU (`infra/20-david.sh`) y la página (`infra/21-page.sh`). |
| `make deploy-david` | Reconstruye y despliega el servicio de David: imagen con Ollama, `LOCAL_MODEL_TAG` (del bucket de modelos), EmbeddingGemma, el índice del dataset de `LATEST` (del bucket de datos) y el código; la corre una vez en un Cloud Run Job con una L4 para que CUDA compile sus kernels, y despliega la imagen con ellos (unos 30 minutos en total). Después de un modelo o un índice nuevo. `MODEL_TAG=…` despliega otro modelo publicado. |
| `make deploy-page` | Reconstruye y despliega la página (`web/` y su servicio). |
| `make page-url` | Imprime la dirección pública de la página. |
| `make david-proxy` | Abre el Ollama del David de la nube en `127.0.0.1:11435` (`DAVID_PROXY_PORT`; no choca con un Ollama instalado en la laptop, que usa 11434) con tu cuenta de `gcloud` (`gcloud run services proxy`). Lo usan las mediciones y `make index`. |
| `make examples` | Revisa las frases de ejemplo de la página (`duel/examples.json`) contra el David de la nube y Goliath: cada una se traduce 3 veces con los dos; queda si las 3 veces David saca chrF++ de 50 o más contra la traducción correcta y por lo menos 15 puntos más que Goliath. `IDS=…` prueba otras frases de `test_niche` y guarda las que pasan. |
| `make screens` | Capturas de la página en vivo para [DEMO.md](DEMO.md), a 1920×1080 (proyector), 1280×800, 768×1024 (tableta), 414×896 y 375×812 (teléfonos): David despertando, la página lista, un ejemplo y una frase escrita. Falla si una columna no se llena o si la página se sale de lado de la pantalla. |
| `make data` | Corre el pipeline de datos en local: descarga, limpia, normaliza, deduplica, etiqueta dominios y separa por fuente. Escribe en `data/processed/<versión>/` y regenera `data/DATASHEET.md`. |
| `make data-cloud` | Corre el mismo pipeline como Cloud Run Job (`infra/10-data-job.sh`) y escribe un dataset versionado en `gs://…-tzij-data/datasets/`. |
| `make data-pull` | Baja el último dataset que produjo el job. |
| `make index` | Construye `rag/index/tzij.sqlite` solo con el split `train`, con EmbeddingGemma del David de la nube (`make david-proxy`), y lo publica en `gs://…-tzij-data/index/<dataset>/`. David lo usa después de `make deploy-david`. |
| `make niche-data` | Construye el índice. Si `LATEST` no tiene `test_niche.jsonl` (un dataset nuevo de `make data` o `make data-cloud`), antes aparta Firefox Focus del dataset base `20261002-022500` como `test_niche.jsonl` y lo saca de train (`python -m pipeline.niche build`). El dataset publicado, `20261002-173447`, ya lo trae. |
| `make review-test` | (Opcional) Exporta el conjunto de prueba a `data/review/test_review_<versión>.csv` para una revisión nativa. |
| `make apply-review REVIEW_CSV=…` | Aplica las decisiones de la revisión (`ok` / `fix` / `reject`) al conjunto de prueba. |
| `make fertility` | Mide la fertilidad de tokens de K'iche' vs español y escribe `evals/fertility.md`. |
| `make datasheet` | Vuelve a generar `data/DATASHEET.md` desde el último manifest. |
| `make tune-retrieval` | Ajusta la recuperación (modo, k, orden, glosario difuso) solo con el split dev y escribe `evals/tuning.md`. |
| `make eval [EVAL_ARGS=…]` | Compara las variantes disponibles y escribe `evals/report.md`. Con `EVAL_ARGS="--split dev_domain --out evals/dev_domain_report.md"` mide en el split `dev_domain` (párrafos de BOUQuET y páginas de Bloom fuera de la muestra de prueba), donde se toman las decisiones entre ejecuciones. |
| `make niche RUN=niche DAVID=<variante>` | David contra Goliath en el nicho (producto de Pontoon apartado, memoria de traducción): `evals/niche_results.md`. |
| `make human-eval-sheet` | Genera una hoja de evaluación humana a ciegas (50 frases) de la última ejecución; `VARIANTS="tzij-2026-10-mix-s7+hybrid+mbr4,gemini-3.8-flash"` elige variantes. |
| `make train-data` | Los datos del David de la página: RAFT (contexto recuperado en cada prompt, sin el propio par), retrotraducción en las dos direcciones, los primeros 2,409 pares destilados y el 30 % de los pares web: `data/train/chat-raft-bt-both-dst2409-new30.jsonl` (el `TRAIN_DATA` por defecto). |
| `make train-data-raft` | Solo los pares de `train` en RAFT: `data/train/chat-raft.jsonl`. |
| `make monolingual` | K'iche' monolingüe con licencia, solo de fuentes de entrenamiento (incluye los libros de Bloom solo en K'iche'): `data/monolingual/quc.jsonl`. |
| `make back-translate` | Gemini traduce ese K'iche' al español una sola vez y registra el costo: `data/train/back_translated_gemini.jsonl`. |
| `make train-data-raft-bt` | Datos RAFT + pares retrotraducidos (solo español → K'iche'): `data/train/chat-raft-bt.jsonl`. |
| `make distill [LIMIT=N]` | Destilación en los dominios de la prueba: Gemini escribe español cotidiano y lo traduce al K'iche' con el contexto recuperado de David; solo quedan los pares que pasan el alfabeto de la ALMG, la longitud y la ida y vuelta. Escribe `data/train/distilled/` (los rechazos en `rejected.jsonl`, para no pagarlos dos veces). Solo entrenamiento ([bitácora, sección 11](BITACORA.md)). |
| `make train TAG=tzij-AAAA-MM [TRAIN_ARGS=…]` | Fine-tune LoRA de `TRAIN_DATA` como Cloud Run Job con una L4. Registra duración y costo en `train/runs/<tag>.json`. La receta en trozos del David de la página es `train/chain.sh` ([ONBOARDING, sección 6.4](ONBOARDING.md)). |
| `make train-finish TAG=…` | Merge y GGUF del adaptador de E4B en una VM de Cloud Batch con 64 GB de RAM y 200 GB de disco (`infra/04-finish-batch.sh`), y lo publica en el bucket de modelos. La VM se borra al terminar. |
| `make test` | Pruebas de Python (`MOCK_AI=1`, sin red, sin GPU) y de la web (`tsc` y vitest). |
