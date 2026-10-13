# Tzij — traductor español ↔ K'iche': un modelo pequeño contra Gemini

Demo de la charla **"David vs. Goliath: cómo un modelo pequeño le gana a un modelo frontier"**. Tzij ("palabra" en K'iche') traduce entre español y K'iche' (ISO 639-3 `quc`), el idioma maya más hablado de Guatemala.

- **David** es Gemma 4 E4B ajustado con LoRA (`tzij-2026-10-mix-s7`), con un índice de recuperación híbrido hecho solo con datos K'iche' con licencia y con decodificación MBR. Corre en Ollama, en su propia GPU (una NVIDIA L4 en Cloud Run) que se apaga sola cuando nadie lo usa.
- **Goliath** es Gemini 3.8 Flash en Vertex AI, usado como lo usa cualquiera.

La demo es una sola página pública en Cloud Run (`make page-url`): escribes una frase (o tocas un ejemplo) y David y Goliath la traducen al mismo tiempo, lado a lado. En los ejemplos, frases de la interfaz de Firefox Focus, la página muestra también la traducción correcta, la que hicieron personas, y qué tanto se parece a ella cada una; en todas, cuánto tardó y cuánto costó cada traducción. No hay nada que correr el día de la charla: se abre la página unos minutos antes y ella despierta a David.

[English version](README.en.md)

![La página: David y Goliath traducen la misma frase de Firefox Focus](docs/demo/pagina-3-ejemplo.png)

## Qué vas a aprender

1. **Datos con licencia y split por fuente:** cada registro K'iche' lleva URL y licencia, y una fuente entera es de prueba o de entrenamiento.
2. **Qué compra cada paso:** la recuperación es el mayor salto; el fine-tune empezó a sumar (+5.7) cuando sus datos se parecieron al dominio de la prueba.
3. **Goliath enseña una vez:** Gemini retrotraduce K'iche' con licencia y escribe datos de destilación por unos $14; después David traduce sin él.
4. **Un nicho pre-registrado:** con una memoria de traducción que Goliath no tiene, David gana por +8.5 chrF++.
5. **Un modelo pequeño en la nube:** David, su índice y su decodificación en una sola imagen, en una GPU de Cloud Run que se enciende al abrir la página y se apaga sola.

## Diapositivas

Esta demo es parte de la charla «David vs. Goliath». Las diapositivas están en Google Slides: [David vs. Goliath](https://docs.google.com/presentation/d/1MddCAi51juUAEXbbiUyXwL6CqYzId0ELFSBwzREUW6U/edit?usp=sharing).

## Taller práctico

El taller de esta charla es «Entrena a tu propio David» ([codelabs-2027/entrena-tu-david](https://github.com/ykro/codelabs-2027/tree/main/entrena-tu-david)): ajustas Gemma 4 E2B con LoRA en Colab y lo comparas con el modelo base. Se sigue desde el navegador, con una cuenta de Google, y termina con algo que funciona.

## La demo: la página

| | David | Goliath |
| --- | --- | --- |
| Qué es | Gemma 4 E4B ajustado (`tzij-2026-10-mix-s7`) + recuperación híbrida + MBR-4 | Gemini 3.8 Flash, sin datos extra |
| Dónde corre | Cloud Run con 1× NVIDIA L4 (`tzij-david`, privado) | Vertex AI |

- **Ejemplos, por caso de uso:** solo de los casos en que David le gana a Goliath en todo el conjunto medido ([casos de uso](#casos-de-uso-donde-gana-david)): 6 frases de la interfaz de Firefox Focus (Mozilla Pontoon, MPL-2.0), 8 palabras cotidianas del diccionario GATITOS (Google Research, CC BY 4.0) y 6 nombres de emoji de Unicode CLDR (Unicode License V3), cada una con su traducción correcta. Cada grupo dice cómo le fue a cada uno en su conjunto completo. Cada frase se tradujo 3 veces con el David de la nube y con Goliath, como lo hace la página, y solo quedaron las que David tradujo siempre cerca de la correcta (chrF++ de 50 o más) y por lo menos 15 puntos más cerca que Goliath. Están en [`duel/examples.json`](duel/examples.json), con las salidas y los puntajes medidos; `make examples` las vuelve a revisar.
- **"Se parece a la correcta":** compara cada traducción con la que hicieron personas, en pedacitos de letras y palabras, y dice qué parte comparten: 100 % es idéntica, 0 % no tiene nada en común. Si la correcta es «Chajital tʼiqonem», «Chajital tʼiqoj» se parece en 66 % y «Jikilik tʼiqoj» en 16 %. Es la medida chrF++, la usual para comparar traductores automáticos; [más abajo](#qué-es-chrf), en detalle.
- **Una frase escrita:** si la frase está en los datos con licencia (la prueba, la memoria de traducción de David o el diccionario), la página la reconoce, muestra su traducción correcta y mide las dos igual que un ejemplo. Si no está, no hay contra qué medir y la página lo dice; para juzgar, muestra las 3 frases más parecidas de la memoria de traducción, traducidas por personas, y marca en cada columna las palabras que también usan esas traducciones (la terminología de la memoria). No es un puntaje. Una revisión palabra por palabra contra el diccionario se descartó: en los ejemplos, las traducciones equivocadas de Goliath tenían más palabras de diccionario que las correctas de David, así que habría engañado.
- **Tiempo y costo:** cada columna muestra cuánto tardó esa traducción y cuánto costó. David corre en su propia GPU, que se cobra por segundo mientras está encendida: su costo son los segundos que trabajó × el precio por segundo de la instancia (L4 + 4 vCPU + 16 GiB en `europe-west4`: $0.0002907/s, $1.05 por hora). Goliath cobra por tokens, al precio de lista de Gemini del día ($0.75 / $3.75 por millón; desde el 1 de enero de 2027, $1.50 / $7.50). Cuándo gana cada uno, en [Proyecciones](#proyecciones-costo-y-tiempo).
- **David se despierta solo:** su GPU tiene mínimo 0 instancias. Al abrir la página, dice «Preparando a David…» unos 40 s (antes, 3 min 24 s; ver [arranque en frío](#arranque-en-frío)) y después «David listo»; mientras la página siga abierta, lo mantiene despierto.
- **En el teléfono:** la página se adapta a teléfonos y tabletas: todo en una columna, David arriba de Goliath, y los ejemplos se deslizan de lado.
- **Dirección:** los ejemplos y la demo son español → K'iche', el caso que David gana. La página también traduce del K'iche' al español (botón ⇄), pero esa dirección no se muestra en la charla (ver [abajo](#por-qué-la-demo-usa-solo-el-modelo-final)).

El guion, con capturas y tiempos, está en [docs/DEMO.md](docs/DEMO.md).

![Arquitectura: todo en Google Cloud](docs/diagrams/architecture.png)

## Resultados (evaluación)

Medido con `make eval` (ejecución `final-20261002`, dataset `20261002-173447`) y `make niche`. Detalle en [evals/report.md](evals/report.md) y [evals/niche_results.md](evals/niche_results.md).

| | David (`mix-s7` + híbrida + MBR-4) | Goliath (`gemini-3.8-flash`) |
| --- | ---: | ---: |
| **Especialidad:** memoria de traducción, Firefox Focus, 144 frases es → quc (chrF++) | **37.4** | 28.9 |
| General: 600 frases de prueba de Bloom y BOUQuET, las dos direcciones (chrF++) | 25.7 | **36.9** |

En la especialidad David gana por **+8.5** [IC 95 %: +4.7, +12.7] en un producto que nunca vio. En traducción general Goliath va arriba por 11.2 puntos; la brecha es K'iche' general, no un tipo de frase ([experimento 10](#lo-que-dijo-cada-experimento)).

**Repetido con David en la nube** (7 de octubre, el mismo modelo y el mismo índice, en la L4 de Cloud Run; ejecuciones `cloud-20261007`, `niche-cloud` y `tm-new`):

| | David | Goliath | David − Goliath [IC 95 %] |
| --- | ---: | ---: | ---: |
| Especialidad: las 144 frases de Firefox Focus | **35.3** | 28.9 | **+6.4** [+2.5, +10.5] |
| Especialidad: 105 frases más de Firefox Focus, más nuevas que el dataset ([`evals/tm_new_results.md`](evals/tm_new_results.md)) | **36.5** | 30.4 | **+6.1** [+3.0, +9.2] |
| General: las mismas 600 frases de prueba | 25.8 | **36.9** | −11.1 |

En la nube David saca lo mismo en la prueba general (25.8 contra 25.7) y responde más rápido (mediana 1.77 s contra 4.14 s en la laptop). En las 144 frases de Firefox Focus saca 35.3 en vez de 37.4: MBR elige entre 4 traducciones muestreadas, así que dos ejecuciones no dan lo mismo; la ventaja sobre Goliath se sostiene en las dos (+6.4 y +8.5, y el intervalo no incluye el cero). Las 105 frases nuevas de Firefox Focus lo confirman con frases que no estaban en ninguna ejecución anterior ([experimento 13](#lo-que-dijo-cada-experimento)).

### Casos de uso donde gana David

Además de la memoria de traducción, se midieron otros casos de uso como conjunto, con muestras fijas con semilla y nunca elegidas por resultado ([`evals/usecases.py`](evals/usecases.py), [`evals/usecases_results.md`](evals/usecases_results.md), contra el David de la nube):

| Caso de uso | n | David | Goliath | David − Goliath [IC 95 %] | Traducción exacta: David | Goliath | Goliath con el mismo glosario |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Interfaz de Firefox Focus (memoria de traducción, frases nunca vistas) | 144 | **37.4** | 28.9 | +8.5 [+4.7, +12.7] | — | — | — |
| Palabras cotidianas del diccionario GATITOS (Google Research) | 150 | **57.5** | 22.1 | +35.4 [+28.0, +42.6] | 37 % | 9 % | 85 % |
| Nombres de emoji de Unicode CLDR | 100 | **60.9** | 25.7 | +35.2 [+28.1, +42.5] | 42 % | 1 % | 91 % |
| Frases generales (Bloom, BOUQuET), cualquier largo o fuente | 600 | 25.8 | **36.9** | −11.1 | — | — | — |

- **Los diccionarios son ventaja de datos, no de modelo.** Esas palabras están en el diccionario que David consulta; Goliath, como lo usa cualquiera, no lo tiene. Con el mismo glosario en el prompt, Gemini acierta más que David (88.6 y 94.4 de chrF++): el modelo ajustado con MBR no siempre copia la entrada exacta del glosario. El caso de uso es real (una organización con su propio glosario), pero lo que gana es tener los datos.
- **No hubo otro caso que David gane.** Por fuente, dirección y largo (de 1 a 3 palabras, de 4 a 6, de 7 a 10 y más) en las 600 frases de prueba, Goliath gana en todos menos en frases de 4 a 6 palabras español → Kʼicheʼ, que empatan (30.1 contra 29.7). Mozilla Monitor, otra interfaz de Mozilla, también lo pierde ([experimento 13](#lo-que-dijo-cada-experimento)).
- **El orden del contexto no cambia estos números.** David recibe el ejemplo más parecido al final, junto a la frase (`RAG_ORDER=best_last`, como se entrenó). Medido otra vez con el David final en la nube, con el ejemplo más parecido primero: Firefox Focus 36.7 contra 36.2, GATITOS 57.2 contra 55.6, CLDR 60.1 contra 62.5; los tres intervalos incluyen el cero, y dos ejecuciones con el mismo orden varían lo mismo por MBR ([evals/tuning.md](evals/tuning.md)).

### Qué es chrF++

Es la medida con que se califica cada traducción contra la que hicieron personas, y la que la página llama «se parece a la correcta». Parte las dos traducciones en pedacitos de 1 a 6 letras seguidas y en palabras sueltas y pares de palabras, y cuenta cuántos pedacitos comparten: 100 es idéntica, 0 es que no comparten nada. Da crédito parcial a una palabra casi bien escrita, que en K'iche' (palabras largas, con prefijos y sufijos) importa más que en otros idiomas. Ejemplo, con la correcta «Chajital tʼiqonem»: «Chajital tʼiqoj» saca 66 y «Jikilik tʼiqoj», 16. No entiende significado: un sinónimo correcto baja el puntaje. Por eso, además, la especialidad se pre-registró y un hablante puede validar la prueba.

## Experimentos

Todos los números salen de [`evals/`](evals/), [`train/runs/`](train/runs/) y la [bitácora](docs/BITACORA.md), donde está la historia completa, con fechas. Reglas: las 600 frases de prueba (150 por fuente y dirección, de Bloom y BOUQuET) nunca están en el índice ni en el entrenamiento; las decisiones se toman con un split de desarrollo (dev, y desde el experimento 10, `dev_domain`); la prueba se usa para el número final. chrF++ va de 0 a 100: más es mejor.

### Resumen

Los experimentos se corrieron con David en la laptop (Apple Silicon, Ollama), antes de pasar todo a la nube: las latencias de estas tablas son de esa máquina. En la nube, ver [David en la GPU de Cloud Run](#david-en-la-gpu-de-cloud-run).

| # | Experimento | Variante | chrF++ prueba (600) | Otra medida | Latencia p50 | Costo único | Resultado |
| ---: | --- | --- | ---: | --- | ---: | ---: | --- |
| 0 | Base, sin datos | `gemma4:e4b` | 11.7 | — | 1.31 s | $0 | Punto de partida |
| 1 | + recuperación por vectores | `gemma4:e4b+rag` | 18.5 | — | 1.84 s | $0 | La mayor ganancia |
| 2 | Fine-tune sin contexto de recuperación | `tzij-2026-09` + recuperación | 17.6* | — | — | $0.70 (+$0.41 cancelado) | Callejón sin salida |
| 3 | Recuperación híbrida (BM25 + vectores) | `gemma4:e4b+hybrid` | 19.4 | dev 30.9 → 32.5 | 1.75 s | $0 | Se queda |
| 4 | RAFT + retrotraducción de Gemini, 1 época | `tzij-2026-10-raft-bt-s3+hybrid` | 18.3 | — | 1.72 s | $3.09 L4 + $0.12 Gemini | Sola no ayuda |
| 5 | + MBR (4 muestras) | `tzij-2026-10-raft-bt-s3+hybrid+mbr4` | 21.5 | — | 3.96 s | $0 | El David de la demo del 2 al 5 de octubre |
| 6 | El nicho pre-registrado (Firefox Focus) | `gemma4:e4b+hybrid+mbr4` | — | especialidad 30.2 vs 28.9 | — | $0 | Empate en chrF++, gana en terminología |
| 7 | Datos sintéticos anclados en el diccionario | `tzij-2026-10-n2b-s1` | — | dev 33.8 vs 34.2 | — | $2.09 Gemini + $1.14 L4 | Fuera |
| 8 | Sesgo de logits hacia el diccionario | `n2a-s1` + llama-server | — | dev 33.8 vs 35.0 | 5.2 s | $0 | Fuera |
| 9 | Más épocas y más español → K'iche' | `tzij-2026-10-tm-a-e2-s4` | — | dev 37.5 vs 36.6 | 4.5 s | $6.16 L4 | Empate |
| 10 | Por qué pierde David; Gemini Pro | `gemini-3.1-pro-preview` | — | `dev_domain` 40.5 vs 40.6 | — | $1.85 | La brecha es K'iche' general |
| 11 | Bloom retrotraducido + destilación | `tzij-2026-10-mix-s7+hybrid+mbr4` | **25.7** | especialidad **37.4** vs 28.9 | 4.14 s | $8.52 L4 + $13.94 Gemini | **El David de la demo** |
| 12 | EmbeddingGemma 2 en la recuperación (en la nube) | `mix-s7` + índice con `embeddinggemma-2` | 23.9 (vs 25.8) | dev 38.8 vs 39.9; especialidad 37.0 vs 35.3 | — | $0 | Fuera: no mejora |
| 13 | Frases nuevas de Pontoon (en la nube) | `tzij-2026-10-mix-s7+hybrid+mbr4` | — | Firefox Focus 36.5 vs 30.4; Mozilla Monitor 22.0 vs 32.6 | — | $0.03 Gemini | Firefox Focus a la página; Mozilla Monitor no |

\* Medido sobre el dataset del 30 de septiembre (las mismas fuentes de prueba). Ahí la base con recuperación sacaba 18.4.

### Todas las variantes en la prueba

Las 600 frases de prueba, ejecución `final-20261002` ([evals/report.md](evals/report.md)). Latencias en la laptop; la última columna es el costo de la API de Gemini.

| Variante | es → quc | quc → es | Las dos | p50 | p95 | API / 1,000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemma4:e4b` | 7.5 | 16.7 | 11.7 | 1.31 s | 3.56 s | $0 |
| `gemma4:e4b+rag` | 18.2 | 18.8 | 18.5 | 1.84 s | 4.76 s | $0 |
| `gemma4:e4b+hybrid` | 19.0 | 19.8 | 19.4 | 1.75 s | 4.73 s | $0 |
| `gemma4:e4b+hybrid+mbr4` | 20.4 | 20.9 | 20.7 | 4.59 s | 16.33 s | $0 |
| `tzij-2026-10-raft-s0+hybrid` (1/4 época, sin retrotraducción) | 13.9 | 15.5 | 14.6 | 1.64 s | 4.65 s | $0 |
| `tzij-2026-10-raft-bt-s0+hybrid` (1/4 época, con retrotraducción) | 14.9 | 16.5 | 15.7 | 1.62 s | 4.59 s | $0 |
| `tzij-2026-10-raft-bt-s3` (sin recuperación) | 9.2 | 17.4 | 13.0 | 1.20 s | 4.62 s | $0 |
| `tzij-2026-10-raft-bt-s3+hybrid` | 18.4 | 18.3 | 18.3 | 1.72 s | 4.67 s | $0 |
| `tzij-2026-10-raft-bt-s3+hybrid+mbr4` | 21.9 | 21.2 | 21.5 | 3.96 s | 14.21 s | $0 |
| `tzij-2026-10-mix-s7+hybrid` | 26.9 | 23.2 | 25.1 | 1.64 s | 4.28 s | $0 |
| **`tzij-2026-10-mix-s7+hybrid+mbr4`** | **27.0** | **24.3** | **25.7** | 4.14 s | 13.43 s | $0 |
| `gemini-3.8-flash` | 33.4 | 40.7 | 36.9 | 1.73 s | 4.71 s | $0.292 |
| `gemini-3.8-flash+rag` (Gemini con el índice de David) | 34.6 | 40.1 | 37.2 | 2.08 s | 6.46 s | $0.947 |

**Fine-tune contra la base, con la misma recuperación y decodificación:** `mix-s7` suma +5.7 con híbrida (25.1 contra 19.4) y +5.0 con MBR (25.7 contra 20.7). El David anterior, `raft-bt-s3`, restaba −1.1 con híbrida y solo sumaba +0.8 con MBR.

**Ablación** (lo que compró cada paso, hasta el David del 2 de octubre y después el final):

| Paso | Variante | Las dos | Δ | p50 |
| --- | --- | ---: | ---: | ---: |
| Base + recuperación por vectores | `gemma4:e4b+rag` | 18.5 | — | 1.84 s |
| + recuperación híbrida | `gemma4:e4b+hybrid` | 19.4 | +0.9 | 1.75 s |
| + RAFT con retrotraducción (1 época) | `tzij-2026-10-raft-bt-s3+hybrid` | 18.3 | −1.1 | 1.72 s |
| + MBR (4 muestras) | `tzij-2026-10-raft-bt-s3+hybrid+mbr4` | 21.5 | +3.2 | 3.96 s |
| + datos del dominio, 2 épocas, Bloom retrotraducido y destilación | `tzij-2026-10-mix-s7+hybrid+mbr4` | 25.7 | +4.2 | 4.14 s |

### La especialidad, pre-registrada

Una memoria de traducción es el caso real donde un modelo pequeño puede ganar: una organización ya tradujo sus productos y quiere traducir uno nuevo con las mismas palabras. Para probarlo sin hacer trampa:

- se apartó un producto completo de Mozilla Pontoon, **Firefox Focus**: 144 pares español → K'iche' que no están ni en el entrenamiento ni en el índice;
- los demás productos de Mozilla quedan en el índice de David como memoria de traducción;
- la regla, el producto y los 41 términos se publicaron en git ([`evals/niche.md`](evals/niche.md)) antes de calcular nada;
- se mide chrF++ y la precisión de terminología al estilo WMT, con bootstrap pareado (2,000 remuestreos, IC 95 %).

| David | chrF++ David | chrF++ Goliath | David − Goliath [IC 95 %] | Frases que gana David | Terminología, David | Terminología, Goliath |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base + híbrida + MBR-4 (índice pre-registrado) | 29.7 | 28.9 | +0.9 [−2.8, +4.6] | — | 83 % | 46 % |
| Base + híbrida + MBR-4 (+ CLDR y FLORES-Mayas en el índice) | 30.2 | 28.9 | +1.3 [−2.3, +5.3] | 49 % | 78 % | 46 % |
| `mix-s7` + híbrida | 35.9 | 28.9 | +7.0 [+2.9, +11.1] | 56 % | 59 % | 46 % |
| **`mix-s7` + híbrida + MBR-4** | **37.4** | 28.9 | **+8.5** [+4.7, +12.7] | 57 % | 61 % | 46 % |

Con el David final, la diferencia en chrF++ ya no incluye el cero. En terminología, +15 puntos, pero ese intervalo sí incluye el cero ([−2, +32]).

**Más frases del mismo caso** ([experimento 13](#lo-que-dijo-cada-experimento), no pre-registrado). La memoria de traducción pública de Pontoon tiene cadenas más nuevas que el dataset. Las que no están en ningún split ni en el índice ([`evals/tm_new.py`](evals/tm_new.py)), medidas con David en la nube ([`evals/tm_new_results.md`](evals/tm_new_results.md)):

| Producto | Frases | chrF++ David | chrF++ Goliath | David − Goliath [IC 95 %] | Frases que gana David |
| --- | ---: | ---: | ---: | ---: | ---: |
| Firefox Focus (el producto apartado) | 105 | **36.5** | 30.4 | **+6.1** [+3.0, +9.2] | 64 % |
| Mozilla Monitor (David tiene sus cadenas viejas en el índice) | 57 | 22.0 | **32.6** | −10.7 [−20.2, −0.5] | 30 % |

En Firefox Focus, David vuelve a ganar con frases que nunca se habían medido. En las cadenas nuevas de Mozilla Monitor pierde: son textos de una página web de marketing, largos y con poco vocabulario repetido de la memoria. Por eso la página solo usa frases de Firefox Focus.

### Lo que dijo cada experimento

**0. La base.** Gemma 4 E4B con las mismas instrucciones que Gemini, sin contexto. 11.7 chrF++, y 7.5 en español → K'iche': el modelo casi no escribe K'iche'. *Aprendimos:* es lo que obtiene cualquiera que descarga un modelo pequeño; el punto de partida tiene que estar medido.

**1. Recuperación por vectores.** Índice local de unos 7,000 pares y entradas de diccionario con licencia, con EmbeddingGemma y `sqlite-vec`; David recibe 6 ejemplos y 6 entradas de glosario por frase. 11.7 → 18.5 (español → K'iche': 7.5 → 18.2). *Aprendimos:* un modelo pequeño no sabe K'iche', pero copia y adapta bien lo que le damos. Ningún otro paso movió tanto a David.

**2. Fine-tune sin contexto (`tzij-2026-09`).** LoRA r=16, 1 época con 5,180 ejemplos, entrenado sin el contexto de recuperación; 22 min de L4 en Cloud Run, $0.70. Solo, sube a la base de 11.5 a 15.2; con recuperación saca 17.6, 0.8 por debajo de la base con recuperación (18.4). *Aprendimos:* si David va a usar recuperación al traducir, tiene que entrenar con ella.

**3. Recuperación híbrida.** BM25 (SQLite FTS5) junto a los vectores, fusionados con Reciprocal Rank Fusion, glosario exacto y difuso, y el ejemplo más parecido al final. Se ajustó solo con dev ([evals/tuning.md](evals/tuning.md)):

| Configuración (dev, 222 frases) | Las dos | p50 |
| --- | ---: | ---: |
| Vectores, k=6 | 30.9 | 1.14 s |
| Híbrida, k=6 | 31.1 | 1.08 s |
| Híbrida, k=6 + difuso | 30.8 | 1.05 s |
| **Híbrida, k=6 + difuso, mejor ejemplo al final** | **32.5** | 1.04 s |
| Híbrida, k=4 + difuso | 30.8 | 0.88 s |
| Híbrida, k=8 + difuso | 32.7 | 1.18 s |

En la prueba: 18.5 → 19.4. *Aprendimos:* BM25 encuentra las palabras raras y los nombres que los embeddings difuminan, y el orden del contexto importa: poner el ejemplo más parecido al final aportó +1.7 por sí solo. k=8 empata dentro del ruido con prompts 25 % más largos, así que se quedó k=6.

**4. RAFT + retrotraducción.** El fine-tune ve el mismo contexto recuperado que David recibe al traducir (RAFT). Gemini tradujo al español 405 oraciones K'iche' con licencia (399 pares, $0.12), que solo entrenan español → K'iche'. 1 época con 5,579 ejemplos en 4 trozos de 1/4 de época, por el límite de 1 h de una tarea de GPU en Cloud Run ($3.09 de L4). Con recuperación híbrida: 18.3, −1.1 frente a la base híbrida. Con el mismo presupuesto de 1/4 de época, la retrotraducción sí aportó: 15.7 contra 14.6. *Aprendimos:* el fine-tune con estos datos todavía no le ganaba a la base con buena recuperación.

**5. MBR.** David genera 4 traducciones a temperatura 0.7 y se queda con la de mayor chrF++ promedio contra las otras. 18.3 → 21.5 (+3.2), y el fine-tune pasa a sumar +0.8 sobre la base con MBR. El p50 sube de 1.7 a 4.0 s. *Aprendimos:* el consenso es la segunda mayor ganancia y no cuesta dinero; cabía en el presupuesto de 5 s de la laptop y se apaga con `DAVID_MBR=0`.

**6. El nicho.** Una primera definición (palabras raras del diccionario) no funcionó: Goliath ganaba igual. En dev se vio dónde ganaba David (Pontoon 48.3 contra 26.2 de Gemini; COERLL 39.3 contra 30.7; UD 36.3 contra 45.0) y con eso se pre-registró Firefox Focus. Con la base: 30.2 contra 28.9, un empate en chrF++, pero 78 % contra 46 % en terminología. *Aprendimos:* el terreno de David es una memoria de traducción que Goliath no tiene; fue el primer corte donde David no iba atrás.

**7. Datos sintéticos anclados en el diccionario.** Gemini escribió frases con cada entrada del diccionario, y se intercambiaron palabras en oraciones de UD con formas atestiguadas: 5,295 + 198 pares filtrados por alfabeto, duplicados e ida y vuelta ($2.09). A/B en dev con el mismo presupuesto: 33.8 con 20 % de sintéticos (`n2b-s1`) contra 34.2 sin ellos (`n2a-s1`). *Aprendimos:* bajan la pérdida de entrenamiento porque son texto fácil, pero no traducen mejor. Quedaron fuera.

**8. Sesgo de logits hacia el diccionario.** Con `llama-server`, el primer token de una traducción exacta del diccionario recibe un sesgo, combinado con MBR de 8 muestras y prompts distintos. En dev (230 frases, `n2a-s1`):

| Decodificación | chrF++ dev | p50 |
| --- | ---: | ---: |
| Voraz | 34.2 | 1.2 s |
| MBR 4 | 34.1 | 4.2 s |
| MBR 8 multi-prompt | 35.0 | 7.1 s |
| MBR 8 multi-prompt + sesgo | 33.8 | 5.2 s |

*Aprendimos:* el sesgo empeora (−1.2 frente al mismo MBR sin sesgo). El MBR multi-prompt suma +0.8, pero su p50 de 7.1 s pasa el límite de 5 s. Ninguno de los dos entró.

**9. Más épocas y más español → K'iche'.** La receta de RAFT con retrotraducción, en trozos de 1/5 de época que continúan el adaptador anterior ($6.16 de L4). En dev (230 frases):

| David | es → quc | quc → es | Las dos | Con MBR-4 | p50 (MBR-4) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `raft-bt-s3` (1 época) | 37.8 | 35.3 | 36.6 | 37.6 | 3.9 s |
| `tm-a-s4` (1 época, es → quc ×1.5) | 36.7 | 34.7 | 35.8 | 36.7 | 4.0 s |
| `tm-a-e2-s4` (2 épocas) | 39.8 | 35.1 | 37.5 | 38.1 | 4.5 s |
| `tm-b-s1` (es → quc ×2, 0.4 épocas) | 35.4 | 31.8 | 33.7 | — | — |
| Goliath | 33.7 | 43.9 | 38.6 | — | 1.6 s |

Dos épocas contra una: +0.9 [−1.0, +2.9] sin MBR y +0.5 [−1.2, +2.4] con MBR. *Aprendimos:* son empates; entrenar más no compra una mejora medible, y subir español → K'iche' a ×2 tampoco. El adaptador de 2 épocas se guardó como punto de partida del experimento 11.

**10. Por qué pierde David en general.** El split dev (UD, Pontoon, COERLL, DUDH) no se parecía a la prueba, así que se creó `dev_domain` (514 frases de BOUQuET y Bloom fuera de la muestra de prueba). En la prueba David quedaba entre 11 y 22 puntos abajo en todas las fuentes, dominios y longitudes. David tenía 2,541 pares de oraciones con licencia (unas 31,000 palabras en K'iche'); solo las noticias de MINGOB, sin licencia, son cerca de 1 millón. Y un Goliath más grande no traduce mejor: `gemini-3.1-pro-preview` sacó 40.5 contra 40.6 de Flash en `dev_domain`, con 3 veces la latencia y 21 veces el costo. Además, el tokenizador de Gemma parte una palabra K'iche' en 2.64 tokens contra 1.41 en español ([evals/fertility.md](evals/fertility.md)). *Aprendimos:* la brecha es cuánto K'iche' hay en la web, no el tamaño del modelo; la única salida son más datos del dominio.

**11. Bloom retrotraducido + destilación (`mix-s7`).** Desde el adaptador de 2 épocas, tres ejecuciones en paralelo en 3 L4, cada una con 30 % de pares web como repaso. Bloom retrotraducido: 1,998 pares nuevos, en las dos direcciones. Destilación: Gemini escribió 10,585 frases cotidianas en español en los dominios de la prueba, tradujo 6,000 al K'iche' con el contexto de David y quedaron 2,409 tras los filtros; nunca entran al dataset, al índice, a dev ni a la prueba. En `dev_domain`, contra el adaptador de partida (22.1):

| Ejecución | Δ las dos [IC 95 %] | Por dirección |
| --- | ---: | --- |
| Bloom retrotraducido (`bl-s3`) | +1.5 [+0.7, +2.2] | quc → es +4.3; es → quc −1.2 |
| Destilación (`dst-s4`) | +2.1 [+1.5, +2.8] | es → quc +3.0 |
| **Las dos (`mix-s7`): 25.8** | **+3.6** [+2.9, +4.3] | +3.7 en cada dirección |

En la prueba, 25.7: +4.1 [+3.6, +4.7] sobre el David anterior, y la brecha con Goliath baja de 15.4 a 11.2. En la especialidad, 37.4 contra 28.9. *Aprendimos:* los dos efectos se suman. Goliath sirve de maestro una vez, por $13.94, y después David traduce sin él. Una segunda tanda de destilación (1,877 pares, $6.98) se generó, pero no entró en `mix-s7`.

**12. EmbeddingGemma 2 en la recuperación.** Se probó para actualizar a la versión nueva; con la versión 1 funciona mejor (dev 39.9 contra 38.8, general 25.8 contra 23.9), por eso se usa la 1. El 7 de octubre se probó EmbeddingGemma 2, el sucesor que Google acababa de publicar (270M de parámetros de texto, 768 dimensiones, 8K de contexto). Se reconstruyó el índice con sus vectores (calculados con `sentence-transformers` en un job de Cloud Run, con el mismo prefijo de similitud de frases) y se midió David en la nube con todo lo demás igual:

| Split | EmbeddingGemma (el de la demo) | EmbeddingGemma 2 |
| --- | ---: | ---: |
| dev (230 frases) | **39.9** | 38.8 |
| prueba general (600) | **25.8** | 23.9 |
| especialidad, Firefox Focus (144) | 35.3 | 37.0 |

Pierde en dev y en la prueba; en la especialidad sube 1.7, dentro de lo que varía MBR entre ejecuciones (35.3 y 37.4 con el mismo índice). Además, Ollama todavía no lo sirve en Linux (sus versiones en Ollama piden el runtime MLX, que no hay en la L4). *Aprendimos:* un modelo de embeddings más nuevo no mejora la recuperación de K'iche' por sí solo; la demo se queda con EmbeddingGemma.

**13. Frases nuevas de Pontoon.** La memoria de traducción pública de Pontoon (TMX por proyecto, MPL-2.0) tiene cadenas más nuevas que la copia de Hugging Face del dataset. Unidas con la de español por la cadena en inglés, y quitando las que están en cualquier split o en el índice, quedan 167 pares: 105 de Firefox Focus, 57 de Mozilla Monitor, 3 de Mozilla accounts y 2 de Firefox Send ([`evals/tm_new.py`](evals/tm_new.py)). En Firefox Focus David gana +6.1 [+3.0, +9.2]; en Mozilla Monitor pierde −10.7 [−20.2, −0.5]. *Aprendimos:* la memoria de traducción ayuda cuando el producto nuevo se parece a lo que ya se tradujo (textos cortos de interfaz); una página web de marketing no. De estas frases salieron 15 de los 26 ejemplos de la página.

### David en la GPU de Cloud Run

La página corre en Cloud Run y David en otro servicio de Cloud Run con una NVIDIA L4 (`europe-west4`, 4 vCPU, 16 GiB), con el modelo, EmbeddingGemma, el índice y sus kernels de GPU ya compilados dentro de la imagen. Medido el 7 de octubre con [`david/bench.py`](david/bench.py) ([resultados](david/bench-results.json)): los 26 ejemplos, 3 veces cada uno, con una copia del servicio de David que no usaba nadie más, así ninguna otra medición lo frenaba; Goliath, desde la página.

| | David (L4) | Goliath (Vertex AI) |
| --- | ---: | ---: |
| Tiempo, mediana de 78 traducciones | **0.81 s** | 1.47 s |
| Tiempo, p95 | **1.43 s** | 3.09 s |
| Traducciones donde David respondió primero | **74 de 78** | — |
| Costo de una traducción, como lo muestra la página | $0.00027 (0.9 s de GPU × $0.0002907/s) | **$0.00012** (107 tokens, tarifa de 2026) |
| Arranque desde cero (GPU apagada) | **39 s** (antes 3 min 24 s) | — |

Una persona usando la página: David responde antes casi siempre, y cada traducción le cuesta más que a Gemini con la tarifa de 2026. Con la de 2027 (el doble), Gemini cobraría $0.00024 por la misma frase y David seguiría en $0.00027. Dónde se invierte la cuenta, en [Proyecciones](#proyecciones-costo-y-tiempo).

#### Arranque en frío

David se apaga solo unos 15 minutos después de la última petición (mínimo 0 instancias: sin la página abierta no cobra). Al despertar, la mayor parte del tiempo se iba en algo que no era cargar el modelo: las bibliotecas de CUDA de Ollama compilan parte de su código para la L4 la primera vez que corre (compilación «JIT»), y en una instancia nueva eso pasaba siempre. Medido en los registros de Cloud Run, del arranque de la instancia a «David listo»:

| Fase | Antes | Después |
| --- | ---: | ---: |
| Arrancar el contenedor | 4 s | 5 s |
| Ollama encuentra la GPU | 15 s | 14 s |
| Cargar el modelo en la GPU | 66 s | 12 s |
| Cargar EmbeddingGemma | 26 s | 2 s |
| Primera traducción completa (recuperación + MBR-4) | 69 s | 2 s |
| **Total** | **3 min 1 s** | **35 s** |

Lo que cambió (en [`infra/20-david.sh`](infra/20-david.sh)):

- **Los kernels se compilan una sola vez.** Después de construir la imagen, un Cloud Run Job con una L4 la corre ([`david/warm_cache.py`](david/warm_cache.py)): carga los dos modelos y traduce frases cortas y largas en las dos direcciones, los ejemplos de la página y tandas de 2, 4 y 8 a la vez. CUDA guarda lo que compila (122 MB) y la imagen final lo lleva adentro ([`david/Dockerfile.cache`](david/Dockerfile.cache)). Probado en un job: con la caché, cargar el modelo pasó de 66 s a 8 s, EmbeddingGemma de 35 s a 2 s y la primera traducción de 62 s a 1 s; con la caché desactivada y todo lo demás igual, volvió a 62, 39 y 60 s. Si Cloud Run cambia su versión del driver de la GPU, CUDA ignora la caché y vuelve a compilar: más lento, nunca incorrecto; `make deploy-david` la regenera.
- **La imagen vive junto al servicio.** Estaba en Artifact Registry de `us-central1` y el servicio corre en `europe-west4`; ahora las dos imágenes de la demo están en `europe-west4`.
- **Antes, las primeras frases largas también tardaban** (de 4 a 10 s) porque compilaban kernels de otros tamaños. Con la caché, el primer minuto después de despertar da p95 de 1.2 s.
- **Lo que no ayudó:** desactivar la búsqueda de GPUs Vulkan de Ollama (la búsqueda de la GPU siguió en unos 14 s; queda desactivada porque David solo usa CUDA) y dar 8 vCPU y 32 GiB en vez de 4 y 16 (mismo tiempo por traducción, 36 % más caro por hora).

### Costo de entrenar a David

| Ejecuciones | Jobs | Duración de los jobs | Costo de L4 |
| --- | ---: | ---: | ---: |
| `tzij-2026-09` | 1 | 30 min | $0.70 |
| `raft-s0`, `raft-bt-s0` … `s3` | 5 | 130 min | $3.09 |
| `n2a`, `n2b` (sintéticos A/B) | 4 | 103 min | $2.44 |
| `tm-a`, `tm-a-e2`, `tm-b` (épocas) | 10 | 260 min | $6.16 |
| `bl`, `dst`, `mix` (ronda de datos) | 17 | 360 min | $8.52 |

Gemini como maestro: $0.12 (primera retrotraducción) + $2.09 (sintéticos, descartados) + $13.94 (ronda de datos) + $1.85 (medición con Gemini Pro). Todas las ejecuciones están en [`train/runs/`](train/runs/), con máquina, duración y costo por etapa.

## Proyecciones: costo y tiempo

Con los números medidos arriba ([`david/bench-results.json`](david/bench-results.json)), qué pasa con más uso. Precios de Cloud Run en `europe-west4` (catálogo de Cloud Billing, 7 de octubre de 2026): L4 sin redundancia zonal $0.0001867/s, vCPU $0.000018/s, GiB $0.000002/s. Gemini 3.8 Flash: $0.75 / $3.75 por millón de tokens de entrada / salida hasta el 31 de diciembre de 2026, y $1.50 / $7.50 desde el 1 de enero de 2027.

**Las fórmulas.**

- Hora de David = $0.0001867 + 4 × $0.000018 + 16 × $0.000002 = $0.0002907 por segundo = **$1.0465 por hora** encendido, traduzca o no.
- Traducción de Goliath = tokens de entrada × precio de entrada + tokens de salida × precio de salida: **$0.000122** en 2026 y **$0.000243** en 2027 (promedio de los 26 ejemplos: 107 tokens).
- Traducción de David = $1.0465 ÷ traducciones por hora. Cuántas puede hacer una L4 se midió mandándole varias frases a la vez:

| Frases a la vez | Traducciones por hora | Mediana | p95 |
| ---: | ---: | ---: | ---: |
| 1 | 3,970 | 0.87 s | 1.17 s |
| 2 | 4,951 | 1.34 s | 2.08 s |
| 4 | **5,548** | 2.29 s | 4.14 s |
| 8 | 5,338 | 4.87 s | 6.36 s |

  Con 4 a la vez la L4 llega a su máximo: unas **5,500 traducciones por hora**, a **$0.000189** cada una. Con una sola persona usándolo, $0.00027.

**Costo: dónde gana cada uno.** David cuesta lo mismo por hora con 1 o con 5,500 traducciones; Goliath, lo mismo por traducción. El punto de equilibrio es $1.0465 ÷ costo de una traducción de Goliath:

| | Tarifa de Gemini 2026 | Tarifa de Gemini 2027 |
| --- | ---: | ---: |
| Equilibrio, traducciones por hora | 8,600 (más de lo que da una L4) | **4,300** |
| David más barato | nunca, con una L4 en Cloud Run | **con más de 4,300 traducciones por hora** |
| A plena carga (5,500 por hora) | David $0.000189, Goliath **$0.000122** | **David $0.000189**, Goliath $0.000243 (David 22 % más barato) |

Por mes, con David encendido todo el tiempo (730 horas, $764):

| Traducciones al mes | Goliath 2026 | Goliath 2027 | David (1 L4) |
| ---: | ---: | ---: | ---: |
| 100,000 | **$12** | **$24** | $764 |
| 1,000,000 | **$122** | **$243** | $764 |
| 3,140,000 (equilibrio en 2027) | **$382** | $764 | $764 |
| 4,050,000 (una L4 a plena carga) | **$493** | $986 | **$764** |

Y en una charla: la página abierta una hora más los 15 minutos que David tarda en apagarse cuestan $1.31 de GPU; 200 traducciones de Gemini, $0.02.

**Qué dice esto.**

- **Con poco uso, Goliath es más barato,** y por mucho: se paga solo lo que se traduce. Una GPU encendida para una persona es cara.
- **Con mucho uso y la tarifa de 2027, David es más barato:** desde unas 4,300 traducciones por hora (3.1 millones al mes con la GPU siempre encendida), y 22 % más barato a plena carga. Con la tarifa de 2026, una sola L4 en Cloud Run no llega.
- **Fuera de este cálculo:** en hardware propio (la laptop donde se hicieron los experimentos, o una GPU ya pagada) cada traducción de David cuesta $0 adicional; y una máquina con L4 dedicada o con descuento por uso comprometido cobra menos por hora que Cloud Run, lo que baja el equilibrio. No se midieron aquí.

**Tiempo: dónde gana cada uno.**

- **Una persona a la vez (la demo): David,** 0.81 s contra 1.47 s de mediana y 1.43 s contra 3.09 s en p95; respondió primero en 74 de 78.
- **Hasta 2 frases a la vez:** David apenas adelante en la mediana (1.34 s contra 1.47 s) y mejor en p95 (2.08 s contra 3.09 s).
- **4 o más a la vez:** gana Goliath. Una L4 reparte su capacidad y David sube a 2.3 s de mediana con 4 y 4.9 s con 8; Gemini escala por su cuenta. Para más tráfico, más instancias de David (`--max-instances`), cada una con su costo por hora.
- **Despertar:** si David estaba apagado, la primera frase espera el arranque en frío (35 s desde que arranca la instancia); Gemini no tiene ese costo.

## Por qué la demo usa solo el modelo final

La página muestra un solo David: `tzij-2026-10-mix-s7` + recuperación híbrida + MBR-4. Las demás variantes quedan medidas arriba, pero no salen en la demo, por estas razones:

- **Es el mejor en las dos medidas.** 25.7 en la prueba general, contra 21.5 del David anterior y 20.7 de la mejor base, y 37.4 en la especialidad, contra 30.2 de la base con el mismo índice.
- **Es el único que puede jugar la especialidad limpiamente.** Los fine-tunes anteriores (`tzij-2026-09`, `raft-s0`, `raft-bt-s0` … `s3`) entrenaron con Firefox Focus antes de que se apartara; con ellos los ejemplos medirían memoria, no traducción.
- **MBR-4 vale la pena.** Sin MBR, `mix-s7` saca 25.1 (35.9 en la especialidad); con MBR-4, 25.7 (37.4). En la laptop tardaba 4.14 s; en la L4 de Cloud Run, la página lo recibe en 0.9 s (mediana). El MBR multi-prompt del experimento 8 sacaba más en dev, pero tardaba 7.1 s en la laptop.
- **La demo enseña el caso que David gana.** En la memoria de traducción, David traduce mejor que Goliath; eso es lo que la página compara. En traducción general Goliath sigue arriba (36.9 contra 25.7), y es más claro en K'iche' → español (−16.4). Esos números están arriba y en la [bitácora](docs/BITACORA.md), pero la charla no muestra esa dirección ni esas frases.
- **Una comparación por frase tiene que ser justa con los dos.** Los botones salen solo de casos de uso que David gana como conjunto, nunca de frases sueltas que gana dentro de un caso que pierde. Cada una se tradujo 3 veces con los dos modelos en vivo, y queda solo si las 3 veces David saca 50 o más y le gana a Goliath por 15 o más. De Firefox Focus se probaron 37 y pasaron 26; la página muestra 6, las más fáciles de entender para cualquiera. De los diccionarios se probaron 27 palabras y pasaron 15. Las salidas, los puntajes y los tiempos medidos están en [`duel/examples.json`](duel/examples.json).
- **La recuperación sigue con EmbeddingGemma 1.** Se probó EmbeddingGemma 2 para actualizar a la versión nueva; con la versión 1 funciona mejor (dev 39.9 contra 38.8, general 25.8 contra 23.9), por eso se usa la 1 ([experimento 12](#lo-que-dijo-cada-experimento)).

## Arranque rápido

```bash
cp .env.example .env                       # modelos, buckets y regiones; nunca se sube .env
uv sync
gcloud auth login && gcloud auth application-default login
make deploy                                # proyecto, jobs, David en su GPU y la página
open "$(make -s page-url)"                 # David y Goliath lado a lado
make test                                  # pruebas con modelos simulados (MOCK_AI=1): sin GPU ni nube
```

**Reproducirlo en tu proyecto.** Los modelos, los datasets y el índice viven en buckets privados de este proyecto (`gs://ai-experiments-487722-tzij-*`): no se publican, porque algunas fuentes solo permiten redistribución privada (BOUQuET) y los modelos se derivan de todas. Todo se reconstruye desde las fuentes con licencia: cambia en `.env` `GOOGLE_CLOUD_PROJECT`, `DATA_BUCKET_URI`, `MODELS_BUCKET` y `STAGING_BUCKET` a tu proyecto y tus buckets, crea el secreto `hf-token` con un token de Hugging Face que haya aceptado los términos de Gemma (y de BOUQuET, si quieres la prueba completa) y corre `make deploy`: arma los datasets (`make data-cloud`), el índice, el entrenamiento en Cloud Run Jobs (`make train`, `make train-finish`), David y la página. Necesitas cuota de GPU L4 en Cloud Run en la región de `DEMO_REGION`. Costos de referencia en [Costo de entrenar a David](#costo-de-entrenar-a-david). Paso a paso en [docs/ONBOARDING.md](docs/ONBOARDING.md).

**Licencias.** El código está bajo Apache 2.0 ([`LICENSE`](LICENSE)); los datos y los modelos conservan sus licencias, listadas en [`THIRD_PARTY.md`](THIRD_PARTY.md).

Ningún modelo se baja a la laptop. Para medir contra el David de la nube (`make eval`, `make index`), `make david-proxy` ([detalle](docs/COMANDOS.md)).

## Documentación

- [docs/DEMO.md](docs/DEMO.md): guion de la demo (la página), con capturas, qué decir y tiempos.
- [docs/ONBOARDING.md](docs/ONBOARDING.md): requisitos, instalación, nube, datos, entrenamiento, pruebas, solución de problemas y el día de la charla.
- [docs/BITACORA.md](docs/BITACORA.md): la historia de David iteración por iteración, con fechas y costo.
- [docs/DECISIONES.md](docs/DECISIONES.md): cada decisión técnica, resultados completos y versiones.
- [docs/COMANDOS.md](docs/COMANDOS.md): desplegar, medir y todos los comandos `make`.
- [docs/ESTRUCTURA.md](docs/ESTRUCTURA.md): qué corre dónde en la nube, pipeline y mapa del repositorio.
- [docs/CREDITOS.md](docs/CREDITOS.md): fuentes de datos, dueños y licencias.
- [MODEL_CARD.md](MODEL_CARD.md): qué es David, con qué datos, resultados y límites.
- [evals/report.md](evals/report.md): reporte de evaluación por fuente, longitud, dominio y fallos.
- [docs/diagrams/](docs/diagrams/): arquitectura, pipeline, resultados y bitácora (HTML, SVG y PNG).
- [data/SOURCES.md](data/SOURCES.md) y [data/DATASHEET.md](data/DATASHEET.md): fuentes y conteos por fuente.
