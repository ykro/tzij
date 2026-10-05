# Decisiones técnicas

Por qué Tzij está hecho así: el detalle de lo que enseña la demo, cada decisión con lo descartado, los resultados completos de `make eval` y las versiones. La historia iteración por iteración, con lo que no funcionó, está en la [bitácora](BITACORA.md). Volver al [README](../README.md). [English version](DECISIONES.en.md).

## Qué vas a aprender, en detalle

| Lección | Dónde está en el código |
| --- | --- |
| **Datos web con licencia y normalización ortográfica.** Cada registro lleva `origin=web`, URL y licencia. Las fuentes que no lo permiten quedan fuera. Las comillas simples tipográficas, la saltillo `ꞌ`, el `ʼ` y otros caracteres que se usan como saltillo se unifican al apóstrofo ASCII antes de indexar, entrenar o evaluar. | [`data/SOURCES.md`](../data/SOURCES.md) (14 fuentes usadas, 14 a la espera de permiso, 28 rechazadas), [`pipeline/sources/`](../pipeline/sources/), [`data/normalize.py`](../data/normalize.py), [`tests/test_normalize.py`](../tests/test_normalize.py) |
| **Split por fuente, no por oración.** Una fuente entera es de prueba o entera de entrenamiento, y cualquier par de entrenamiento que repita una oración de prueba se descarta. Si las oraciones se repartieran al azar, la evaluación mediría memoria. | [`pipeline/split.py`](../pipeline/split.py), [`pipeline/sources/__init__.py`](../pipeline/sources/__init__.py), [`data/DATASHEET.md`](../data/DATASHEET.md) |
| **Ablación decidida por `make eval`.** Base + vectores → + recuperación híbrida → + fine-tune RAFT con retrotraducción → + MBR → + datos en el dominio de la prueba (retrotraducción de Bloom y destilación), más Gemini con y sin recuperación, sobre las mismas 600 frases. Se ajusta con dev (desde el 4 de octubre, con `dev_domain`: párrafos de BOUQuET y páginas de Bloom fuera de la muestra de prueba) y se mide con prueba una sola vez. Gana la mejor variante local con p50 ≤ 5 s, aunque no sea la que costó más trabajo. | [`evals/run_eval.py`](../evals/run_eval.py), [`evals/tune_retrieval.py`](../evals/tune_retrieval.py), [`duel/tzij_duel/variants.py`](../duel/tzij_duel/variants.py), [`evals/report.md`](../evals/report.md) |
| **Recuperación híbrida.** BM25 (FTS5) para las palabras raras y EmbeddingGemma para el sentido, fusionados con RRF; glosario exacto y difuso; el ejemplo más cercano va al final, junto a la frase. | [`rag/retrieve.py`](../rag/retrieve.py), [`rag/store.py`](../rag/store.py), [`evals/tuning.md`](../evals/tuning.md) |
| **RAFT, retrotraducción y destilación: Goliath enseña una vez.** El fine-tune ve el mismo contexto recuperado que verá en escena, sin su propia respuesta. Gemini traduce al español K'iche' monolingüe con licencia, y esos pares entrenan las dos direcciones. Además destila: escribe español cotidiano en los dominios de la prueba y lo traduce al K'iche' con el contexto de David, y solo quedan los pares que pasan el alfabeto de la ALMG y la ida y vuelta. Todo se usa solo para entrenar, con origen, modelo, prompt, semilla y costo registrados. | [`pipeline/train_set.py`](../pipeline/train_set.py), [`pipeline/monolingual.py`](../pipeline/monolingual.py), [`pipeline/back_translate.py`](../pipeline/back_translate.py), [`pipeline/distill.py`](../pipeline/distill.py) |
| **MBR.** 4 muestras y gana la de mayor chrF++ promedio contra las demás: la mayor ganancia individual del David anterior (+3.2), a cambio de latencia. | [`duel/tzij_duel/variants.py`](../duel/tzij_duel/variants.py) (`_mbr`) |
| **Un nicho pre-registrado: memoria de traducción.** Se aparta un producto completo de Pontoon (Firefox Focus) y los demás productos se quedan como memoria de traducción. La regla, el producto y los términos se publican en git antes de calcular nada; se mide chrF++ y la precisión de terminología al estilo WMT con bootstrap. Ahí David gana: 37.4 contra 28.9 (+8.5 [+4.7, +12.7]). | [`pipeline/niche.py`](../pipeline/niche.py), [`evals/niche.md`](../evals/niche.md), [`evals/niche_report.py`](../evals/niche_report.py), [`evals/niche_results.md`](../evals/niche_results.md) |
| **Fertilidad de tokens.** En el tokenizador de Gemma, una palabra K'iche' cuesta 2.64 tokens y una española 1.41. La misma oración ocupa **1.92×** tokens en K'iche'. | [`evals/fertility.py`](../evals/fertility.py), [`evals/fertility.md`](../evals/fertility.md) |
| **Offline por diseño.** Modelo, embeddings, índice, servicio y vistas viven en la laptop. Las tipografías se descargan al compilar. Un sondeo TCP de 0.8 s decide si Goliath está en línea antes de llamarlo. | [`duel/duel_core/connectivity.py`](../duel/duel_core/connectivity.py), [`rag/embedder.py`](../rag/embedder.py), [`web/next.config.ts`](../web/next.config.ts), [`duel/tzij_duel/main.py`](../duel/tzij_duel/main.py) |
| **Validación automática; hablantes nativos opcionales.** Nadie tiene que revisar nada para que el demo funcione: cada par de prueba se valida solo (split por fuente, limpieza, proporción de longitud 0.5–2.0, el lado español parece español, nada repetido de train) y queda `auto_validated`. La revisión nativa y la vista del validador en el teléfono son extras opcionales. | [`pipeline/validate_test.py`](../pipeline/validate_test.py), [`pipeline/review.py`](../pipeline/review.py) (opcional), [`web/app/validar/page.tsx`](../web/app/validar/page.tsx) (opcional), [`evals/human_eval.md`](../evals/human_eval.md) (opcional) |

## Decisiones

### Qué corre en la laptop y por qué

| Componente | Dónde | Por qué |
| --- | --- | --- |
| David (`tzij-2026-10-mix-s7` en Ollama) | Laptop | La charla trata de un modelo que sirve a una comunidad sin conexión. Si David necesitara internet, no habría historia. |
| Índice de recuperación (EmbeddingGemma + `sqlite-vec`) | Laptop | Las consultas se hacen en el escenario sin red, así que el índice tiene que construirse con el mismo modelo de embeddings que responde offline. El nombre del modelo se guarda dentro del índice y se verifica en cada consulta (`rag/retrieve.py`). |
| Servicio de duelo (FastAPI) | Laptop | Llama a David y a Goliath en paralelo, mide latencia y costo, y guarda rondas y veredictos en un JSON. Si se va la red, Goliath aparece "sin conexión" y David sigue. |
| Vistas del presentador y del validador (Next.js, export estático) | Laptop, servidas por el mismo proceso | Un solo origen en la LAN: el teléfono solo necesita la IP de la laptop. Las tipografías se descargan al compilar (`next/font`), así que la página no pide nada a internet. |
| Goliath (`gemini-3.8-flash`) | Vertex AI, `global` | Es el modelo frontier tal como lo usa la gente, sin datos extra. Necesita internet a propósito. |
| Pipeline de datos | Cloud Run Job (`us-central1`) | Descarga unos 1.5 GB (el volcado de Wikcionario se filtra en streaming), tiene que ser reproducible y no debe depender de la laptop del presentador. Guarda la caché cruda y los datasets versionados en `gs://…-tzij-data`. `make data` corre el mismo código en local. |
| Fine-tune LoRA | Cloud Run Job con 1× NVIDIA L4 (`europe-west4`) | Sin servidores, se cobra por segundo, no queda nada encendido entre reentrenamientos, y usa la misma idea de contenedor que el pipeline. `TRAIN_RUNTIME=vertex` envía el mismo contenedor como Vertex AI Custom Job, y `train/colab.ipynb` envuelve el mismo script para Colab Enterprise. |
| Merge y GGUF del modelo E4B | Laptop (`make train-finish`) | Ver abajo. |

**El validador en la LAN.** El teléfono abre `http://<IP de la laptop>:8787/validar/` (el QR la calcula en `duel/tzij_duel/lan.py`, o se fija con `PUBLIC_URL`). Recibe las dos traducciones en orden aleatorio, sin nombre, latencia ni costo, y su voto aparece en la pantalla del presentador por SSE. En el emulador Android la laptop es `10.0.2.2`. `make emulator` comprueba que el voto llegue en menos de 1 s.

### Qué puede hacer cada quien en la LAN

El servicio escucha en `0.0.0.0` para que el teléfono llegue, así que la API separa dos públicos:

- **La laptop del presentador** (peticiones desde `127.0.0.1`): iniciar rondas, reiniciar, simular
  Wi-Fi apagado, leer el estado completo y el flujo `state`. Por eso la vista del presentador se
  abre en `http://127.0.0.1:8787/presentador/`, no con la IP de la LAN. Desde otra máquina estas
  rutas responden 403.
- **El teléfono:** solo el flujo `validator` y el voto. El flujo del teléfono es otro conjunto de
  suscriptores (`duel/tzij_duel/events.py`): nunca recibe nombres de modelo, latencia, costo ni la
  referencia, así que el voto es a ciegas de verdad, no solo en la interfaz. El voto se acepta solo
  para la ronda en vivo actual y una vez por traducción; las rondas de evaluación no aceptan votos
  (se califican con chrF++).

Descartado: autenticación con usuario y contraseña. En el escenario no hay tiempo para iniciar
sesión, y lo que hay que proteger es quién manda (la laptop), no quién mira.

### Por qué el merge/GGUF de E4B termina en la laptop

Un Cloud Run Job con GPU tiene como máximo **32 GiB** de memoria, y su sistema de archivos vive en esa misma memoria. El entrenamiento de E4B cabe: el adapter LoRA se guarda en un volumen de Cloud Storage. Lo que no cabe es guardar el checkpoint fusionado de 16 GB y convertirlo a GGUF. La ejecución `tzij-2026-09` entrenó 324 pasos en 1,316 s (22 min). Después se quedó sin memoria al guardar el modelo fusionado (`train/runs/tzij-2026-09.json`, ~30 min de job, ~$0.70 estimados). `make train-finish` baja el adapter, hace el merge y la conversión a GGUF Q4_K_M en la laptop con las mismas funciones de `train_lora.py`, y publica el resultado en el bucket de modelos. A `make pull-model` le da igual dónde se hizo el merge. Una primera ejecución con 1.5 épocas se canceló porque, a ~4 s por paso, no terminaba dentro del límite de 1 h de una tarea de GPU en Cloud Run (`train/runs/failed/`).

Los prompts RAFT son más largos (llevan el contexto recuperado), así que una época no cabe en una tarea de 1 h, y con lote 8 la L4 se quedó sin memoria. `tzij-2026-10-raft-bt` entrena con lote 2 × acumulación 8, máximo 1,024 tokens, y en 4 trozos (`--shard i/4`): cada trozo continúa el adapter del anterior (`--init-adapter`). `make train-finish` hace el merge del último en la laptop, con un GGUF intermedio Q8_0 para ahorrar disco.

### BOUQuET: solo evaluación y fuera de git

BOUQuET (Meta) es un benchmark multidominio con traducciones humanas español → K'iche'. Su acceso en Hugging Face está restringido: hay que aceptar los términos, y el token vive en Secret Manager como `hf-token`. Los términos permiten **solo evaluación** y redistribución privada. Por eso:

- tiene rol `test` y nunca entra al entrenamiento ni al índice;
- sus datos crudos y procesados están en `.gitignore` y solo existen en el bucket privado;
- las rondas de evaluación del escenario lo excluyen (`duel/tzij_duel/deck.py`), así que sus frases nunca se proyectan. `make eval` sí lo usa, junto con los libros de Bloom.

### Tope del 30 % para textos religiosos

El Nuevo Testamento de Totonicapán aporta unos 8,000 versículos, muchos más que todas las oraciones cotidianas juntas. Sin un tope, David traduciría "¿Dónde está el mercado?" con la voz de un evangelio. `pipeline/split.py` limita los textos religiosos al 30 % de las oraciones de entrenamiento. Elige los versículos con un hash estable, para que la selección sea reproducible y repartida, y nunca pone textos religiosos en prueba. `pipeline/train_set.py` vuelve a comprobar el tope antes del fine-tune. En el dataset actual la proporción es exactamente 30.0 %.

### K'iche' de Gemini solo para entrenar, y filtrado

Gemini no domina el K'iche'. Si generara K'iche' sin control, le enseñaría a David sus propios errores. Por eso cada registro K'iche' del dataset, del índice, de dev y de prueba es `origin=web`, con URL y licencia. Hay dos excepciones controladas, y las dos viven solo en los archivos de entrenamiento:

- **Retrotraducción:** Gemini traduce al **español** oraciones K'iche' monolingües con licencia (`origin=back_translated_gemini`, con modelo, prompt, semilla y costo en `data/train/back_translated_gemini.meta.json`). El lado K'iche' sigue siendo 100 % escrito por personas. Desde el 4 de octubre los pares entrenan las dos direcciones: K'iche' → español aprende el español de Gemini para K'iche' escrito por personas.
- **Destilación** (desde el 4 de octubre, `origin=distilled_gemini`, `pipeline/distill.py`): Gemini escribe español cotidiano en los dominios de BOUQuET y lo traduce al K'iche' con el mismo contexto recuperado que recibe David. Solo quedan los pares que usan el alfabeto de la ALMG, tienen una longitud razonable y vuelven al español con un chrF++ de al menos la mediana de los pares de dev (46.6). Del primer lote quedaron 2,409 de 6,000. Una segunda tanda (1,877 pares más, $6.98, incluidos en los ~$14 de Gemini y en los ~$24.3 de la ronda) se generó pero no entró a `tzij-2026-10-mix-s7`. Los datos sintéticos anclados en el diccionario no ayudaron y su código se quitó ([bitácora, sección 7](BITACORA.md)); la destilación en el dominio de la prueba sí (+2.1 en `dev_domain`, [sección 11](BITACORA.md)). Las fuentes que unen español y K'iche' a través del inglés (Pontoon, GATITOS) son traducciones humanas independientes, sin traducción automática. Hasta el modo simulado (`MOCK_AI=1`) responde con textos de los datos con licencia, nunca con K'iche' inventado. Se descartó `HuggingFaceFW/finetranslations` por ser traducción automática.

### EmbeddingGemma + `sqlite-vec`

- **Por qué:** corren en local, offline, en un solo archivo SQLite que se copia y se versiona por dataset. EmbeddingGemma se sirve desde el mismo Ollama que David. Usa el prefijo de tarea `task: sentence similarity | query: ` porque compara frases de entrada con frases fuente del mismo idioma.
- **Cómo:** dos búsquedas por consulta. Los **ejemplos** salen de una búsqueda híbrida: BM25 sobre FTS5 (encuentra palabras raras y nombres) y vecinos por embedding (encuentra el sentido), fusionados con Reciprocal Rank Fusion y filtrados por dirección. El **glosario** busca primero coincidencias exactas de la entrada completa, de bigramas y de palabras sueltas, luego coincidencias difusas (variantes ortográficas), y completa con la misma búsqueda híbrida. David recibe `RAG_K=6` de cada tipo, con el ejemplo más cercano al final, junto a la frase (`RAG_ORDER=best_last`, +1.7 en dev). Todo se ajustó con `make tune-retrieval` en el split dev. Hay una caché de embeddings en disco (`rag/.cache/`) que abarata la reconstrucción.
- **Descartado:** una API de embeddings en la nube. No funcionaría con la red cortada, y el índice tiene que construirse con el mismo modelo que consulta.

### Otras decisiones

- **chrF++ y no BLEU.** Da crédito parcial por n-gramas de caracteres en un idioma aglutinante con mucha variación ortográfica. Se calcula a nivel corpus sobre texto normalizado, con el mismo apóstrofo para todos.
- **Mismas instrucciones para todos los modelos** (`tzij-translate-v1`). Solo cambia el bloque de contexto, así que la comparación mide datos y no prompts.
- **La latencia de David incluye la recuperación**, porque el público también espera por ella.
- **MBR en escena detrás de una bandera.** Con `MBR_ON_STAGE=1` David genera `MBR_SAMPLES=4` traducciones a temperatura 0.7 y se queda con la de mayor chrF++ promedio contra las otras. Solo entra porque el p50 queda en 4.1 s (límite: 5 s). Con `MBR_ON_STAGE=0` vuelve a una sola muestra.
- **`OLLAMA_NUM_CTX=4096`.** El contexto por defecto de 128k reserva una caché KV enorme y saca a EmbeddingGemma de memoria en cada petición.
- **Sin sesgo de logits ni MBR multi-prompt.** Se probaron con llama-server: el sesgo restó 1.2 en dev y el MBR multi-prompt pasó el límite de 5 s; su código se quitó ([bitácora, sección 8](BITACORA.md)).

## Resultados

**Con la memoria de traducción de una organización, David le gana a Goliath:** en Firefox Focus, un producto que nunca vio, saca **37.4 chrF++** contra **28.9** (+8.5 [+4.7, +12.7]). En traducción general Goliath sigue arriba: **36.9** contra **25.7**. David gana además en otras cosas: cuesta **$0** por traducción, los datos no salen de la laptop y **funciona sin internet**, donde Goliath no produce nada. Este repo es la mitad de la charla que responde a *cuándo NO hacer fine-tuning* y *qué compra cada paso*: la recuperación es el mayor salto, y el fine-tune solo empezó a sumar cuando sus datos se parecieron al dominio de la prueba. Goliath enseña una vez en la nube (retrotraducción y destilación) y David sirve para siempre sin internet.

`make eval`, ejecución `final-20261002`, dataset `20261002-173447` (el de escena; su split de prueba es idéntico al de `20261002-022500`, con el que se corrieron las filas anteriores a `mix-s7`). Son 600 frases de prueba (150 por fuente y dirección, de Bloom y BOUQuET) que nunca están en el índice ni en el entrenamiento. Las referencias están `auto_validated` (`pipeline/validate_test.py`). La recuperación se ajustó solo con el split dev ([`evals/tuning.md`](../evals/tuning.md)), y el conjunto de prueba se usó una sola vez, para estos números.

| Variante | Dónde | Recuperación | es → quc | quc → es | Ambas | p50 | p95 | Costo / 1,000 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 E4B (`gemma4:e4b`) | laptop | no | 7.5 | 16.7 | 11.7 | 1.31 s | 3.6 s | $0 |
| Gemma 4 E4B | laptop | vectores | 18.2 | 18.8 | 18.5 | 1.84 s | 4.8 s | $0 |
| Gemma 4 E4B | laptop | híbrida | 19.0 | 19.8 | 19.4 | 1.75 s | 4.7 s | $0 |
| Gemma 4 E4B + MBR (4 muestras) | laptop | híbrida | 20.4 | 20.9 | 20.7 | 4.59 s | 16.3 s | $0 |
| `tzij-2026-10-raft-bt-s3` (LoRA RAFT + retrotraducción, 1 época) | laptop | no | 9.2 | 17.4 | 13.0 | 1.20 s | 4.6 s | $0 |
| `tzij-2026-10-raft-bt-s3` | laptop | híbrida | 18.4 | 18.3 | 18.3 | 1.72 s | 4.7 s | $0 |
| `tzij-2026-10-raft-bt-s3` + MBR (4) — David anterior | laptop | híbrida | 21.9 | 21.2 | 21.5 | 3.96 s | 14.2 s | $0 |
| `tzij-2026-10-mix-s7` (2 épocas sin Focus + Bloom retrotraducido + destilación) | laptop | híbrida | 26.9 | 23.2 | 25.1 | 1.64 s | 4.3 s | $0 |
| **`tzij-2026-10-mix-s7` + MBR (4) — David en escena** | laptop | híbrida | 27.0 | 24.3 | **25.7** | 4.14 s | 13.4 s | $0 |
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
- **MBR fue la mayor ganancia con el David anterior (+3.2), y la paga la latencia.** David genera 4 traducciones y se queda con la que más se parece a las otras. Con el David actual suma +0.6 en la prueba (25.1 → 25.7) y +1.5 en el nicho (+7.0 → +8.5). El p50 sube de 1.6 a 4.1 s (dentro del límite de 5 s para el escenario) y el p95 a 13 s, por eso se puede apagar con `MBR_ON_STAGE=0`.
- **El primer fine-tune, con la recuperación, no ayudó: −1.1.** RAFT entrena con el mismo contexto recuperado que verá en escena, sin la respuesta dentro. Combinado con MBR sumaba +0.8 sobre la base con MBR (21.5 vs 20.7). Sus datos (UD, Pontoon, COERLL) no se parecían a la prueba.
- **El fine-tune suma cuando los datos se parecen al dominio.** Con Bloom retrotraducido en las dos direcciones y destilación en los dominios de BOUQuET, `tzij-2026-10-mix-s7` le saca +5.7 a la base con la misma recuperación (25.1 vs 19.4) y +5.0 con MBR (25.7 vs 20.7). Contra el David anterior: +4.1 [+3.6, +4.7].
- **Goliath enseña una vez en la nube; David sirve para siempre sin internet.** Gemini tradujo al español 405 oraciones K'iche' monolingües con licencia (Wikipedia en K'iche', Space Scoop): 399 pares por **$0.12** una sola vez. Con el mismo presupuesto de entrenamiento (1/4 de época) la retrotraducción sumó +1.1 (15.7 vs 14.6), y ese primer fine-tune costó **$3.09** en 5 jobs de L4. Después tradujo los libros de Bloom solo en K'iche' ($0.36, 1,998 pares) y destiló 2,409 pares en los dominios de la prueba. La ronda de datos que produjo el David actual costó unos **$24.3** ($8.52 de L4; [bitácora, sección 11](BITACORA.md)). Nada de eso entra a la prueba ni al índice.
- **Donde David gana sin discusión:** costo ($0 contra $0.29 por cada 1,000 traducciones, y la tarifa de lista de Gemini se duplica desde el 1 de enero de 2027), privacidad (nada sale de la laptop) y disponibilidad. Sin internet Goliath no produce nada, y los números de David no cambian.
- Gemini con la misma recuperación mejora poco (36.9 → 37.2) y cuesta más de 3 veces más por el prompt más largo.

Detalle por fuente, longitud, dominio y fallos en [`evals/report.md`](../evals/report.md). Fertilidad de tokens en [`evals/fertility.md`](../evals/fertility.md). Datos y límites en [`MODEL_CARD.md`](../MODEL_CARD.md).

### En el escenario

![Ronda de evaluación: la referencia viene de un libro con licencia; David y Goliath traducen la misma frase](demo/02-evaluacion-es-quc.png)

*Ronda de evaluación con `tzij-2026-10-mix-s7`. La frase y su **referencia** vienen de un libro de Bloom Library (MINEDUC Guatemala, CC BY 4.0). Las dos traducciones son **salida del modelo, sin validar** por una persona hablante nativa; chrF++ las compara con la referencia (45.9 contra 47.3). David tardó 5.1 s con 4 muestras MBR en una frase larga (p50 en el reporte: 4.1 s) y Goliath 3.2 s.*

![Con Wi-Fi apagado: David traduce en la laptop, Goliath aparece sin conexión](demo/07-sin-conexion.png)

*Otra ronda de evaluación con la red cortada (interruptor de ensayo). La traducción de David es **salida del modelo, sin validar**.*

## Versiones

Ninguna API en preview de las que sigue la serie de charlas (AppFunctions, WebMCP, UCP, AP2, A2A, MCP SDK, ADK) se usa en este repo. Versiones verificadas el 30 de septiembre de 2026:

| Pieza | Versión |
| --- | --- |
| Goliath | `gemini-3.8-flash`, Vertex AI `global`, `thinking_level=low`, SDK `google-genai` 2.25.0 |
| David | `tzij-2026-10-mix-s7` (LoRA sobre `google/gemma-4-E4B-it`, GGUF Q4_K_M) en Ollama 0.35.0 |
| Otras variantes de `make eval` | `gemma4:e4b` (base), `tzij-2026-10-raft-bt-s3` (el David anterior), `tzij-2026-10-raft-bt-s0` y `tzij-2026-10-raft-s0` (1/4 de época, para aislar la retrotraducción) |
| Embeddings | `embeddinggemma` en Ollama |
| Python | 3.12 con uv 0.8.22: FastAPI 0.142.2, uvicorn 0.54.0, sacrebleu 2.6.0, sqlite-vec 0.1.9, tokenizers 0.23.2, huggingface-hub 1.33.0, google-cloud-storage 3.15.1, pytest 9.1.1 |
| Web | Node 24.21.0, npm 12.0.2, Next.js 16.3.8, React 19.3.0, TypeScript 5.9.3, vitest 3.2.7, Playwright 1.63.0 |
| Imagen de entrenamiento | torch 2.14.0 (CUDA 12.6), transformers 5.17.0, peft 0.21.1, trl 1.14.1, accelerate 1.15.0, datasets 5.0.1, llama.cpp `b11292` |
| Google Cloud SDK | 587.0.0 |

Ningún nombre de modelo está escrito en el código: todos vienen de `.env` (`GEMINI_MODEL`, `LOCAL_MODEL_TAG`, `BASE_MODEL_TAGS`, `FINETUNED_MODEL_TAGS`, `GEMMA_BASE_MODEL`, `EMBEDDING_MODEL`).
