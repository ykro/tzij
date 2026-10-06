# Tzij — traductor español ↔ K'iche' que funciona sin internet

Demo de la charla **"David vs. Goliath: cómo un modelo pequeño le gana a un modelo frontier"**. Tzij ("palabra" en K'iche') traduce entre español y K'iche' (ISO 639-3 `quc`), el idioma maya más hablado de Guatemala.

- **David** es Gemma 4 E4B ajustado con LoRA (`tzij-2026-10-mix-s7`). Corre en Ollama, en la laptop, con un índice de recuperación híbrido hecho solo con datos K'iche' con licencia y con decodificación MBR.
- **Goliath** es Gemini 3.8 Flash en Vertex AI, usado como lo usa cualquiera.

La demo es una sola página, `/traductor/`: escribes una frase (o tocas un ejemplo) y David y Goliath la traducen al mismo tiempo, lado a lado, cada uno con su tiempo y su costo. En los ejemplos, frases de la interfaz de Firefox Focus, la página muestra también la traducción correcta, la que hicieron personas, y qué tanto se parece a ella cada una. Sin internet, Goliath dice "Sin conexión" y David sigue traduciendo.

[English version](README.en.md)

![La página del traductor: David y Goliath traducen la misma frase de Firefox Focus](docs/demo/traductor-3-ejemplo.png)

## Qué vas a aprender

1. **Datos con licencia y split por fuente:** cada registro K'iche' lleva URL y licencia, y una fuente entera es de prueba o de entrenamiento.
2. **Qué compra cada paso:** la recuperación es el mayor salto; el fine-tune empezó a sumar (+5.7) cuando sus datos se parecieron al dominio de la prueba.
3. **Goliath enseña una vez:** Gemini retrotraduce K'iche' con licencia y escribe datos de destilación por unos $14, y David sirve para siempre sin internet.
4. **Un nicho pre-registrado:** con una memoria de traducción que Goliath no tiene, David gana por +8.5 chrF++.
5. **Offline por diseño:** modelo, embeddings, índice, servicio y página viven en la laptop.

## La demo: el traductor

| | David | Goliath |
| --- | --- | --- |
| Qué es | Gemma 4 E4B ajustado (`tzij-2026-10-mix-s7`) + recuperación híbrida + MBR-4 | Gemini 3.8 Flash, sin datos extra |
| Dónde corre | En la laptop (Ollama) | En la nube (Vertex AI) |
| Costo de cada traducción | $0 | El real de la llamada (unos $0.0001 por frase corta) |
| Sin internet | Traduce igual | "Sin conexión" |

- **Ejemplos:** 12 frases de Firefox Focus en español, con su traducción correcta al K'iche' (Mozilla Pontoon, licencia MPL-2.0). Cada una se tradujo en vivo 3 veces con los dos modelos, y solo quedaron las que David tradujo siempre cerca de la correcta (chrF++ de 50 o más) y por lo menos 15 puntos más cerca que Goliath. Están en [`duel/examples.json`](duel/examples.json), con las salidas y los puntajes medidos; `make examples` las vuelve a revisar.
- **"Se parece a la correcta":** es chrF++ contra la traducción hecha por personas, en porcentaje. Solo sale con los ejemplos: una frase escrita no tiene traducción correcta con qué comparar, así que la página muestra las dos traducciones, el tiempo y el costo.
- **Dirección:** los ejemplos y la demo son español → K'iche', el caso que David gana. La página también traduce del K'iche' al español (botón ⇄), pero esa dirección no se muestra en la charla (ver [abajo](#por-qué-la-demo-usa-solo-el-modelo-final)).

El guion, con capturas y tiempos, está en [docs/DEMO.md](docs/DEMO.md).

![Arquitectura: laptop sin internet frente a Google Cloud](docs/diagrams/architecture.png)

## Resultados (evaluación)

Medido con `make eval` (ejecución `final-20261002`, dataset `20261002-173447`) y `make niche`. Detalle en [evals/report.md](evals/report.md) y [evals/niche_results.md](evals/niche_results.md).

| | David (`mix-s7` + híbrida + MBR-4) | Goliath (`gemini-3.8-flash`) |
| --- | ---: | ---: |
| **Especialidad:** memoria de traducción, Firefox Focus, 144 frases es → quc (chrF++) | **37.4** | 28.9 |
| General: 600 frases de prueba de Bloom y BOUQuET, las dos direcciones (chrF++) | 25.7 | **36.9** |
| Latencia p50 / p95 en la prueba general | 4.14 s / 13.4 s | 1.73 s / 4.71 s |
| Costo por 1,000 traducciones | **$0** | $0.29 |
| Sin internet | **traduce igual** | no produce nada |

En la especialidad David gana por **+8.5** [IC 95 %: +4.7, +12.7] en un producto que nunca vio. En traducción general Goliath va arriba por 11.2 puntos; la brecha es K'iche' general, no un tipo de frase ([experimento 10](#lo-que-dijo-cada-experimento)).

## Experimentos

Todos los números salen de [`evals/`](evals/), [`train/runs/`](train/runs/) y la [bitácora](docs/BITACORA.md), donde está la historia completa, con fechas. Reglas: las 600 frases de prueba (150 por fuente y dirección, de Bloom y BOUQuET) nunca están en el índice ni en el entrenamiento; las decisiones se toman con un split de desarrollo (dev, y desde el experimento 10, `dev_domain`); la prueba se usa para el número final. chrF++ va de 0 a 100: más es mejor.

### Resumen

| # | Experimento | Variante | chrF++ prueba (600) | Otra medida | Latencia p50 | Costo único | Resultado |
| ---: | --- | --- | ---: | --- | ---: | ---: | --- |
| 0 | Base, sin datos | `gemma4:e4b` | 11.7 | — | 1.31 s | $0 | Punto de partida |
| 1 | + recuperación por vectores | `gemma4:e4b+rag` | 18.5 | — | 1.84 s | $0 | La mayor ganancia |
| 2 | Fine-tune sin contexto de recuperación | `tzij-2026-09` + recuperación | 17.6* | — | — | $0.70 (+$0.41 cancelado) | Callejón sin salida |
| 3 | Recuperación híbrida (BM25 + vectores) | `gemma4:e4b+hybrid` | 19.4 | dev 30.9 → 32.5 | 1.75 s | $0 | Se queda |
| 4 | RAFT + retrotraducción de Gemini, 1 época | `tzij-2026-10-raft-bt-s3+hybrid` | 18.3 | — | 1.72 s | $3.09 L4 + $0.12 Gemini | Sola no ayuda |
| 5 | + MBR (4 muestras) | `tzij-2026-10-raft-bt-s3+hybrid+mbr4` | 21.5 | — | 3.96 s | $0 | David en escena del 2 al 5 de octubre |
| 6 | El nicho pre-registrado (Firefox Focus) | `gemma4:e4b+hybrid+mbr4` | — | especialidad 30.2 vs 28.9 | — | $0 | Empate en chrF++, gana en terminología |
| 7 | Datos sintéticos anclados en el diccionario | `tzij-2026-10-n2b-s1` | — | dev 33.8 vs 34.2 | — | $2.09 Gemini + $1.14 L4 | Fuera |
| 8 | Sesgo de logits hacia el diccionario | `n2a-s1` + llama-server | — | dev 33.8 vs 35.0 | 5.2 s | $0 | Fuera |
| 9 | Más épocas y más español → K'iche' | `tzij-2026-10-tm-a-e2-s4` | — | dev 37.5 vs 36.6 | 4.5 s | $6.16 L4 | Empate |
| 10 | Por qué pierde David; Gemini Pro | `gemini-3.1-pro-preview` | — | `dev_domain` 40.5 vs 40.6 | — | $1.85 | La brecha es K'iche' general |
| 11 | Bloom retrotraducido + destilación | `tzij-2026-10-mix-s7+hybrid+mbr4` | **25.7** | especialidad **37.4** vs 28.9 | 4.14 s | $8.52 L4 + $13.94 Gemini | **El David de la demo** |

\* Medido sobre el dataset del 30 de septiembre (las mismas fuentes de prueba). Ahí la base con recuperación sacaba 18.4.

### Todas las variantes en la prueba

Las 600 frases de prueba, ejecución `final-20261002` ([evals/report.md](evals/report.md)).

| Variante | es → quc | quc → es | Las dos | p50 | p95 | Costo / 1,000 |
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

### Lo que dijo cada experimento

**0. La base.** Gemma 4 E4B con las mismas instrucciones que Gemini, sin contexto. 11.7 chrF++, y 7.5 en español → K'iche': el modelo casi no escribe K'iche'. *Aprendimos:* es lo que obtiene cualquiera que descarga un modelo pequeño; el punto de partida tiene que estar medido.

**1. Recuperación por vectores.** Índice local de unos 7,000 pares y entradas de diccionario con licencia, con EmbeddingGemma y `sqlite-vec`; David recibe 6 ejemplos y 6 entradas de glosario por frase. 11.7 → 18.5 (español → K'iche': 7.5 → 18.2). *Aprendimos:* un modelo pequeño no sabe K'iche', pero copia y adapta bien lo que le damos. Ningún otro paso movió tanto a David.

**2. Fine-tune sin contexto (`tzij-2026-09`).** LoRA r=16, 1 época con 5,180 ejemplos, entrenado sin el contexto de recuperación; 22 min de L4 en Cloud Run, $0.70. Solo, sube a la base de 11.5 a 15.2; con recuperación saca 17.6, 0.8 por debajo de la base con recuperación (18.4). *Aprendimos:* si David va a usar recuperación en escena, tiene que entrenar con ella.

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

**4. RAFT + retrotraducción.** El fine-tune ve el mismo contexto recuperado que David recibe en escena (RAFT). Gemini tradujo al español 405 oraciones K'iche' con licencia (399 pares, $0.12), que solo entrenan español → K'iche'. 1 época con 5,579 ejemplos en 4 trozos de 1/4 de época, por el límite de 1 h de una tarea de GPU en Cloud Run ($3.09 de L4). Con recuperación híbrida: 18.3, −1.1 frente a la base híbrida. Con el mismo presupuesto de 1/4 de época, la retrotraducción sí aportó: 15.7 contra 14.6. *Aprendimos:* el fine-tune con estos datos todavía no le ganaba a la base con buena recuperación.

**5. MBR.** David genera 4 traducciones a temperatura 0.7 y se queda con la de mayor chrF++ promedio contra las otras. 18.3 → 21.5 (+3.2), y el fine-tune pasa a sumar +0.8 sobre la base con MBR. El p50 sube de 1.7 a 4.0 s. *Aprendimos:* el consenso es la segunda mayor ganancia y no cuesta dinero; cabe en el presupuesto de 5 s del escenario y se apaga con `MBR_ON_STAGE=0`.

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

### Costo de entrenar a David

| Ejecuciones | Jobs | Duración de los jobs | Costo de L4 |
| --- | ---: | ---: | ---: |
| `tzij-2026-09` | 1 | 30 min | $0.70 |
| `raft-s0`, `raft-bt-s0` … `s3` | 5 | 130 min | $3.09 |
| `n2a`, `n2b` (sintéticos A/B) | 4 | 103 min | $2.44 |
| `tm-a`, `tm-a-e2`, `tm-b` (épocas) | 10 | 260 min | $6.16 |
| `bl`, `dst`, `mix` (ronda de datos) | 17 | 360 min | $8.52 |

Gemini como maestro: $0.12 (primera retrotraducción) + $2.09 (sintéticos, descartados) + $13.94 (ronda de datos) + $1.85 (medición con Gemini Pro). Todas las ejecuciones están en [`train/runs/`](train/runs/), con máquina, duración y costo por etapa.

## Por qué la demo usa solo el modelo final

La página muestra un solo David: `tzij-2026-10-mix-s7` + recuperación híbrida + MBR-4. Las demás variantes quedan medidas arriba, pero no salen en la demo, por estas razones:

- **Es el mejor en las dos medidas.** 25.7 en la prueba general, contra 21.5 del David anterior y 20.7 de la mejor base, y 37.4 en la especialidad, contra 30.2 de la base con el mismo índice.
- **Es el único que puede jugar la especialidad limpiamente.** Los fine-tunes anteriores (`tzij-2026-09`, `raft-s0`, `raft-bt-s0` … `s3`) entrenaron con Firefox Focus antes de que se apartara; con ellos los ejemplos medirían memoria, no traducción. `make preflight` falla si `LOCAL_MODEL_TAG` es uno de esos.
- **MBR-4 cabe en el escenario.** Sin MBR, `mix-s7` responde en 1.64 s y saca 25.1 (35.9 en la especialidad); con MBR-4, 4.14 s y 25.7 (37.4). Los 4 s quedan dentro del presupuesto de 5 s. El MBR multi-prompt del experimento 8 sacaba más en dev, pero tardaba 7.1 s.
- **La demo enseña el caso que David gana.** En la memoria de traducción, David traduce mejor que Goliath, gratis y sin internet; eso es lo que la página compara. En traducción general Goliath sigue arriba (36.9 contra 25.7), y es más claro en K'iche' → español (−16.4). Esos números están arriba y en la [bitácora](docs/BITACORA.md), pero la charla no muestra esa dirección ni esas frases.
- **Una comparación por frase tiene que ser justa con los dos.** Los ejemplos se eligieron entre frases que ninguno de los dos vio, y se verificaron en vivo con los dos modelos. Las salidas y los puntajes medidos están en [`duel/examples.json`](duel/examples.json).

## Arranque rápido

```bash
cp .env.example .env                       # modelos, buckets y puertos; nunca se sube .env
uv sync && ollama pull gemma4:e4b && ollama pull embeddinggemma
gcloud auth application-default login      # ADC para Vertex AI y Cloud Storage
make data-pull && make niche-data && make web   # dataset con Firefox Focus apartado, índice y página
make pull-model TAG=tzij-2026-10-mix-s7 && make up
open http://127.0.0.1:8787/traductor/      # David y Goliath lado a lado
```

Para ensayar sin la nube ni GPU: `make up MOCK_AI=1` ([detalle](docs/COMANDOS.md)).

## Documentación

- [docs/DEMO.md](docs/DEMO.md): guion de la demo (el traductor), con capturas, qué decir y tiempos.
- [docs/ONBOARDING.md](docs/ONBOARDING.md): requisitos, instalación, nube, datos, entrenamiento, pruebas, solución de problemas y checklist del día.
- [docs/BITACORA.md](docs/BITACORA.md): la historia de David iteración por iteración, con fechas y costo.
- [docs/DECISIONES.md](docs/DECISIONES.md): cada decisión técnica, resultados completos y versiones.
- [docs/COMANDOS.md](docs/COMANDOS.md): arranque paso a paso y todos los comandos `make`.
- [docs/ESTRUCTURA.md](docs/ESTRUCTURA.md): qué corre en la laptop y en la nube, pipeline y mapa del repositorio.
- [docs/CREDITOS.md](docs/CREDITOS.md): fuentes de datos, dueños y licencias.
- [MODEL_CARD.md](MODEL_CARD.md): qué es David, con qué datos, resultados y límites.
- [evals/report.md](evals/report.md): reporte de evaluación por fuente, longitud, dominio y fallos.
- [docs/diagrams/](docs/diagrams/): arquitectura, pipeline, resultados y bitácora (HTML, SVG y PNG).
- [data/SOURCES.md](data/SOURCES.md) y [data/DATASHEET.md](data/DATASHEET.md): fuentes y conteos por fuente.
