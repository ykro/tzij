# Credits and provenance

Where Tzij's data comes from: licenses and attribution. Back to the [README](../README.en.md). [Versión en español](CREDITOS.md).

## Data: licenses and attribution

Every source, with owner, license, size, domain, orthography and status, is listed in [`data/SOURCES.md`](../data/SOURCES.md). Per-source counts and drop reasons are in [`data/DATASHEET.md`](../data/DATASHEET.md). Raw data is never committed: some licenses allow use but not redistribution.

| Source | Owner | License | Use |
| --- | --- | --- | --- |
| [Bloom Library K'iche' books](https://bloomlibrary.org/language:quc) (CC BY only) | Mostly Ministerio de Educación de Guatemala / USAID, via SIL Bloom Library | CC BY 4.0 per book; NC/ND books excluded | Test |
| [BOUQuET](https://huggingface.co/datasets/facebook/bouquet) | Meta FAIR and community translators | CC BY 4.0, gated; terms: evaluation only, private redistribution | Test (evaluation only) |
| [UD K'iche'-IU](https://github.com/UniversalDependencies/UD_Kiche-IU) | F. Tyers, R. Henderson (Indiana University) | CC BY-SA 4.0; sentences used with permission of the Academia de Lenguas Mayas de Guatemala and Telma Can Pixabaj | Training / index |
| [COERLL K'iche' course](https://tzij.coerll.utexas.edu/) | COERLL / LLILAS / AILLA, UT Austin | CC BY 4.0 | Training / index |
| [Universal Declaration of Human Rights](https://github.com/eric-muller/udhr) | OHCHR; XML from the UDHR in Unicode project | Free reproduction citing OHCHR as the source | Training / index |
| [Mozilla Pontoon](https://huggingface.co/datasets/ayymen/Pontoon-Translations) | Mozilla localization community; packaged by ayymen | MPL-2.0 | Training / index |
| [New Testament, K'iche' of Totonicapán](https://ebible.org/quctt/) + Biblia Libre para el Mundo | Pioneer Bible Translators (quc); BLM (es) | quc: CC BY 4.0 (© 2022 Pioneer Bible Translators); es: public domain | Training (max 30%) |
| [GATITOS](https://huggingface.co/datasets/google/smol) | Google Research (SMOL/GATITOS) | CC BY 4.0 | Lexicon |
| [PanLex](https://panlex.org/) | PanLex / Long Now Foundation; packaged by cointegrated | CC0 1.0 | Lexicon |
| [Spanish Wiktionary](https://es.wiktionary.org/) via [kaikki.org](https://kaikki.org/eswiktionary/) | Wiktionary contributors | CC BY-SA 4.0 | Lexicon |
| [Unicode CLDR](https://github.com/unicode-org/cldr), K'iche' emoji names | Unicode CLDR contributors | Unicode License V3 | Lexicon (translation memory) |
| [FLORES-Mayas glossary](https://github.com/transducens/floresmayas) (`quc/vocab.json`, pinned commit) | Transducens (Universitat d'Alacant) with PLFM translators | Apache-2.0 | Lexicon (translation memory); never together with a FLORES-based test |
| [K'iche' Wikipedia (Incubator `Wp/quc`)](https://incubator.wikimedia.org/wiki/Wp/quc) | Wikimedia contributors | CC BY-SA 4.0 | Monolingual K'iche' for back-translation (Spanish → K'iche' only) |
| [Space Scoop in K'iche'](https://www.unawe.org/kids/archive/lang/quc/viewall/) | Universe Awareness (UNAWE) / SpaceScoop.org | CC BY 4.0 (credit SpaceScoop.org) | Monolingual K'iche' for back-translation (Spanish → K'iche' only) |

Sources that require prior authorization (ALMG publications beyond the permitted examples, PLFM, SIL dictionaries, among others) are marked *needs permission* and are not used. K'iche' data belongs to its speakers and their institutions.

Every translation shown in a screenshot (`docs/screenshots/`, `docs/demo/`) is unvalidated model output.
