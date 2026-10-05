# Evaluación humana a ciegas — plantilla (opcional)

**Opcional.** El demo y `make eval` no dependen de ella. Si hay una persona hablante nativa de K'iche' disponible, sirve para complementar chrF++. chrF++ mide
parecido de caracteres con una referencia; esta evaluación mide si la traducción *sirve*.

## Cómo se prepara

1. Correr `make eval` (deja las traducciones en `evals/runs/<run>/`).
2. Correr `make human-eval-sheet`: toma **50 frases** del conjunto de prueba (muestra estable) y
   las traducciones de los modelos elegidos, las mezcla y reemplaza el nombre del modelo por una
   letra (A, B, …). Escribe:
   - `evals/runs/<run>/human_eval_sheet.csv` — la hoja para la evaluadora (sin nombres de modelo).
   - `evals/runs/<run>/human_eval_key.json` — la clave letra → modelo. **No se comparte** hasta
     terminar.
3. La evaluadora califica cada fila sin ver la referencia ni el modelo.

## Escalas (1–5)

**Adecuación** — ¿dice lo mismo que el original?

| | |
| --- | --- |
| 5 | Todo el significado está, sin errores. |
| 4 | Casi todo; un detalle menor falta o cambia. |
| 3 | La idea principal está, pero con errores que la persona nota. |
| 2 | Solo fragmentos del significado. |
| 1 | No dice lo mismo, o no es la lengua pedida. |

**Fluidez** — ¿suena natural para alguien que habla la lengua (sin mirar el original)?

| | |
| --- | --- |
| 5 | Natural; así lo diría una persona hablante. |
| 4 | Correcto, con algún giro poco usual. |
| 3 | Se entiende, pero se nota que no es natural. |
| 2 | Difícil de entender; errores gramaticales serios. |
| 1 | Incomprensible, u otra lengua / otra variante no pedida. |

Columna `notas`: variante dialectal, palabras en español sin traducir, ortografía no ALMG.

## Resultados

Todavía no se ha hecho ninguna evaluación humana; los resultados del repositorio son de chrF++
(`evals/report.md`, `evals/niche_results.md`). Al terminar una, se abre la clave, se promedian
adecuación y fluidez por modelo desde la hoja, y la tabla y 3–5 líneas de observaciones (errores
recurrentes, dónde ayudó la recuperación, dónde el modelo grande inventó palabras) se agregan aquí
con la fecha, el evento, la variante de K'iche' de quien evaluó y el run de `make eval`.
