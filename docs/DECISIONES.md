# Decisiones técnicas

Por qué Tzij está hecho así: el detalle de lo que enseña la demo, cada decisión con lo descartado, los resultados completos de `make eval` y las versiones. La historia iteración por iteración, con lo que no funcionó, está en la [bitácora](BITACORA.md). Volver al [README](../README.md). [English version](DECISIONES.en.md).

## Qué vas a aprender, en detalle

| Lección | Dónde está en el código |
| --- | --- |
| **Datos web con licencia y normalización ortográfica.** Cada registro lleva `origin=web`, URL y licencia. Las fuentes que no lo permiten quedan fuera. Las comillas simples tipográficas, la saltillo `ꞌ`, el `ʼ` y otros caracteres que se usan como saltillo se unifican al apóstrofo ASCII antes de indexar, entrenar o evaluar. | [`data/SOURCES.md`](../data/SOURCES.md) (14 fuentes usadas, 14 a la espera de permiso, 28 rechazadas), [`pipeline/sources/`](../pipeline/sources/), [`data/normalize.py`](../data/normalize.py), [`tests/test_normalize.py`](../tests/test_normalize.py) |
| **Split por fuente, no por oración.** Una fuente entera es de prueba o entera de entrenamiento, y cualquier par de entrenamiento que repita una oración de prueba se descarta. Si las oraciones se repartieran al azar, la evaluación mediría memoria. | [`pipeline/split.py`](../pipeline/split.py), [`pipeline/sources/__init__.py`](../pipeline/sources/__init__.py), [`data/DATASHEET.md`](../data/DATASHEET.md) |
| **Ablación decidida por `make eval`.** Base + vectores → + recuperación híbrida → + fine-tune RAFT con retrotraducción → + MBR → + datos en el dominio de la prueba (retrotraducción de Bloom y destilación), más Gemini con y sin recuperación, sobre las mismas 600 frases. Se ajusta con dev (desde el 4 de octubre, con `dev_domain`: párrafos de BOUQuET y páginas de Bloom fuera de la muestra de prueba) y se mide con prueba una sola vez. Gana la mejor variante local con p50 ≤ 5 s, aunque no sea la que costó más trabajo. | [`evals/run_eval.py`](../evals/run_eval.py), [`evals/tune_retrieval.py`](../evals/tune_retrieval.py), [`duel/tzij_duel/variants.py`](../duel/tzij_duel/variants.py), [`evals/report.md`](../evals/report.md) |
| **Recuperación híbrida.** BM25 (FTS5) para las palabras raras y EmbeddingGemma para el sentido, fusionados con RRF; glosario exacto y difuso; el ejemplo más cercano va al final, junto a la frase. | [`rag/retrieve.py`](../rag/retrieve.py), [`rag/store.py`](../rag/store.py), [`evals/tuning.md`](../evals/tuning.md) |
| **RAFT, retrotraducción y destilación: Goliath enseña una vez.** El fine-tune ve el mismo contexto recuperado que verá en la demo, sin su propia respuesta. Gemini traduce al español K'iche' monolingüe con licencia, y esos pares entrenan las dos direcciones. Además destila: escribe español cotidiano en los dominios de la prueba y lo traduce al K'iche' con el contexto de David, y solo quedan los pares que pasan el alfabeto de la ALMG y la ida y vuelta. Todo se usa solo para entrenar, con origen, modelo, prompt, semilla y costo registrados. | [`pipeline/train_set.py`](../pipeline/train_set.py), [`pipeline/monolingual.py`](../pipeline/monolingual.py), [`pipeline/back_translate.py`](../pipeline/back_translate.py), [`pipeline/distill.py`](../pipeline/distill.py) |
| **MBR.** 4 muestras y gana la de mayor chrF++ promedio contra las demás: la mayor ganancia individual del David anterior (+3.2), a cambio de latencia. | [`duel/tzij_duel/variants.py`](../duel/tzij_duel/variants.py) (`_mbr`) |
| **Un nicho pre-registrado: memoria de traducción.** Se aparta un producto completo de Pontoon (Firefox Focus) y los demás productos se quedan como memoria de traducción. La regla, el producto y los términos se publican en git antes de calcular nada; se mide chrF++ y la precisión de terminología al estilo WMT con bootstrap. Ahí David gana: 37.4 contra 28.9 (+8.5 [+4.7, +12.7]). | [`pipeline/niche.py`](../pipeline/niche.py), [`evals/niche.md`](../evals/niche.md), [`evals/niche_report.py`](../evals/niche_report.py), [`evals/niche_results.md`](../evals/niche_results.md) |
| **Fertilidad de tokens.** En el tokenizador de Gemma, una palabra K'iche' cuesta 2.64 tokens y una española 1.41. La misma oración ocupa **1.92×** tokens en K'iche'. | [`evals/fertility.py`](../evals/fertility.py), [`evals/fertility.md`](../evals/fertility.md) |
| **Un modelo pequeño servido en la nube.** David, EmbeddingGemma y el índice van dentro de una sola imagen, en una GPU de Cloud Run con mínimo 0 instancias: no cobra mientras nadie usa la página, y la página lo despierta y espera a que esté listo. | [`david/Dockerfile`](../david/Dockerfile), [`duel/tzij_duel/david_app.py`](../duel/tzij_duel/david_app.py), [`infra/20-david.sh`](../infra/20-david.sh), [`duel/tzij_duel/page.py`](../duel/tzij_duel/page.py) |
| **Validación automática; hablantes nativos opcionales.** Nadie tiene que revisar nada para que el demo funcione: cada par de prueba se valida solo (split por fuente, limpieza, proporción de longitud 0.5–2.0, el lado español parece español, nada repetido de train) y queda `auto_validated`. La revisión nativa y la evaluación humana a ciegas (`make human-eval-sheet`) son extras opcionales. | [`pipeline/validate_test.py`](../pipeline/validate_test.py), [`pipeline/review.py`](../pipeline/review.py) (opcional), [`evals/human_eval.md`](../evals/human_eval.md) (opcional) |

## Decisiones

### Qué corre dónde y por qué

Todo corre en Google Cloud, proyecto `ai-experiments-487722`. En la laptop no corre ningún modelo: solo se abre la página.

| Componente | Dónde | Por qué |
| --- | --- | --- |
| La página (exportación estática de Next.js + servicio FastAPI, `page/`) | Cloud Run `tzij`, `europe-west4`, pública, 1 vCPU | Se abre desde cualquier navegador y no hay nada que correr el día de la charla. Por cada frase pide la traducción de David y la de Goliath por separado, así cada columna se llena en cuanto su modelo responde, y en los ejemplos mide el parecido con la traducción correcta (chrF++). No guarda nada. |
| David (`tzij-2026-10-mix-s7` + EmbeddingGemma en Ollama, el índice y MBR-4, `david/`) | Cloud Run `tzij-david`, `europe-west4`, privado, 1× NVIDIA L4, 4 vCPU, 16 GiB, mínimo 0 y máximo 1 instancia, 16 traducciones en paralelo en Ollama | Una GPU solo mientras alguien usa la página. El modelo (5.3 GB), EmbeddingGemma y los kernels de GPU ya compilados van dentro de la imagen, en Artifact Registry de `europe-west4`, así que un arranque en frío no baja nada de internet ni compila nada. 4 vCPU y 16 GiB (el mínimo con una L4) traducen igual de rápido que 8 y 32, y cuestan 26 % menos por hora. Solo la cuenta de servicio de la página (`tzij-page`) tiene `run.invoker`. `europe-west4` porque ahí el proyecto tiene cuota de L4 sin redundancia zonal. |
| Goliath (`gemini-3.8-flash`) | Vertex AI, `global`, llamado desde la página | Es el modelo frontier tal como lo usa la gente, sin datos extra. |
| Pipeline de datos | Cloud Run Job (`us-central1`) | Descarga unos 1.5 GB (el volcado de Wikcionario se filtra en streaming) y tiene que ser reproducible. Guarda la caché cruda y los datasets versionados en `gs://…-tzij-data`. `make data` corre el mismo código en local. |
| Índice de recuperación | `gs://…-tzij-data/index/<dataset>/`, dentro de la imagen de David | Se construye con el mismo EmbeddingGemma que responde las consultas: `make index` usa el de la nube a través de `make david-proxy`. |
| Fine-tune LoRA | Cloud Run Job con 1× NVIDIA L4 (`europe-west4`) | Sin servidores, se cobra por segundo, no queda nada encendido entre reentrenamientos. `TRAIN_RUNTIME=vertex` envía el mismo contenedor como Vertex AI Custom Job, y `train/colab.ipynb` envuelve el mismo script para Colab Enterprise. |
| Merge y GGUF del modelo E4B | Cloud Batch, una VM `n2-highmem-8` (64 GB) con 200 GB de disco, `europe-west4` | Ver abajo. |

### La página y David: cómo se conectan

- **David es privado.** La página llama a `tzij-david` con un token de identidad de su cuenta de servicio (`duel/tzij_duel/remote.py`); nadie más puede llamarlo. El dueño del proyecto también puede, con `gcloud`: así corren `make examples`, `make eval` y `make index` (`make david-proxy` abre su Ollama en `127.0.0.1:11435`).
- **Despertar a David.** Con mínimo 0 instancias, la GPU se apaga sola unos 15 minutos después de la última petición. La página pregunta `/api/david` cada 3 s hasta que David está listo (la pregunta misma lo despierta), muestra «Preparando a David…» y no deja traducir hasta entonces. El servicio de David abre su puerto enseguida, carga el modelo en la GPU, EmbeddingGemma y el índice, hace una traducción completa y solo entonces dice `ready` (`david_app.py`). Del arranque de la instancia a `ready` tarda 35 s; desde la página, unos 40 s (39 s medido con la GPU apagada; antes, 3 min 24 s). Después, la página pregunta una vez por minuto mientras está visible, y eso lo mantiene despierto durante la charla.
- **Los kernels de GPU, compilados una vez.** Un arranque desde cero tardaba 3.5 minutos, y 2.5 de ellos eran CUDA compilando el código de Ollama para la L4 (lo confirmó un job que repitió el arranque con la caché de CUDA llena y vacía). `infra/20-david.sh` construye la imagen, la corre una vez en un Cloud Run Job con una L4 (`david/warm_cache.py`) y construye la imagen final con lo compilado (`david/Dockerfile.cache`). Detalle y números en el [README](../README.md#arranque-en-frío).
- **Tiempo y costo en la página.** Cada columna muestra cuánto tardó la traducción y cuánto costó. El costo de David son los segundos que trabajó × el precio por segundo de su instancia ($0.0002907: L4 + 4 vCPU + 16 GiB); el de Goliath, sus tokens × el precio de lista de Gemini del día (que se duplica el 1 de enero de 2027). Con una persona usando la página David responde antes (0.81 s contra 1.47 s de mediana) y cuesta más por traducción ($0.00027 contra $0.00012 en 2026); las [proyecciones del README](../README.md#proyecciones-costo-y-tiempo) dicen dónde se invierte.
- **Ejemplos solo de casos de uso que David gana como conjunto:** la memoria de traducción (Firefox Focus) y los diccionarios que consulta (GATITOS, nombres de emoji de CLDR), medidos en `evals/usecases_results.md`. Nunca frases sueltas que gane dentro de un caso que pierde (las frases generales).
- **Protección de costo.** La página es pública y cada lado cuesta. `duel/tzij_duel/limits.py`: por IP, 30 traducciones y 40 consultas de estado por minuto; por día, 2,000 llamadas a Gemini y 12 encendidas de David; una pestaña abierta mantiene despierto a David solo 45 minutos después de su última traducción. Los contadores viven en la memoria de la página, que corre como una sola instancia. Todo se ajusta con variables de entorno (`LIMIT_*`, `KEEPALIVE_MAX_MIN`).
- **Una frase escrita sin traducción correcta.** Si está en los datos con licencia (prueba, memoria o diccionario), se mide como un ejemplo. Si no, la página muestra las frases más parecidas de la memoria de traducción, traducidas por personas, y marca las palabras que cada columna comparte con ellas. Se descartó comparar cada palabra con el diccionario: en los ejemplos, las traducciones equivocadas de Goliath tenían más palabras de diccionario que las correctas de David.
- **Descartado:** una sola instancia con la página y David juntos (la página tardaría lo mismo que la GPU en abrir), dejar a David siempre encendido ($764 al mes) y servir David en CPU (MBR-4 con E4B tarda decenas de segundos).

### Por qué el merge/GGUF de E4B corre en Cloud Batch

Un Cloud Run Job con GPU tiene como máximo **32 GiB** de memoria, y su sistema de archivos vive en esa misma memoria. El entrenamiento de E4B cabe: el adapter LoRA se guarda en un volumen de Cloud Storage. Lo que no cabe es guardar el checkpoint fusionado de 16 GB y convertirlo a GGUF. La ejecución `tzij-2026-09` entrenó 324 pasos en 1,316 s (22 min). Después se quedó sin memoria al guardar el modelo fusionado (`train/runs/tzij-2026-09.json`, ~30 min de job, ~$0.70 estimados). Por eso, con `TRAIN_FINISH=later`, el job de GPU solo entrena el adapter y `make train-finish` corre el mismo `train/finish.py`, con la misma imagen de entrenamiento, en una VM de Cloud Batch con 64 GB de RAM y 200 GB de disco (`infra/04-finish-batch.sh`). La VM se borra al terminar. Probado el 6 de octubre de 2026 con el adapter `tzij-2026-10-tm-a-e2-s4`: 10 minutos de punta a punta, GGUF Q4_K_M de 5.3 GB. Una primera ejecución con 1.5 épocas se canceló porque, a ~4 s por paso, no terminaba dentro del límite de 1 h de una tarea de GPU en Cloud Run (`train/runs/failed/`).

Los prompts RAFT son más largos (llevan el contexto recuperado), así que una época no cabe en una tarea de 1 h, y con lote 8 la L4 se quedó sin memoria. `tzij-2026-10-raft-bt` entrena con lote 2 × acumulación 8, máximo 1,024 tokens, y en 4 trozos (`--shard i/4`): cada trozo continúa el adapter del anterior (`--init-adapter`). Al final, `make train-finish` hace el merge del último trozo.

### BOUQuET: solo evaluación y fuera de git

BOUQuET (Meta) es un benchmark multidominio con traducciones humanas español → K'iche'. Su acceso en Hugging Face está restringido: hay que aceptar los términos, y el token vive en Secret Manager como `hf-token`. Los términos permiten **solo evaluación** y redistribución privada. Por eso:

- tiene rol `test` y nunca entra al entrenamiento ni al índice;
- sus datos crudos y procesados están en `.gitignore` y solo existen en el bucket privado;
- nunca se proyecta: los ejemplos de la página son de Firefox Focus (Mozilla Pontoon, MPL-2.0). `make eval` sí lo usa, junto con los libros de Bloom.

### Tope del 30 % para textos religiosos

El Nuevo Testamento de Totonicapán aporta unos 8,000 versículos, muchos más que todas las oraciones cotidianas juntas. Sin un tope, David traduciría "¿Dónde está el mercado?" con la voz de un evangelio. `pipeline/split.py` limita los textos religiosos al 30 % de las oraciones de entrenamiento. Elige los versículos con un hash estable, para que la selección sea reproducible y repartida, y nunca pone textos religiosos en prueba. `pipeline/train_set.py` vuelve a comprobar el tope antes del fine-tune. En el dataset actual la proporción es exactamente 30.0 %.

### K'iche' de Gemini solo para entrenar, y filtrado

Gemini no domina el K'iche'. Si generara K'iche' sin control, le enseñaría a David sus propios errores. Por eso cada registro K'iche' del dataset, del índice, de dev y de prueba es `origin=web`, con URL y licencia. Hay dos excepciones controladas, y las dos viven solo en los archivos de entrenamiento:

- **Retrotraducción:** Gemini traduce al **español** oraciones K'iche' monolingües con licencia (`origin=back_translated_gemini`, con modelo, prompt, semilla y costo en `data/train/back_translated_gemini.meta.json`). El lado K'iche' sigue siendo 100 % escrito por personas. Desde el 4 de octubre los pares entrenan las dos direcciones: K'iche' → español aprende el español de Gemini para K'iche' escrito por personas.
- **Destilación** (desde el 4 de octubre, `origin=distilled_gemini`, `pipeline/distill.py`): Gemini escribe español cotidiano en los dominios de BOUQuET y lo traduce al K'iche' con el mismo contexto recuperado que recibe David. Solo quedan los pares que usan el alfabeto de la ALMG, tienen una longitud razonable y vuelven al español con un chrF++ de al menos la mediana de los pares de dev (46.6). Del primer lote quedaron 2,409 de 6,000. Una segunda tanda (1,877 pares más, $6.98, incluidos en los ~$14 de Gemini y en los ~$24.3 de la ronda) se generó pero no entró a `tzij-2026-10-mix-s7`. Los datos sintéticos anclados en el diccionario no ayudaron y su código se quitó ([bitácora, sección 7](BITACORA.md)); la destilación en el dominio de la prueba sí (+2.1 en `dev_domain`, [sección 11](BITACORA.md)). Las fuentes que unen español y K'iche' a través del inglés (Pontoon, GATITOS) son traducciones humanas independientes, sin traducción automática. Hasta el modo simulado (`MOCK_AI=1`) responde con textos de los datos con licencia, nunca con K'iche' inventado. Se descartó `HuggingFaceFW/finetranslations` por ser traducción automática.

### EmbeddingGemma + `sqlite-vec`

- **Por qué:** caben en un solo archivo SQLite que se copia y se versiona por dataset, y viaja dentro de la imagen de David. EmbeddingGemma se sirve desde el mismo Ollama que David, en la misma GPU. Usa el prefijo de tarea `task: sentence similarity | query: ` porque compara frases de entrada con frases fuente del mismo idioma.
- **Cómo:** dos búsquedas por consulta. Los **ejemplos** salen de una búsqueda híbrida: BM25 sobre FTS5 (encuentra palabras raras y nombres) y vecinos por embedding (encuentra el sentido), fusionados con Reciprocal Rank Fusion y filtrados por dirección. El **glosario** busca primero coincidencias exactas de la entrada completa, de bigramas y de palabras sueltas, luego coincidencias difusas (variantes ortográficas), y completa con la misma búsqueda híbrida. David recibe `RAG_K=6` de cada tipo, con el ejemplo más cercano al final, junto a la frase (`RAG_ORDER=best_last`, +1.7 en dev). Todo se ajustó con `make tune-retrieval` en el split dev. Hay una caché de embeddings en disco (`rag/.cache/`) que abarata la reconstrucción.
- **Descartado:** una API de embeddings aparte. Sumaría una llamada de red por consulta, y el índice tiene que construirse con el mismo modelo que consulta.
- **EmbeddingGemma 1, no la 2.** Se probó EmbeddingGemma 2 para actualizar a la versión nueva; con la versión 1 funciona mejor (dev 39.9 contra 38.8, general 25.8 contra 23.9), por eso se usa la 1 (probado el 7 de octubre). Con el mismo David y el índice reconstruido con sus vectores bajó en dev (38.8 contra 39.9) y en la prueba (23.9 contra 25.8); en la especialidad subió 1.7, dentro de lo que varía MBR. Además, en Ollama solo corre con el runtime MLX, que no hay en la L4 ([bitácora, sección 13](BITACORA.md)).

### Otras decisiones

- **chrF++ y no BLEU.** Da crédito parcial por n-gramas de caracteres en un idioma aglutinante con mucha variación ortográfica. Se calcula a nivel corpus sobre texto normalizado, con el mismo apóstrofo para todos.
- **Mismas instrucciones para todos los modelos** (`tzij-translate-v1`). Solo cambia el bloque de contexto, así que la comparación mide datos y no prompts.
- **La latencia de David incluye la recuperación**, porque quien mira la página también espera por ella.
- **MBR en la demo, detrás de una bandera.** Con `DAVID_MBR=1` David genera `MBR_SAMPLES=4` traducciones a temperatura 0.7 y se queda con la de mayor chrF++ promedio contra las otras. En la laptop el p50 quedaba en 4.1 s; en la L4, en 0.9 s, porque Ollama corre las 4 muestras en paralelo (`OLLAMA_NUM_PARALLEL=4`). Con `DAVID_MBR=0` vuelve a una sola muestra.
- **`OLLAMA_NUM_CTX=4096`.** El contexto por defecto de 128k reserva una caché KV enorme y saca a EmbeddingGemma de memoria en cada petición.
- **Sin sesgo de logits ni MBR multi-prompt.** Se probaron con llama-server: el sesgo restó 1.2 en dev y el MBR multi-prompt pasó el límite de 5 s; su código se quitó ([bitácora, sección 8](BITACORA.md)).

## Resultados

**Con la memoria de traducción de una organización, David le gana a Goliath:** en Firefox Focus, un producto que nunca vio, saca **37.4 chrF++** contra **28.9** (+8.5 [+4.7, +12.7]). En traducción general Goliath sigue arriba: **36.9** contra **25.7**. Repetido el 7 de octubre con David en la GPU de la nube: 35.3 contra 28.9 en Firefox Focus (+6.4 [+2.5, +10.5]), 36.5 contra 30.4 en 105 frases más nuevas de Firefox Focus (+6.1 [+3.0, +9.2]) y 25.8 en la prueba general ([bitácora, sección 13](BITACORA.md)). En las cadenas nuevas de Mozilla Monitor, una página de marketing, gana Goliath (32.6 contra 22.0); la demo no las usa. Este repo es la mitad de la charla que responde a *cuándo NO hacer fine-tuning* y *qué compra cada paso*: la recuperación es el mayor salto, y el fine-tune solo empezó a sumar cuando sus datos se parecieron al dominio de la prueba. Goliath enseña una vez (retrotraducción y destilación) y después David traduce sin él.

`make eval`, ejecución `final-20261002`, dataset `20261002-173447` (el de la demo; su split de prueba es idéntico al de `20261002-022500`, con el que se corrieron las filas anteriores a `mix-s7`). Son 600 frases de prueba (150 por fuente y dirección, de Bloom y BOUQuET) que nunca están en el índice ni en el entrenamiento. Las variantes de Gemma se midieron en la laptop (Apple Silicon, Ollama), antes de pasar David a la nube: «Dónde» y las latencias son de esa ejecución. Las referencias están `auto_validated` (`pipeline/validate_test.py`). La recuperación se ajustó solo con el split dev ([`evals/tuning.md`](../evals/tuning.md)), y el conjunto de prueba se usó una sola vez, para estos números.

| Variante | Dónde | Recuperación | es → quc | quc → es | Ambas | p50 | p95 | API / 1,000 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 E4B (`gemma4:e4b`) | laptop | no | 7.5 | 16.7 | 11.7 | 1.31 s | 3.6 s | $0 |
| Gemma 4 E4B | laptop | vectores | 18.2 | 18.8 | 18.5 | 1.84 s | 4.8 s | $0 |
| Gemma 4 E4B | laptop | híbrida | 19.0 | 19.8 | 19.4 | 1.75 s | 4.7 s | $0 |
| Gemma 4 E4B + MBR (4 muestras) | laptop | híbrida | 20.4 | 20.9 | 20.7 | 4.59 s | 16.3 s | $0 |
| `tzij-2026-10-raft-bt-s3` (LoRA RAFT + retrotraducción, 1 época) | laptop | no | 9.2 | 17.4 | 13.0 | 1.20 s | 4.6 s | $0 |
| `tzij-2026-10-raft-bt-s3` | laptop | híbrida | 18.4 | 18.3 | 18.3 | 1.72 s | 4.7 s | $0 |
| `tzij-2026-10-raft-bt-s3` + MBR (4) — David anterior | laptop | híbrida | 21.9 | 21.2 | 21.5 | 3.96 s | 14.2 s | $0 |
| `tzij-2026-10-mix-s7` (2 épocas sin Focus + Bloom retrotraducido + destilación) | laptop | híbrida | 26.9 | 23.2 | 25.1 | 1.64 s | 4.3 s | $0 |
| **`tzij-2026-10-mix-s7` + MBR (4) — el David de la demo** | laptop | híbrida | 27.0 | 24.3 | **25.7** | 4.14 s | 13.4 s | $0 |
| **Gemini 3.8 Flash — Goliath** | nube | no | 33.4 | 40.7 | **36.9** | 1.73 s | 4.7 s | $0.29 |
| Gemini 3.8 Flash | nube | vectores | 34.6 | 40.1 | 37.2 | 2.08 s | 6.5 s | $0.95 |

**Ablación: qué compró cada paso** (mismas 600 frases):

| Paso | Ambas | Δ | p50 |
| --- | ---: | ---: | ---: |
| E4B base + recuperación por vectores | 18.5 | — | 1.84 s |
| + recuperación híbrida (BM25 + vectores con RRF, glosario difuso, ajustada en dev) | 19.4 | +0.9 | 1.75 s |
| + fine-tune RAFT con retrotraducción de Gemini | 18.3 | −1.1 | 1.72 s |
| + MBR (4 muestras, gana la de mayor chrF++ promedio contra las otras) | 21.5 | +3.2 | 3.96 s |
| + datos sin Focus, 2 épocas, Bloom retrotraducido y destilación ([bitácora, sección 11](BITACORA.md)) | **25.7** | +4.1 | 4.14 s |

![chrF++ por variante](diagrams/results.png)

**Conclusiones:**

- **Donde David tiene una memoria de traducción que Goliath no tiene, gana.** En el nicho (Firefox Focus, 144 frases que David nunca vio, ni en el índice ni en el entrenamiento, con los demás productos de Mozilla en su índice) saca 37.4 contra 28.9: +8.5 con IC 95 % [+4.7, +12.7]. Sin MBR, +7.0 [+2.9, +11.1]. En terminología empatan: 61 % contra 46 %, +15 con un intervalo que incluye el cero. La base con el mismo índice usa el término correcto el 78 % de las veces, pero empata en chrF++ (30.2). El nicho se pre-registró en [`evals/niche.md`](../evals/niche.md) y los números están en [`evals/niche_results.md`](../evals/niche_results.md).
- **En general, Goliath sigue siendo mejor traductor.** David queda 11.2 puntos abajo (eran 15.4 con el David anterior) y en todos los cortes (longitud, dirección, fuente, dominio): la brecha es K'iche' general, no un corte ([bitácora, sección 10](BITACORA.md)). Supera a Goliath en 130 de 599 oraciones (22 %) y queda a menos de 5 puntos en 206 (34 %). Un Goliath más grande no cambia nada: `gemini-3.1-pro-preview` empata con `gemini-3.8-flash` en K'iche'.
- **Los datos siguen siendo lo que mueve a David.** La recuperación lleva a E4B de 11.7 a 18.5, y en español → K'iche', la dirección que un modelo no puede improvisar, de 7.5 a 18.2. La búsqueda híbrida suma +0.9: BM25 encuentra las palabras raras que los embeddings no ven.
- **MBR fue la mayor ganancia con el David anterior (+3.2), y la paga la latencia.** David genera 4 traducciones y se queda con la que más se parece a las otras. Con el David actual suma +0.6 en la prueba (25.1 → 25.7) y +1.5 en el nicho (+7.0 → +8.5). En la laptop el p50 subía de 1.6 a 4.1 s y el p95 a 13 s; en la L4 de Cloud Run la mediana es 0.9 s. Se apaga con `DAVID_MBR=0`.
- **El primer fine-tune, con la recuperación, no ayudó: −1.1.** RAFT entrena con el mismo contexto recuperado que verá en la demo, sin la respuesta dentro. Combinado con MBR sumaba +0.8 sobre la base con MBR (21.5 vs 20.7). Sus datos (UD, Pontoon, COERLL) no se parecían a la prueba.
- **El fine-tune suma cuando los datos se parecen al dominio.** Con Bloom retrotraducido en las dos direcciones y destilación en los dominios de BOUQuET, `tzij-2026-10-mix-s7` le saca +5.7 a la base con la misma recuperación (25.1 vs 19.4) y +5.0 con MBR (25.7 vs 20.7). Contra el David anterior: +4.1 [+3.6, +4.7].
- **Goliath enseña una vez; después David traduce sin él.** Gemini tradujo al español 405 oraciones K'iche' monolingües con licencia (Wikipedia en K'iche', Space Scoop): 399 pares por **$0.12** una sola vez. Con el mismo presupuesto de entrenamiento (1/4 de época) la retrotraducción sumó +1.1 (15.7 vs 14.6), y ese primer fine-tune costó **$3.09** en 5 jobs de L4. Después tradujo los libros de Bloom solo en K'iche' ($0.36, 1,998 pares) y destiló 2,409 pares en los dominios de la prueba. La ronda de datos que produjo el David actual costó unos **$24.3** ($8.52 de L4; [bitácora, sección 11](BITACORA.md)). Nada de eso entra a la prueba ni al índice.
- **En la nube, David es más barato solo con mucho uso.** En la laptop costaba $0 por traducción. En la L4 de Cloud Run cuesta $1.05 por hora encendido: con una persona, $0.00027 por traducción contra $0.00012 de Gemini; a plena carga (unas 5,500 por hora), $0.000189. Con la tarifa de Gemini de 2027 ($0.000243), David sale más barato desde unas 4,300 traducciones por hora; con la de 2026, una sola L4 no llega ([proyecciones](../README.md#proyecciones-costo-y-tiempo)).
- Gemini con la misma recuperación mejora poco (36.9 → 37.2) y cuesta más de 3 veces más por el prompt más largo.

Detalle por fuente, longitud, dominio y fallos en [`evals/report.md`](../evals/report.md). Fertilidad de tokens en [`evals/fertility.md`](../evals/fertility.md). Datos y límites en [`MODEL_CARD.md`](../MODEL_CARD.md).

### En la demo

![La página: David y Goliath traducen la misma frase de Firefox Focus](demo/pagina-3-ejemplo.png)

*Un ejemplo de Firefox Focus en la página. Arriba, la traducción correcta, hecha por personas
para Mozilla Pontoon (MPL-2.0); en cada columna, la traducción y qué tanto se parece a la correcta
(chrF++). Las traducciones son **salida de los modelos**.*

## Versiones

Ninguna API en preview de las que sigue la serie de charlas (AppFunctions, WebMCP, UCP, AP2, A2A, MCP SDK, ADK) se usa en este repo. Versiones verificadas el 30 de septiembre de 2026:

| Pieza | Versión |
| --- | --- |
| Goliath | `gemini-3.8-flash`, Vertex AI `global`, `thinking_level=low`, SDK `google-genai` 2.25.0 |
| David | `tzij-2026-10-mix-s7` (LoRA sobre `google/gemma-4-E4B-it`, GGUF Q4_K_M) en Ollama 0.35.0, Cloud Run con 1× NVIDIA L4 (`europe-west4`) |
| Otras variantes medidas (`evals/runs/final-20261002`) | `gemma4:e4b` (base), `tzij-2026-10-raft-bt-s3` (el David anterior), `tzij-2026-10-raft-bt-s0` y `tzij-2026-10-raft-s0` (1/4 de época, para aislar la retrotraducción) |
| Embeddings | `embeddinggemma` en Ollama |
| Python | 3.12 con uv 0.8.22: FastAPI 0.142.2, uvicorn 0.54.0, sacrebleu 2.6.0, sqlite-vec 0.1.9, tokenizers 0.23.2, huggingface-hub 1.33.0, google-cloud-storage 3.15.1, pytest 9.1.1 |
| Web | Node 24.21.0, npm 12.0.2, Next.js 16.3.8, React 19.3.0, TypeScript 5.9.3, vitest 3.2.7, Playwright 1.63.0 |
| Imagen de entrenamiento | torch 2.14.0 (CUDA 12.6), transformers 5.17.0, peft 0.21.1, trl 1.14.1, accelerate 1.15.0, datasets 5.0.1, llama.cpp `b11292` |
| Google Cloud SDK | 587.0.0 |

Ningún nombre de modelo está escrito en el código: todos vienen de `.env` (`GEMINI_MODEL`, `LOCAL_MODEL_TAG`, `BASE_MODEL_TAGS`, `FINETUNED_MODEL_TAGS`, `GEMMA_BASE_MODEL`, `EMBEDDING_MODEL`).
