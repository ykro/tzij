# Tzij — traductor español ↔ K'iche' que funciona sin internet

Demo de la charla **"David vs. Goliath: cómo un modelo pequeño le gana a un modelo frontier"**. Tzij ("palabra" en K'iche') traduce entre español y K'iche' (ISO 639-3 `quc`), el idioma maya más hablado de Guatemala. **David** es Gemma 4 E4B ajustado con LoRA (`tzij-2026-10-mix-s7`) en Ollama, en la laptop, con un índice de recuperación híbrido construido solo con datos K'iche' con licencia y decodificación MBR. **Goliath** es Gemini 3.8 Flash en Vertex AI, usado como lo usa cualquiera. Los dos traducen la misma frase en paralelo en el escenario. **Con la memoria de traducción de una organización, David le gana a Goliath**; en traducción general, Goliath sigue arriba. Una persona hablante nativa vota desde su teléfono sin saber qué modelo hizo cada traducción.

[English version](README.en.md)

## Qué vas a aprender

1. **Datos con licencia y split por fuente:** cada registro K'iche' lleva URL y licencia, y una fuente entera es de prueba o de entrenamiento.
2. **Qué compra cada paso:** la recuperación es el mayor salto; el fine-tune empezó a sumar (+5.7) cuando sus datos se parecieron al dominio de la prueba.
3. **Goliath enseña una vez:** Gemini retrotraduce K'iche' con licencia y escribe datos de destilación por unos $14, y David sirve para siempre sin internet.
4. **Un nicho pre-registrado:** con una memoria de traducción que Goliath no tiene, David gana por +8.5 chrF++.
5. **Offline por diseño:** modelo, embeddings, índice, servicio y vistas viven en la laptop.

## El resultado

| | David (laptop) | Goliath (nube) |
| --- | ---: | ---: |
| **Especialidad:** memoria de traducción, Firefox Focus (144 frases), chrF++ | **37.4** | 28.9 |
| General: `make eval`, 600 frases de prueba, chrF++ | 25.7 | **36.9** |
| Costo por 1,000 traducciones | **$0** | $0.29 |
| Sin internet | **traduce igual** | no produce nada |

En la especialidad David gana por +8.5 [IC 95 %: +4.7, +12.7] en un producto que nunca vio. En traducción general Goliath sigue arriba por 11.2 puntos: la brecha es K'iche' general ([bitácora, sección 10](docs/BITACORA.md)). Tabla completa, ablación y conclusiones en [docs/DECISIONES.md](docs/DECISIONES.md#resultados).

**Lo que no funcionó** (detalle, números y costo en la [bitácora](docs/BITACORA.md)):

- Fine-tune sin el contexto de recuperación: 0.8 puntos por debajo de la base con recuperación (sección 2).
- Datos sintéticos anclados en el diccionario: 33.8 contra 34.2 en dev, fuera del entrenamiento (sección 7).
- Sesgo de logits hacia el diccionario: −1.2 en dev frente al mismo MBR sin sesgo (sección 8).
- Más épocas y más español → K'iche': empate en dev, el David en escena no cambia (sección 9).

![Arquitectura: laptop sin internet frente a Google Cloud](docs/diagrams/architecture.png)

![Qué se prueba en la demo](docs/diagrams/que-se-prueba.png)

## Arranque rápido

```bash
cp .env.example .env                       # modelos, buckets y puertos; nunca se sube .env
uv sync && ollama pull gemma4:e4b && ollama pull embeddinggemma
gcloud auth application-default login      # ADC para Vertex AI y Cloud Storage
make data-pull && make index && make web   # dataset, índice y vistas
make pull-model TAG=tzij-2026-10-mix-s7 && make up
open http://127.0.0.1:8787/presentador/    # E: frase de evaluación · /: frase en vivo
```

Para ensayar sin la nube ni GPU: `make up MOCK_AI=1` ([detalle](docs/COMANDOS.md)).

## Documentación

- [docs/DEMO.md](docs/DEMO.md): guion de la demo, con capturas, teclas, qué decir y tiempos.
- [docs/ONBOARDING.md](docs/ONBOARDING.md): requisitos, instalación, nube, datos, entrenamiento, pruebas, solución de problemas y checklist del día.
- [docs/BITACORA.md](docs/BITACORA.md): la historia de David iteración por iteración, con costo, incluido lo que no funcionó.
- [docs/DECISIONES.md](docs/DECISIONES.md): lo que enseña la demo en detalle, cada decisión técnica, resultados completos y versiones.
- [docs/COMANDOS.md](docs/COMANDOS.md): arranque paso a paso y todos los comandos `make`.
- [docs/ESTRUCTURA.md](docs/ESTRUCTURA.md): qué corre en la laptop, en la LAN y en la nube, pipeline y mapa del repositorio.
- [docs/CREDITOS.md](docs/CREDITOS.md): fuentes de datos, dueños y licencias.
- [MODEL_CARD.md](MODEL_CARD.md): qué es David, con qué datos, resultados y límites.
- [evals/report.md](evals/report.md): reporte de evaluación por fuente, longitud, dominio y fallos.
- [docs/diagrams/](docs/diagrams/): arquitectura, qué se prueba, pipeline, resultados y bitácora (HTML, SVG y PNG).
- [data/SOURCES.md](data/SOURCES.md) y [data/DATASHEET.md](data/DATASHEET.md): fuentes y conteos por fuente.
