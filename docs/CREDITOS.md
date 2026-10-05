# Créditos y procedencia

De dónde salen los datos de Tzij: licencias y atribución. Volver al [README](../README.md). [English version](CREDITOS.en.md).

## Datos: licencias y atribución

Cada fuente, con dueño, licencia, tamaño, dominio, ortografía y estado, está en [`data/SOURCES.md`](../data/SOURCES.md). Los conteos por fuente y las razones de descarte están en [`data/DATASHEET.md`](../data/DATASHEET.md). Los datos crudos nunca se suben a git: algunas licencias permiten usarlos pero no redistribuirlos.

| Fuente | Dueño | Licencia | Uso |
| --- | --- | --- | --- |
| [Bloom Library, libros K'iche'](https://bloomlibrary.org/language:quc) (solo CC BY) | Principalmente Ministerio de Educación de Guatemala / USAID, vía SIL Bloom Library | CC BY 4.0 por libro; se excluyen los NC/ND | Prueba |
| [BOUQuET](https://huggingface.co/datasets/facebook/bouquet) | Meta FAIR y traductores de la comunidad | CC BY 4.0, acceso restringido; términos: solo evaluación, redistribución privada | Prueba (solo evaluación) |
| [UD K'iche'-IU](https://github.com/UniversalDependencies/UD_Kiche-IU) | F. Tyers, R. Henderson (Indiana University) | CC BY-SA 4.0; oraciones usadas con permiso de la Academia de Lenguas Mayas de Guatemala y de Telma Can Pixabaj | Entrenamiento / índice |
| [COERLL, curso de K'iche'](https://tzij.coerll.utexas.edu/) | COERLL / LLILAS / AILLA, UT Austin | CC BY 4.0 | Entrenamiento / índice |
| [Declaración Universal de Derechos Humanos](https://github.com/eric-muller/udhr) | OHCHR; XML del proyecto UDHR in Unicode | Reproducción libre citando a OHCHR como fuente | Entrenamiento / índice |
| [Mozilla Pontoon](https://huggingface.co/datasets/ayymen/Pontoon-Translations) | Comunidad de localización de Mozilla; empaquetado por ayymen | MPL-2.0 | Entrenamiento / índice |
| [Nuevo Testamento, K'iche' de Totonicapán](https://ebible.org/quctt/) + Biblia Libre para el Mundo | Pioneer Bible Translators (quc); BLM (es) | quc: CC BY 4.0 (© 2022 Pioneer Bible Translators); es: dominio público | Entrenamiento (máx. 30 %) |
| [GATITOS](https://huggingface.co/datasets/google/smol) | Google Research (SMOL/GATITOS) | CC BY 4.0 | Léxico |
| [PanLex](https://panlex.org/) | PanLex / Long Now Foundation; empaquetado por cointegrated | CC0 1.0 | Léxico |
| [Wikcionario](https://es.wiktionary.org/) vía [kaikki.org](https://kaikki.org/eswiktionary/) | Colaboradores de Wikcionario | CC BY-SA 4.0 | Léxico |
| [Unicode CLDR](https://github.com/unicode-org/cldr), nombres de emoji en K'iche' | Colaboradores de Unicode CLDR | Unicode License V3 | Léxico (memoria de traducción) |
| [Glosario FLORES-Mayas](https://github.com/transducens/floresmayas) (`quc/vocab.json`, commit fijo) | Transducens (Universitat d'Alacant) con traductores de la PLFM | Apache-2.0 | Léxico (memoria de traducción); nunca junto a una prueba basada en FLORES |
| [Wikipedia en K'iche' (Incubator `Wp/quc`)](https://incubator.wikimedia.org/wiki/Wp/quc) | Colaboradores de Wikimedia | CC BY-SA 4.0 | K'iche' monolingüe para retrotraducción (entrenamiento) |
| [Space Scoop en K'iche'](https://www.unawe.org/kids/archive/lang/quc/viewall/) | Universe Awareness (UNAWE) / SpaceScoop.org | CC BY 4.0 (crédito a SpaceScoop.org) | K'iche' monolingüe para retrotraducción (entrenamiento) |
| [Bloom Library, libros solo en K'iche'](https://bloomlibrary.org/language:quc) (solo CC BY) | Principalmente Ministerio de Educación de Guatemala / USAID, vía SIL Bloom Library | CC BY 4.0 por libro; se excluyen los NC/ND | K'iche' monolingüe para retrotraducción (entrenamiento, las dos direcciones; 2,052 oraciones). Nunca los libros bilingües de prueba |

**Pares destilados** (`origin=distilled_gemini`): son salida de Gemini, español escrito por Gemini y traducido por Gemini al K'iche' con el contexto recuperado de David, filtrado por alfabeto, longitud e ida y vuelta (`pipeline/distill.py`). Solo entrenan: nunca entran al dataset, al índice, a dev ni a la prueba, y no son datos K'iche' de ninguna fuente.

Las fuentes que piden autorización previa (publicaciones de la ALMG fuera de los ejemplos permitidos, PLFM, diccionarios del SIL, entre otras) están marcadas como *needs permission* y no se usan. Los datos K'iche' pertenecen a sus hablantes y a sus instituciones.

Toda traducción que aparece en una captura (`docs/screenshots/`, `docs/demo/`) es salida del modelo, sin validar.
