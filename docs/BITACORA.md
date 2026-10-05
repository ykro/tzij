# Bitácora de David

La historia de David, iteración por iteración: qué cambió, por qué, qué resultado dio, cuánto
costó y cuándo. Los números de prueba salen siempre de las mismas 600 frases (150 por fuente y
dirección, de Bloom y BOUQuET), que nunca están en el índice ni en el entrenamiento. Las
decisiones se toman con el split dev; el conjunto de prueba se usa para el número final.

![Bitácora de David: chrF++ por iteración contra Goliath](diagrams/bitacora.png)

*chrF++ de David en las 600 frases de prueba. Goliath (Gemini 3.8 Flash, sin datos extra) está
arriba, punteado. Fuente: [`diagrams/bitacora.py`](diagrams/bitacora.py), que lee las predicciones
de `evals/runs/`.*

## Resumen

| # | Fecha | Iteración | chrF++ prueba | Δ | Costo único | Resultado |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 0 | 30 sep | Gemma 4 E4B base, sin datos | 11.7 | — | $0 | Punto de partida |
| 1 | 30 sep | + recuperación por vectores | 18.5 | +6.8 | $0 | La mayor ganancia de toda la bitácora |
| 2 | 1 oct | Fine-tune sin contexto de recuperación (`tzij-2026-09`) | 17.6* | −0.8* | $0.70 | **Callejón sin salida** |
| 3 | 1 oct | Recuperación híbrida (BM25 + vectores, RRF) | 19.4 | +0.9 | $0 | Ajustada en dev |
| 4 | 2 oct | RAFT + retrotraducción de Gemini | 18.3 | −1.1 | $0.12 + $3.09 | Sola no ayuda |
| 5 | 2 oct | + MBR (4 muestras) | **21.5** | +3.2 | $0 | En escena |
| 6 | 2 oct | El nicho: memoria de traducción (Firefox Focus) | 30.2 vs 28.9 | +1.3 | $0 | **Empate en chrF++; David gana en terminología (78 % contra 46 %)** |
| 7 | 2 oct | Datos sintéticos anclados en el diccionario | 33.8 vs 34.2 en dev | −0.4 | $2.09 + $1.14 | **No ayudaron: fuera** |
| 8 | 2 oct | Sesgo de logits hacia el diccionario (llama-server) | 33.8 vs 35.0 en dev | −1.2 | $0 | **No ayudó: fuera** |
| 9 | 4 oct | Más épocas (hasta 2) y más español → Kʼicheʼ | 37.5 vs 36.6 en dev | +0.9 | $6.16 | **Empate en dev: el David en escena no cambia** |

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
- **Costo:** $0.70, más $0.41 de una primera ejecución cancelada porque no cabía en la hora máxima
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
- **Costo:** $0.12 de Gemini, una sola vez. $3.09 de L4 (5 jobs), más $0.27 de la ejecución que se
  quedó sin memoria.

## 5. MBR: elegir por consenso (2 de octubre)

- **Qué:** David genera 4 traducciones a temperatura 0.7 y se queda con la que tiene el mayor
  chrF++ promedio contra las otras (decodificación de mínimo riesgo de Bayes).
- **Resultado en prueba:** 18.3 → **21.5** (+3.2), la mayor ganancia después de la recuperación.
  Con MBR el fine-tune sí suma: +0.8 sobre la base con MBR (21.5 contra 20.7).
- **Costo:** $0, pero el p50 sube de 1.7 a 4.0 s y el p95 a 14 s. Entra al escenario porque el
  p50 queda por debajo del límite de 5 s, y se apaga con `MBR_ON_STAGE=0`.

## 6. El nicho: una memoria de traducción que Goliath no tiene (2 de octubre)

Una primera definición del nicho, basada en palabras raras de nuestros diccionarios, no funcionó:
Goliath ganaba igual. Así que el nicho se redefinió en dev antes de tocar la prueba.

- **Lo que mostró dev:** David gana donde nuestros datos son una memoria de traducción que Goliath
  no tiene.

  | Dev, español → Kʼicheʼ | David | Gemini |
  | --- | ---: | ---: |
  | Pontoon (interfaz de Firefox) | 48.3 | 26.2 |
  | COERLL (curso) | 39.3 | 30.7 |
  | UD, ejemplos del diccionario de la ALMG (públicos en GitHub) | 36.3 | 45.0 |

- **Qué:**
  - se aparta un producto completo de Pontoon, Firefox Focus: 144 pares español → Kʼicheʼ;
  - los demás productos de Mozilla se quedan como memoria de traducción;
  - se mide chrF++ y la precisión exacta de terminología al estilo WMT (41 términos).

  La regla, el producto y los términos quedaron pre-registrados y publicados en git antes de
  calcular nada ([`evals/niche.md`](../evals/niche.md)). Después se sumaron a la memoria dos
  glosarios con licencia: los nombres de Unicode CLDR en Kʼicheʼ y el glosario de FLORES-Mayas.
- **Resultado** (David = Gemma 4 E4B base + híbrida + MBR, que nunca vio Focus;
  [`evals/niche_results.md`](../evals/niche_results.md)):

  | | David | Goliath | David − Goliath [IC 95 %] | Terminología, David | Terminología, Goliath |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | Índice pre-registrado | 29.7 | 28.9 | +0.9 [−2.8, +4.6] | 83 % | 46 % |
  | + CLDR y FLORES-Mayas | 30.2 | 28.9 | +1.3 [−2.3, +5.3] | 78 % | 46 % |

- **Lectura honesta:**
  - en chrF++ es un **empate**: David va arriba, pero el intervalo incluye el cero;
  - en terminología David **gana sin discusión** (+37 puntos [+17, +56]), porque usa los términos
    de la memoria del producto y Goliath los inventa;
  - es el primer corte donde David no va atrás.
- **Costo:** $0.

## 7. Datos sintéticos anclados en el diccionario: no ayudaron (2 de octubre)

- **Qué:** Gemini escribió frases con cada entrada del diccionario, con un sesgo hacia frases
  cortas, y se intercambiaron sustantivos y verbos de las oraciones de UD con formas atestiguadas
  que tienen los mismos rasgos.
- **Filtros:**
  - la palabra del diccionario tiene que estar en el lado Kʼicheʼ;
  - solo letras del alfabeto de la ALMG;
  - nada repetido de dev, de la prueba ni del nicho;
  - ida y vuelta: el chrF++ tiene que llegar al percentil 25 de los pares reales de dev (26.8).

  Quedaron 5,295 pares anclados al diccionario y 198 de UD, por $2.09 de Gemini.
- **A/B en dev,** con el mismo presupuesto (2 trozos, unos 2,700 ejemplos, español → Kʼicheʼ ×1.5,
  sin Firefox Focus):

  | | chrF++ dev | Costo L4 |
  | --- | ---: | ---: |
  | sin sintéticos | **34.2** | $1.30 |
  | con 20 % de sintéticos | 33.8 | $1.14 |

- **Decisión:** se quedan fuera del entrenamiento. Bajaron la pérdida de entrenamiento porque son
  texto fácil, pero no mejoraron dev.

## 8. Sesgo de logits hacia el diccionario: no ayudó (2 de octubre)

- **Qué:** cuando la recuperación encuentra una traducción exacta del diccionario para una
  palabra de contenido de la entrada, `llama-server` (llama.cpp) le da un sesgo de logits al primer
  token de esa forma (sesgar la palabra completa hacía que el modelo la repitiera en bucle). Se
  combina con MBR de 8 muestras y prompts distintos (contextos barajados y submuestreados). Ollama
  no tiene sesgo de logits.
- **Resultado en dev** (230 frases; David = `tzij-2026-10-n2a-s1`, 0.4 épocas):

  | Decodificación | chrF++ dev | p50 |
  | --- | ---: | ---: |
  | voraz | 34.2 | 1.2 s |
  | MBR 4 | 34.1 | 4.2 s |
  | MBR 8 multi-prompt (llama-server) | **35.0** | 7.1 s |
  | MBR 8 multi-prompt + sesgo 2 | 33.8 | 5.2 s |

- **Decisión:** el sesgo queda fuera (−1.2 frente al mismo MBR sin sesgo). El MBR multi-prompt
  suma +0.8, pero su p50 de 7.1 s pasa el límite de 5 s del escenario, así que tampoco entra.
- **Costo:** $0.

## 9. Más épocas y más español → Kʼicheʼ: empate (4 de octubre)

- **Qué:** la misma receta de RAFT con retrotraducción, entrenada en trozos de un quinto de época
  que continúan el adaptador anterior. Dos preguntas: (A) ¿ayuda entrenar más, de 0.4 a 1 y a 2
  épocas, con español → Kʼicheʼ ×1.5?; (B) ¿ayuda subir español → Kʼicheʼ a ×2 con el presupuesto
  de 0.4 épocas? B tiene un factor de confusión: sus contextos de recuperación salen del índice
  actual (con CLDR y FLORES), y los de A del índice anterior.
- **Resultado en dev** (230 frases, índice actual, mismas predicciones de Goliath):

  | David | es → quc | quc → es | ambas | con MBR 4 | p50 (MBR 4) |
  | --- | ---: | ---: | ---: | ---: | ---: |
  | En escena (`raft-bt-s3`, 1 época) | 37.8 | 35.3 | 36.6 | 37.6 | 3.9 s |
  | A, 1 época (`tm-a-s4`) | 36.7 | 34.7 | 35.8 | 36.7 | 4.0 s |
  | A, 2 épocas (`tm-a-e2-s4`) | 39.8 | 35.1 | **37.5** | **38.1** | 4.5 s |
  | B, español → Kʼicheʼ ×2, 0.4 épocas (`tm-b-s1`) | 35.4 | 31.8 | 33.7 | — | — |
  | Goliath (`gemini-3.8-flash`) | 33.7 | 43.9 | 38.6 | — | 1.6 s |

- **Bootstrap pareado** (2,000 remuestreos, IC 95 %): A con 2 épocas contra el David en escena da
  +0.9 [−1.0, +2.9] sin MBR y +0.5 [−1.2, +2.4] con MBR 4. Son empates.
- **Lo que sí sale claro en dev:** los dos Davids le ganan a Goliath en español → Kʼicheʼ (+5.5
  [+1.0, +10.3] el de escena con MBR 4) y pierden en Kʼicheʼ → español (−8.0 [−14.6, −1.7]). En
  la prueba (Bloom y BOUQuET) David pierde en las dos direcciones, así que esta ventaja es de las
  fuentes de dev (COERLL, Pontoon, UD, DUDH) y no se puede generalizar.
- **Decisión:** el David en escena no cambia. Más épocas no compran una mejora medible, y subir
  español → Kʼicheʼ a ×2 no ayuda: B saca 33.7, contra 34.2 de A con el mismo presupuesto
  (sección 7, medido con el índice anterior).
- **Costo:** $6.16 de L4 (A, época 1: $1.81; A, época 2: $3.12; B: $1.23), más el merge y el GGUF
  en la laptop.

## Dónde gana David hoy y dónde pierde

- **Gana siempre:** costo ($0 contra $0.29 por cada 1,000 traducciones), privacidad (nada sale
  de la laptop) y disponibilidad (sin internet Goliath no produce nada).
- **Gana en terminología:** en el nicho (Firefox Focus con la memoria de traducción de los demás
  productos) usa el término correcto el 78–83 % de las veces, contra el 46 % de Goliath. En chrF++
  empata.
- **Pierde:**
  - en general, por 15.4 puntos en la prueba;
  - en Kʼicheʼ → español, donde Goliath escribe en un idioma que domina;
  - en todos los textos que probablemente ya están en la web (Bloom, UD).

## Qué haríamos después

- **Más memoria de traducción con licencia,** que es donde David gana. Lo más valioso son los
  ~3,800 textos de MINGOB, que necesitan permiso.
- **Una persona hablante que valide la prueba,** para que chrF++ deje de ser el único juez.
- **Destilar el MBR en el modelo** (fine-tune sobre las salidas de consenso). Así se gana la
  calidad de MBR sin pagar su latencia en escena.
