# Bitácora de David

La historia de David, iteración por iteración: qué cambió, por qué, qué resultado dio, cuánto
costó y cuándo. Los números de prueba salen siempre de las mismas 600 frases (150 por fuente y
dirección, de Bloom y BOUQuET), que nunca están en el índice ni en el entrenamiento. Las
decisiones se toman con el split dev; el conjunto de prueba se usa para el número final.

![Bitácora de David: chrF++ por iteración contra Goliath](diagrams/bitacora.png)

*chrF++ de David en toda la prueba (línea roja) y en el nicho pre-registrado v1 (línea azul).
Goliath (Gemini 3.8 Flash, sin datos extra) está arriba, punteado. Fuente:
[`diagrams/bitacora.py`](diagrams/bitacora.py), que lee las predicciones de `evals/runs/`.*

## Resumen

| # | Fecha | Iteración | chrF++ prueba | Δ | Costo único | Resultado |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 0 | 30 sep | Gemma 4 E4B base, sin datos | 11.7 | — | $0 | Punto de partida |
| 1 | 30 sep | + recuperación por vectores | 18.5 | +6.8 | $0 | La mayor ganancia de toda la bitácora |
| 2 | 1 oct | Fine-tune sin contexto de recuperación (`tzij-2026-09`) | 17.6* | −0.8* | $0.70 | **Callejón sin salida** |
| 3 | 1 oct | Recuperación híbrida (BM25 + vectores, RRF) | 19.4 | +0.9 | $0 | Ajustada en dev |
| 4 | 2 oct | RAFT + retrotraducción de Gemini | 18.3 | −1.1 | $0.12 + $3.09 | Sola no ayuda |
| 5 | 2 oct | + MBR (4 muestras) | **21.5** | +3.2 | $0 | En escena |
| — | 1 oct | Gemma de 12B | — | — | — | **Descartado** |
| 6 | 2 oct | Nicho v1: vocabulario raro de nuestros diccionarios | 21.4 vs 37.3 | — | $0 | **Goliath gana** |
| 7 | 2 oct | Nicho v2: memoria de traducción (Pontoon) | en curso | | | Pre-registrado |
| 8 | 2 oct | Datos sintéticos anclados en el diccionario | en curso | | $2.09 | |
| 9 | 2 oct | Decodificación guiada por el diccionario | en curso | | $0 | |

\* La iteración 2 se midió sobre el dataset del 30 de septiembre (las mismas fuentes de prueba,
referencias aún sin validar). Ahí la base con recuperación sacaba 18.4.

Goliath: **36.9** en toda la prueba, $0.29 por cada 1,000 traducciones, y nada sin internet.

## 0. El punto de partida (30 de septiembre)

- **Qué:** Gemma 4 E4B en Ollama, sin contexto, con las mismas instrucciones que Gemini.
- **Resultado:** 11.7 chrF++, y 7.5 en español → Kʼicheʼ: el modelo casi no escribe Kʼicheʼ.
- **Por qué empezar aquí:** es lo que cualquiera obtiene al descargar un modelo pequeño.

## 1. Recuperación por vectores (30 de septiembre)

- **Qué:** índice local con unos 7,000 pares y entradas de diccionario con licencia por
  dirección, construido con EmbeddingGemma y `sqlite-vec`. David recibe 6 ejemplos y 6 entradas
  de glosario por frase.
- **Por qué:** un modelo pequeño no sabe Kʼicheʼ, pero puede copiar y adaptar lo que le damos.
- **Resultado:** 11.7 → 18.5. En español → Kʼicheʼ, 7.5 → 18.2. Ninguna otra iteración
  movió tanto a David.
- **Costo:** $0. Todo corre en la laptop.

## 2. Callejón sin salida: fine-tune sin contexto (1 de octubre)

- **Qué:** LoRA (r=16) sobre Gemma 4 E4B, 1 época con 5,180 ejemplos, entrenado **sin** el
  contexto de recuperación en el prompt (`tzij-2026-09`). Cloud Run Job con una L4: 22 min de
  entrenamiento y unos $0.70. El merge y el GGUF se hicieron en la laptop.
- **Resultado:** solo, sube a E4B de 11.5 a 15.2. Con recuperación, 17.6: **0.8 por debajo** de
  la base con recuperación (18.4).
- **Por qué falló:** el modelo aprendió a traducir sin glosario y en escena lo recibe. Lo que
  aprendió choca con lo que le damos.
- **Lección:** si David va a usar recuperación en escena, tiene que entrenar con ella (iteración 4).
- **Costo:** $0.70, más $0.41 de una primera corrida cancelada porque no cabía en la hora máxima
  de una tarea de GPU.

## 3. Recuperación híbrida (1 de octubre)

- **Qué:**
  - BM25 sobre SQLite FTS5 junto a los vectores, fusionados con Reciprocal Rank Fusion;
  - glosario exacto y difuso (variantes ortográficas);
  - el ejemplo más parecido va al final, justo antes de la frase.
- **Por qué:** los embeddings difuminan las palabras raras y los nombres; BM25 los encuentra.
- **Cómo se decidió:** solo con dev ([`evals/tuning.md`](../evals/tuning.md)). En dev pasó de
  30.9 a 32.5; poner el mejor ejemplo al final aportó +1.7 por sí solo.
- **Resultado en prueba:** 18.5 → 19.4 (+0.9).
- **Costo:** $0.

## 4. RAFT + retrotraducción: Goliath enseña una vez (1–2 de octubre)

- **Qué:**
  - **RAFT:** el fine-tune ve el mismo contexto recuperado que David recibe en escena, sin el
    propio par (cero respuestas filtradas en el contexto).
  - **Retrotraducción:** Gemini tradujo al español 405 oraciones Kʼicheʼ monolingües con licencia
    (Wikipedia en Kʼicheʼ en Incubator, Space Scoop) y salieron 399 pares. Solo entrenan
    español → Kʼicheʼ, y el lado Kʼicheʼ sigue siendo 100 % humano.
  - **Entrenamiento:** 1 época con 5,579 ejemplos, en 4 trozos de 1/4 de época (`-s0` … `-s3`),
    porque una tarea de GPU en Cloud Run dura como máximo 1 h. Con lote 8 la L4 se quedó sin
    memoria, así que se usó lote 2 con acumulación 8 y un máximo de 1,024 tokens.
- **Resultado en prueba:**
  - con recuperación híbrida, 18.3: **−1.1** frente a la base híbrida;
  - con el mismo presupuesto (1/4 de época), la retrotraducción aporta +1.1 (15.7 contra 14.6
    sin ella).
- **Costo:** $0.12 de Gemini, una sola vez. $3.09 de L4 (5 jobs), más $0.27 de la corrida que se
  quedó sin memoria.

## 5. MBR: elegir por consenso (2 de octubre)

- **Qué:** David genera 4 traducciones a temperatura 0.7 y se queda con la que tiene el mayor
  chrF++ promedio contra las otras (decodificación de mínimo riesgo de Bayes).
- **Resultado en prueba:** 18.3 → **21.5** (+3.2), la mayor ganancia después de la recuperación.
  Con MBR el fine-tune sí suma: +0.8 sobre la base con MBR (21.5 contra 20.7).
- **Costo:** $0, pero el p50 sube de 1.7 a 4.0 s y el p95 a 14 s. Entra al escenario porque el
  p50 queda por debajo del límite de 5 s, y se apaga con `MBR_ON_STAGE=0`.

## Callejón sin salida: un Gemma más grande (1 de octubre)

Se planeó un Gemma de 12B como punto de control y se descartó antes de medirlo. La tesis de la
charla es "modelo pequeño + datos": un David de 12B ya no es pequeño, y solo serviría para
comparar. Se borró el modelo y todo su código. No hay números de 12B.

## 6. Nicho v1: vocabulario de nuestros diccionarios (2 de octubre)

- **Qué:** el nicho se definió y se publicó en git **antes** de mirar resultados por oración
  ([`evals/niche.md`](../evals/niche.md)). Entran las frases con al menos una palabra de
  nuestros diccionarios cuya forma en Kʼicheʼ nunca aparece en un corpus de Kʼicheʼ de la web de
  211,516 tokens. Los umbrales salieron de dev, sin usar ninguna salida de modelo.
- **Resultado** (257 frases; [`evals/niche_results.md`](../evals/niche_results.md)):

  | | David | Goliath | David − Goliath [IC 95 %] | David gana |
  | --- | ---: | ---: | ---: | ---: |
  | Nicho, ambas direcciones | 21.4 | 37.3 | **−15.9** [−17.0, −14.7] | 9 % |
  | Fuera del nicho | 21.7 | 36.3 | −14.6 [−16.2, −12.9] | 15 % |
  | Frases cortas (el corte más cercano) | 13.7 | 20.4 | −6.7 [−11.6, −2.3] | 32 % |

- **Lectura honesta:** David **no** gana el nicho; ahí incluso pierde por un poco más. Una
  explicación probable es que Goliath ya vio estos textos: los libros de Bloom están en la web
  desde 2012.
- **Lo que sí se ve en dev:** David gana donde nuestros datos son una memoria de traducción que
  Goliath no tiene.

  | Dev, español → Kʼicheʼ | David | Gemini |
  | --- | ---: | ---: |
  | Pontoon (interfaz de Firefox) | 48.3 | 26.2 |
  | COERLL (curso) | 39.3 | 30.7 |
  | UD, ejemplos del diccionario de la ALMG (públicos en GitHub) | 36.3 | 45.0 |

  De ahí sale el nicho v2.

## 7. Nicho v2: una memoria de traducción que Goliath no tiene (en curso)

- **Qué:** se aparta un producto completo de Pontoon (`focus-for-android`, Firefox Focus: 144
  pares español → Kʼicheʼ) y los demás productos se quedan como memoria de traducción. Se mide
  chrF++ y la precisión exacta de terminología al estilo WMT (41 términos). Quedó pre-registrado
  y publicado en git antes de calcular nada en prueba.
- **Contendientes válidos:**
  - la base `gemma4:e4b` + híbrida + MBR, limpia por construcción;
  - un fine-tune reentrenado desde cero sin ese producto.

  `tzij-2026-10-raft-bt-s3` vio esos pares al entrenar y queda fuera.

## 8. Datos sintéticos anclados en el diccionario (en curso)

- **Qué:** Gemini escribe frases con cada entrada del diccionario, con un sesgo hacia frases
  cortas, que son el corte más cercano. Además, se intercambian sustantivos y verbos de las
  oraciones de UD con otras formas atestiguadas que tienen los mismos rasgos.
- **Filtros:**
  - la palabra del diccionario tiene que estar en el lado Kʼicheʼ;
  - solo letras del alfabeto de la ALMG;
  - nada repetido de dev ni de prueba;
  - ida y vuelta: Gemini traduce el Kʼicheʼ de vuelta al español, y el chrF++ contra el español
    original tiene que llegar al percentil 25 de los pares reales de dev (26.8).
- **Resultado de la generación:** 5,295 pares anclados al diccionario y 198 de UD.
  - Descartes: 1,430 por alfabeto, 2,722 por ida y vuelta, 89 sin la palabra.
  - Costo de Gemini: $2.09.
  - En el entrenamiento A/B ocupan el 19.8 % de los ejemplos (`origin=synthetic`, con método,
    modelo, prompt y semilla).
- **Entrenamiento:** el A/B (con y sin sintéticos, español → Kʼicheʼ ×1.5) está listo para la L4.

## 9. Decodificación guiada por el diccionario (en curso)

- **Qué:** cuando la recuperación encuentra una traducción exacta del diccionario para una
  palabra de contenido de la entrada, esa forma se vuelve una restricción.
  - (a) Se pide en el prompt, y entre los candidatos de MBR solo compiten los que la usan; si
    ninguno la usa, decide el MBR normal.
  - (b) Con `llama-server` (llama.cpp), un sesgo de logits sobre esos tokens, con MBR de 8
    muestras y prompts distintos (contextos barajados y submuestreados). Ollama no tiene sesgo
    de logits.
- **Estado:** el ajuste de (a) en dev está corriendo. El cliente de `llama-server` y el MBR
  multi-prompt ya tienen pruebas; falta correrlos.

## Dónde gana David hoy y dónde pierde

- **Gana siempre:** costo ($0 contra $0.29 por cada 1,000 traducciones), privacidad (nada sale
  de la laptop) y disponibilidad (sin internet Goliath no produce nada).
- **Gana en traducción, en dev:** español → Kʼicheʼ donde nuestros datos son memoria de
  traducción (Pontoon, COERLL).
- **Pierde:**
  - en general, por 15.4 puntos en la prueba;
  - en el nicho de vocabulario raro (v1);
  - en Kʼicheʼ → español, donde Goliath escribe en un idioma que domina;
  - en todos los textos que probablemente ya están en la web (Bloom, UD).

## Qué haríamos después

- **Más memoria de traducción con licencia,** que es donde David gana. Lo más valioso son los
  ~3,800 textos de MINGOB, que necesitan permiso.
- **Una persona hablante que valide la prueba,** para que chrF++ deje de ser el único juez.
- **Destilar el MBR en el modelo** (fine-tune sobre las salidas de consenso). Así se gana la
  calidad de MBR sin pagar su latencia en escena.
