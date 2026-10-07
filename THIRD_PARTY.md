# Licencias de terceros

[English below](#third-party-licenses)

El **código** de este repositorio está bajo la licencia Apache 2.0 ([`LICENSE`](LICENSE)). Los
**datos y modelos** de terceros conservan su propia licencia:

| Qué | Dónde | Fuente | Licencia |
| --- | --- | --- | --- |
| Frases de ejemplo de la página y frases nuevas de la memoria de traducción | `duel/examples.json`, `evals/tm_new.jsonl`, `evals/niche_terms.json` | Mozilla Pontoon (localización de Firefox Focus y otros productos) | MPL-2.0 |
| Pares de ejemplo para el modo sin IA y las pruebas | `duel/mock_data/index_pairs.jsonl` | UD K'iche'-IU (CC BY-SA 4.0, con permiso de la ALMG y de Telma Can Pixabaj), COERLL (CC BY 4.0), GATITOS (CC BY 4.0), PanLex (CC0) | La de cada registro (campo `license`) |
| Fragmentos de formato para probar los lectores | `tests/fixtures/raw/` | Bloom Library, COERLL, eBible, UD K'iche'-IU | La de cada fuente (ver [`data/SOURCES.md`](data/SOURCES.md)) |
| Modelo David (`tzij-2026-10-mix-s7`) | No está en el repo (bucket privado de GCS) | Ajuste de Gemma 4 E4B | [Términos de uso de Gemma](https://ai.google.dev/gemma/terms) |
| Embeddings | No está en el repo | EmbeddingGemma | [Términos de uso de Gemma](https://ai.google.dev/gemma/terms) |

Los datos crudos y el dataset procesado no están en el repo (viven en GCS). BOUQuET, cuyos
términos solo permiten redistribución privada, nunca se versiona. La atribución completa por
fuente está en [`docs/CREDITOS.md`](docs/CREDITOS.md) y [`data/SOURCES.md`](data/SOURCES.md).

## Third-party licenses

The **code** is licensed under Apache 2.0 ([`LICENSE`](LICENSE)). Third-party **data and models**
keep their own licenses (table above): Pontoon strings are MPL-2.0; mock and fixture pairs carry
their source license per record (UD K'iche'-IU is CC BY-SA 4.0); the fine-tuned David model and
EmbeddingGemma are not in this repository and are subject to the
[Gemma Terms of Use](https://ai.google.dev/gemma/terms). Raw data and BOUQuET (private
redistribution only) are never committed. Full attribution: [`docs/CREDITOS.en.md`](docs/CREDITOS.en.md).
