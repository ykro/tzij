# Sources — Spanish ↔ K'iche' (`quc`)

Every candidate found during source research (September 2026), with its paperwork.
Status:

- **used** — license or terms allow this use; downloaded by `pipeline/` (see `pipeline/sources/`).
- **needs permission** — possibly great, but the license is unclear, it asks for prior
  authorization, or it sits behind a login. Left out until someone gets permission.
- **rejected** — reason given.

Rules applied: nothing behind a login, nothing whose terms forbid it, no machine-translated
or synthetic K'iche' (`origin=web` on every record). Raw files are never committed: they
live in `data/raw/` (gitignored) and in `gs://ai-experiments-487722-tzij-data/raw/`; the
download code is what's versioned.

Counts, splits and drop reasons per source are in `data/DATASHEET.md`.

All of this was gathered automatically (no human collected or reviewed data). Monolingual K'iche'
sources feed only the back-translation step (`pipeline/monolingual.py` → `pipeline/back_translate.py`):
Gemini writes the Spanish side once, the K'iche' side stays human-written, and the pairs are used
only to train Spanish → K'iche', never for test or retrieval.

## Used (14)

| Source (pipeline name) | URL | Owner | License / terms | Size (raw) | Domain | Orthography | Date | Role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Bloom Library K'iche' books, CC BY subset (`bloom_kiche`) | https://bloomlibrary.org/language:quc | Mostly Ministerio de Educación de Guatemala / USAID, via SIL Bloom Library | CC BY 4.0 per book (130 of 142 K'iche' books). The 12 CC BY-NC-SA / NC-ND books are excluded. Read-online HTML fetched from Bloom's public harvester bucket; book list from the public API the website uses (no account) | 142 books; ~536 page-aligned quc/es text blocks in the ~28 bilingual CC BY books | Education (children's stories, parent guides) | Modern ALMG; a few books tagged `quc` are actually Mam (filtered) | 2012–2024 | **test** |
| BOUQuET benchmark, sentence level dev + test (`bouquet`) | https://huggingface.co/datasets/facebook/bouquet | Meta FAIR + community translators | CC BY 4.0, **gated**: the presenter's Hugging Face account accepted the terms; the token is Secret Manager `hf-token`. Terms: **evaluation only** (never training or retrieval), redistribution only privately or behind a gate. Kept out of git (raw and processed data are gitignored; copies only in the private bucket) and not shown in the on-stage evaluation rounds | 1,358 spa→quc sentences (504 dev + 854 test) | Multi-domain: conversation, how-to, narration, reflection… (the `domain` field is kept) | Modern, mostly ALMG | 2025–2026 | **test** (evaluation only) |
| Wikipedia in K'iche', Wikimedia Incubator `Wp/quc` (`incubator_quc`) | https://incubator.wikimedia.org/wiki/Wp/quc | Wikimedia contributors | CC BY-SA 4.0 | 112 pages; 76 sentences kept after filtering (many pages are mostly Spanish medical stubs) | Encyclopedic / health | Modern | 2015–2024 | **monolingual**: K'iche' side of Gemini back-translation (train, es→quc only) |
| Space Scoop K'iche' (`spacescoop_quc`) | https://www.unawe.org/kids/archive/lang/quc/viewall/ | Universe Awareness (UNAWE) / SpaceScoop.org, volunteer translators | CC BY 4.0 ("provided that the text is credited to SpaceScoop.org") | 22 astronomy-news articles for children; 318 sentences. The K'iche' versions are freer and shorter than the Spanish ones, so they can't be paragraph-aligned | Science / education | Modern | 2015–2016 | **monolingual**: back-translation (train, es→quc only) |
| UD K'iche'-IU treebank (`ud_kiche_iu`) | https://github.com/UniversalDependencies/UD_Kiche-IU | F. Tyers, R. Henderson (Indiana U.) | CC BY-SA 4.0. README: sentences used with permission of the Academia de Lenguas Mayas de Guatemala and Telma Can Pixabaj | 1,435 sentences, 980 with `text[spa]` (657 ALMG vocabulary examples, 288 UT course, a few Bible/legal/COVID) | Everyday (dictionary examples); small legal, health, religious | ALMG with lax vowels marked (`ä`); folded by `normalize.py` | 2021 (UD v2.8) | train |
| COERLL "Chqeta'maj le qach'ab'al K'iche'!" (`coerll_kiche`) | https://tzij.coerll.utexas.edu/ | COERLL / LLILAS / AILLA, UT Austin | CC BY 4.0 (stated on the site). Lessons read via the public WordPress REST API | 46 lessons (Spanish edition); ~850 table rows (phrases + vocabulary) | Everyday / language learning | Near-ALMG, Nahualá variety | 2016–2026 | train |
| Universal Declaration of Human Rights (`udhr_ohchr`) | https://github.com/eric-muller/udhr (XML); https://www.ohchr.org/en/human-rights/universal-declaration/universal-declaration-human-rights/about-universal-declaration-human-rights-translation-project | OHCHR; XML by the UDHR in Unicode project | OHCHR translation project: translations may be reproduced citing OHCHR as the source | 30 articles + title → 51 aligned paragraphs | Legal | Modern with `'` glottal | 2006 (XML) | train |
| Mozilla Pontoon localizations (`pontoon_mozilla`) | https://huggingface.co/datasets/ayymen/Pontoon-Translations ; product labels from Pontoon's public K'iche' TMX https://pontoon.mozilla.org/translation-memory/quc.all-projects.tmx (no login) | Mozilla localization community; packaged by ayymen | MPL-2.0 (TMX: the same strings, used only to label each pair with its product for the niche) | 1,014 en→quc strings; joined with en→es-MX (fallback es-ES) on the English source → 783 pairs after dropping placeholders/markup | Software UI | Modern, `‘` as glottal | 2024 snapshot | train |
| New Testament, K'iche' of Totonicapán + Biblia Libre para el Mundo (`ebible_quctt`) | https://ebible.org/quctt/ ; corpus https://github.com/BibleNLP/ebible | Pioneer Bible Translators (quc); BLM (es) | quc: CC BY 4.0 (© 2022 Pioneer Bible Translators). es: public domain | 7,957 verses; capped to 30% of train sentences | **Religious** (never in test) | Modern ALMG with `ꞌ` saltillo | 2022 | train (capped) |
| GATITOS lexicon (`gatitos`) | https://huggingface.co/datasets/google/smol | Google Research (SMOL/GATITOS) | CC BY 4.0 | 3,992 en→quc and en→es entries; joined on the English entry → 3,982 es–quc | Dictionary (general vocabulary) | Modern, `'` glottal | 2025 | train (lexicon only) |
| PanLex (`panlex`) | https://panlex.org/ ; https://huggingface.co/datasets/cointegrated/panlex-meanings | PanLex / Long Now Foundation; packaged by cointegrated | CC0 1.0 | 4,141 quc expressions; 279 share a meaning with a Spanish (spa-000) expression | Dictionary | Mixed (some `ä`, `ʼ`) | 2025 packaging | train (lexicon only) |
| Wikcionario / Spanish Wiktionary (`wiktionary_es`) | https://es.wiktionary.org/ via https://kaikki.org/eswiktionary/ | Wiktionary contributors; kaikki.org (wiktextract) | CC BY-SA 4.0 | 45 K'iche' translations on Spanish entries (1.4 GB dump streamed and filtered) | Dictionary | Mixed | 2026 dump | train (lexicon only) |
| Unicode CLDR K'iche' emoji names (`cldr_quc`) | https://github.com/unicode-org/cldr (common/annotations/quc.xml, es.xml) | Unicode CLDR contributors (human vetters) | Unicode License V3 (repo LICENSE: "All other content in this repo is released under UNICODE LICENSE V3") | 1,228 quc names joined with Spanish on the code point; 1,164 kept after cleaning and dedupe | Everyday vocabulary (food, animals, objects, jobs, places) | Modern, `’` as glottal (normalized) | 2026 (main) | train (lexicon only: translation memory) |
| FLORES-Mayas K'iche' glossary (`floresmayas_quc`) | https://github.com/transducens/floresmayas (flores_plus_translation_task/data/quc/vocab.json, pinned commit `16bc3364ef`) | Transducens (Universitat d'Alacant) with PLFM translators | Apache-2.0 (root LICENSE) | 389 terms with a K'iche' definition; 428 pairs (alternatives split on `/`), 407 kept | News/encyclopedic terms | Modern | 2026-02-13 | train (lexicon only). Derived from FLORES Spanish: **never use it with a FLORES-based test**. Only vocab.json is read; config/state files hold personal data |

Notes on joins through English (Pontoon, GATITOS): both sides are independent *human*
translations of the same English original — no machine translation is involved — but a
sense can diverge ("spot" → "punto" / "k'olib'al" = place). GATITOS entries are therefore
`kind=lexicon` (retrieval context, not counted as translation examples).

Round-2 search (October 2): new candidates checked.
- **Needs permission:** the PLFM K'iche'–Spanish dictionary digitized by Transducens
  (`transducens/diccionarios_mayas`, 6,866 entries with example sentences; no license). Also the new
  ALMG PDFs (`Sinonimos-Kiche.pdf`, `Texto-Avanzado-Kiche.pdf`, `Antecedentes-Historicos-Kiche.pdf`,
  and `Vocabulario-Kiche.pdf` now at almg.org.gt/wp-content/uploads/2026/09/).
- **Rejected:**
  - StoryWeaver has 7 K'iche' books, but reading them requires a login.
  - MADLAD-400 `quc` has the FineWeb-2 problems plus wrong-language text (Kaqchikel, other Mayan
    Bibles).
  - DoenetML's quc strings are machine-generated (its own file header says so).
  - OPUS Mozilla-I10n duplicates Pontoon.
  - Glot500-c, CulturaX and HPLT: no usable quc.
  - Rosetta Swadesh (25 words, English) and Wikidata labels (names): negligible.
- **Checked:** Common Voice now has a quc locale, but it has 0 sentences.

Synthetic and back-translated training data are not sources: they are derived from the
sources above. Back-translation (`origin=back_translated_gemini`, Spanish side only) is described in
`pipeline/back_translate.py`; grounded synthetic pairs (`origin=synthetic`, dictionary-anchored
and UD slot filling, round-trip filtered) in `pipeline/synthetic.py`, with model, prompt, seed,
cost and rejection counts in `data/train/synthetic/meta.json`. Neither ever enters dev, test,
the niche slices or the retrieval index.

## Needs permission (14)

| Source | URL | Owner | License / terms | Size | Domain | Orthography | Date | Why not used yet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MayanV (quc subset) | https://github.com/transducens/mayanv | Transducens, U. d'Alacant (NAACL 2024) | CC0 for the *packaging*; README says they do not own the text. Text comes from the ALMG *Vocabulario K'iche'* | 2,632 pairs | Everyday (dictionary examples) | ALMG | 2024 | ALMG requires prior authorization; would more than double the everyday training data. 657 of these examples are already in via UD K'iche'-IU, which has ALMG's permission |
| Ministerio de Gobernación (MINGOB) news in K'iche' | https://mingob.gob.gt/ (found through FineWeb-2 `quc_Latn`) | Gobierno de Guatemala | No license on the site; news is not covered by Decreto 33-98's free publication of laws | ~3,800 pages, ~1M words of human-translated K'iche' — by far the largest K'iche' text online | Government news | Modern ALMG | 2015–2023 | **Biggest opportunity**: with written permission it would be the main back-translation source (×100 the current monolingual text) |
| ALMG *K'iche' Choltzij / Vocabulario K'iche'* | https://aprendeporti.com/wp-content/uploads/2023/11/vocabulario-kiche.pdf (mirror; ALMG original 404) | Academia de Lenguas Mayas de Guatemala | No explicit license; ALMG publications state reproduction needs prior authorization | 221 pp., es↔quc entries with example sentences | Everyday | ALMG | 2010 | Authorization from the Comunidad Lingüística K'iche' |
| ALMG *Kemtaqanik K'iche' Tzij, Gramática Normativa* | https://almg.org.gt/wp-content/uploads/2026/03/Gramatica-Normativa-Idioma-Kiche.pdf | ALMG | "La reproducción total o parcial puede realizarse previa autorización de la Comunidad Lingüística K'iche'" | 111 pp. | Grammar examples | ALMG (normative) | 2021 | Explicit prior authorization; used only as the orthography reference for `normalize.py` |
| ELAR — Can Pixabaj, formal and ceremonial discourse | https://www.elararchive.org/dk0187/ | Telma Can Pixabaj / ELAR | ELAR access terms (not CC); downloads need an account | ~20 h transcribed with Spanish, ~5,000-entry lexicon | Ceremonial / conversation | Modern | 2018 | Login + archive terms |
| Diccionario K'iche'–Español (Iglesia Católica) | https://www.iglesiacatolica.org.gt/bibliakiche/BKiche_DiccioKE.pdf | Conferencia Episcopal de Guatemala | No explicit license | ~1,780 entries | Religious / general | ALMG | 2012 | No license |
| SIL *Diccionario quiché-español* (Pontious et al.) | https://www.sil.org/resources/archives/26272 | SIL / ILV | Not stated on record (SIL archive items are often all-rights-reserved or NC-ND) | Full dictionary | General | Pre-1987 | 1980 | License unknown; old orthography |
| PLFM *Diccionario K'iche'* | https://plfm.org/publicaciones | Proyecto Lingüístico Francisco Marroquín | All rights reserved (print, sold) | 538 pp. | General | ALMG | 1996/2001 | Copyright; online copies are unauthorized |
| U. de Guadalajara *Diccionario Bilingüe Ilustrado Español–Kiche* | https://mayanlanguageimmigrationlawinfo.wordpress.com/wp-content/uploads/2015/01/diccionariobilingueilustradokiche.pdf | Universidad de Guadalajara | "D.R. © 2007" | 295 pp. | General | Modern | 2009 | Copyright; also contains copied Chuj boilerplate |
| Swarthmore K'iche' Talking Dictionary | https://talkingdictionary.swarthmore.edu/kiche/ | K'iche' community / Swarthmore | "All content copyright © K'iche' language community" | 299 entries with audio | Everyday | Modern | 2014 | Copyright |
| MSPAS K'iche' health materials | https://mspas.gob.gt/descargas-mspas/category/93-kiche | Ministerio de Salud Pública (Guatemala) | No license; site behind a bot challenge | Unknown | Health | Unknown | — | Couldn't verify content or terms |
| CNB Guatemala wiki, K'iche' | https://cnbguatemala.org/wiki/Idioma_K'iche' | MINEDUC / USAID | Reportedly CC BY-SA 4.0, not verifiable (bot-blocked) | 59 K'iche' / 44 Spanish readings (comparable, not parallel) | Education | ALMG | — | Terms unverified; not parallel |
| MINEDUC/DIGEBI *Kemon Ch'ab'äl* textbooks | https://digebi.mineduc.gob.gt/digebi/producto/kemon-chabal-2do-primaria-kiche/ | MINEDUC Guatemala | No license | Grades 1–6 | Education | ALMG | — | No license; K'iche' and Spanish editions are parallel series, not translations |
| Wuqu' Kawoq COVID-19 resources | https://wuqukawoq.org/programs/covid-19-response/covid-resources/ | Wuqu' Kawoq / Maya Health Alliance | No license | ~9 videos + audio | Health | — | 2020 | No license; audio would need transcription |

## Rejected (28)

| Source | URL | Owner | License / terms | Reason |
| --- | --- | --- | --- | --- |
| FineWeb-2 `quc_Latn` (HuggingFaceFW) | https://huggingface.co/datasets/HuggingFaceFW/fineweb-2 | Hugging Face (crawl compilation) | ODC-By for the compilation; each page keeps its own copyright | 4,772 pages: 80% MINGOB (no license), Bible sites, jw.org (terms forbid), a few Incubator/Space Scoop pages | Mixed | Mixed | 2026 | Used only to *discover* sources; the usable ones (Incubator, Space Scoop) are fetched from the original under their own licenses |
| GlotCC-V1 `quc-Latn` | https://huggingface.co/datasets/cis-lmu/GlotCC-V1 | CIS LMU | Compilation license; same crawl origins as FineWeb-2 | — | Mixed | Mixed | 2024 | Same pages as FineWeb-2 (government news without license, Bible, jw.org) |
| FLORES+ (`openlanguagedata/flores_plus`) | https://huggingface.co/datasets/openlanguagedata/flores_plus | Open Language Data Initiative | CC BY-SA 4.0, gated | No `quc` file in the current release | — | — | 2026 | No K'iche' yet (FLORES+ Mayas not released) |
| Mozilla Common Voice / Global Storybooks / StoryWeaver | — | — | — | No K'iche' locale or edition found | — | — | 2026 | Not available |
| OPUS bible-uedin es–quc / Christodouloupoulos Bible corpus | https://opus.nlpl.eu/bible-uedin ; https://github.com/christos-c/bible-corpus | C. Christodoulopoulos (markup CC0); texts from Bible.is / Bible Gateway | Markup CC0; the translations themselves are copyrighted by their publishers | Translation copyright not cleared; one of the two K'iche' NTs is in pre-ALMG spelling (`qui bi'`). Replaced by the CC BY Totonicapán NT |
| eBible `qucNNT` / `qucTNT` (K'iche' Cantel NT) | https://ebible.org/qucNNT/ | Wycliffe Bible Translators | CC BY-NC-ND 3.0 | No-derivatives: normalizing and training on it would be a derivative. Also redundant with the CC BY NT |
| bible-nlp/biblenlp-corpus, Taxi1500, other Bible repackagings | https://huggingface.co/datasets/bible-nlp/biblenlp-corpus | various | various | Same verses as eBible; religious data is already capped |
| Bloom books under CC BY-NC-SA / CC BY-NC-ND | https://bloomlibrary.org/language:quc | Bible for Children, others | NC / ND | Non-commercial / no-derivatives |
| Tatoeba (en–quc) | https://tatoeba.org / OPUS Tatoeba | Tatoeba contributors | CC BY 2.0 FR | 8 sentences, English only, no Spanish |
| ec5ug/chikhapo (eng–quc) | https://huggingface.co/datasets/ec5ug/chikhapo | ec5ug | MIT | Derived from GATITOS (same entries), English only |
| microsoft/ms_terms (Microsoft Terminology) | https://huggingface.co/datasets/microsoft/ms_terms | Microsoft | Microsoft terminology terms; loader needs a manual download | English–quc only; manual download from Microsoft |
| apertium-quc-spa bilingual dictionary | https://github.com/apertium/apertium-quc-spa | Apertium | GPL-3.0 | ~530 lexical pairs, mostly biblical proper nouns; copyleft would propagate to the index; covered by other dictionaries |
| apertium-quc corpora | https://github.com/apertium/apertium-quc/tree/master/corpora | Apertium (third-party text) | GPL-3.0 packaging; underlying text from ALMG, COERLL, others | Overlaps UD K'iche'-IU and COERLL; ALMG part needs permission |
| FLORES+ Mayas | https://github.com/transducens/floresmayas | U. d'Alacant + PLFM | Planned CC BY-SA 4.0 | Not released for quc yet (repo has encrypted sources). **Revisit**: would be an excellent test set |
| Ley de Acceso a la Información Pública, Español/K'iche' | https://mcd.gob.gt/wp-content/uploads/2013/07/Ley-de-acceso-a-la-informaci%C3%B3n-p%C3%BAblica-en-idioma-kiche.pdf | COPRET / Gobierno de Guatemala | Decreto 33-98: laws and their official translations may be published freely | Two-column PDF with loose, non-sentence alignment; not worth the extraction cost in Phase 1. Legally usable — revisit |
| UNM K'iche' Maya Oral History Project | https://digitalrepository.unm.edu/laii_kichemaya/ | UNM LAII | CC BY-NC-ND 4.0 | No derivatives; scanned 1968–73 typescripts in pre-ALMG spelling |
| English Wiktionary K'iche' entries | https://kaikki.org/dictionary/K'iche'/ | Wiktionary | CC BY-SA 4.0 | 372 entries with English glosses only |
| Wikimedia Incubator Wp/quc | https://incubator.wikimedia.org/wiki/Wp/quc | Wikimedia | CC BY-SA 4.0 | Monolingual (112 pages) |
| Glot500, GlotCC, FineWeb-2, FinePDFs, DCAD-2000, MADLAD-style web crawls | https://huggingface.co/datasets/cis-lmu/Glot500 etc. | various | various | Monolingual K'iche' web text; no Spanish alignment |
| HuggingFaceFW/finetranslations | https://huggingface.co/datasets/HuggingFaceFW/finetranslations | Hugging Face | ODC-By | Machine translations: synthetic data is not allowed |
| sil-ai/bloom-lm, bloom-captioning, bloom-vist, bloom-speech | https://huggingface.co/datasets/sil-ai/bloom-lm | SIL | per-book CC | Monolingual repackaging of Bloom; we read Bloom directly for aligned text |
| Popol Wuj (Sam Colop editions) | https://popol-mayab.org/popol-wuj-kiche/ | Cholsamaj / heirs | All rights reserved | Copyright; poetic text not sentence-aligned |
| Colonial dictionaries (Basseta 1698, Berlin dictionary) | — | various | Public domain / unclear | Colonial orthography, not usable for modern MT |
| Christenson K'iche'–English dictionary (FAMSI) | https://www.famsi.org/mayawriting/dictionary/christenson/quidic_complete.pdf | Allen Christenson / FAMSI | No explicit license | English glosses only |
| Kaufman & Justeson, Preliminary Mayan Etymological Dictionary | https://www.famsi.org/reports/01051/pmed.pdf | FAMSI | No explicit license | English glosses; reconstruction-oriented |
| Glosbe quc↔es | https://es.glosbe.com/quc/es | Glosbe | Proprietary terms | Aggregator without an open license; scraping not permitted |
| JW300 / jw.org | https://www.jw.org | Watch Tower | Terms forbid reuse | Terms of use; removed from OPUS for that reason |
| Apps and phrasebooks (idiomasmayas.com, MINEDUC *Qatzij*, buildOn phrasebook) | — | various | Copyright / no license | No license; phrasebook is English-oriented |

## Checked and not found

- **AmericasNLP shared tasks 2021–2025**: no K'iche' track.
- **FLORES-200 / FLORES+**: no `quc` in the released splits (see FLORES+ Mayas above).
- **Google Translate** (June 2024 expansion) lists Mam, Q'eqchi' and Yucatec, not K'iche'.
- **Constitución Política / Ley de Idiomas Nacionales / Acuerdos de Paz in K'iche'**,
  **UNICEF–ALMG**, **CONRED**: catalog records or press releases only, no downloadable text.
- **StoryWeaver, Global Voices, Mozilla Common Voice**: no K'iche'.
