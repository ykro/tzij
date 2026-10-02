# Model card — Tzij "David" (Spanish ↔ K'iche')

## What it is

David is a small Gemma model that translates between Spanish and K'iche' (`quc`) on a
laptop, with no internet, helped by a retrieval index built from licensed K'iche' data.
On stage it competes against Goliath, a frontier model (Gemini) used as anyone would use it.

| | David | Goliath |
| --- | --- | --- |
| Model | `LOCAL_MODEL_TAG` (now `tzij-2026-10-raft-bt-s3`, a LoRA on Gemma 4 E4B) served by Ollama | `GEMINI_MODEL` (now `gemini-3.8-flash`) on Vertex AI |
| Extra knowledge | Hybrid retrieval index: ~7,000 dictionary entries and example pairs per direction (BM25 over SQLite FTS5 + EmbeddingGemma in sqlite-vec, fused with RRF; exact and fuzzy glossary) | None |
| Decoding | MBR: 4 samples at temperature 0.7, keep the one with the highest mean chrF++ against the others (`MBR_ON_STAGE=1`) | One answer, temperature 0.2 |
| Runs on | The presenter's laptop, offline | Google Cloud, needs internet |
| Cost per translation | $0 (hardware already paid for) | Tokens × list price (shown live) |

**On stage now:** `tzij-2026-10-raft-bt-s3` + hybrid retrieval + MBR (4 samples), the best local
variant in `evals/report.md` with p50 under the 5 s stage budget.

Run `final-20261002`, dataset `20261002-022500`, 600 held-out sentences (Bloom + BOUQuET,
references `auto_validated`). Retrieval tuned on dev only; test used once.

| Variant | es→quc | quc→es | both | p50 | p95 | cost / 1,000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 E4B, base | 7.5 | 16.7 | 11.7 | 1.3 s | 3.6 s | $0 |
| Gemma 4 E4B + vector retrieval | 18.2 | 18.8 | 18.5 | 1.8 s | 4.8 s | $0 |
| Gemma 4 E4B + hybrid retrieval | 19.0 | 19.8 | 19.4 | 1.8 s | 4.7 s | $0 |
| Gemma 4 E4B + hybrid + MBR4 | 20.4 | 20.9 | 20.7 | 4.6 s | 16.3 s | $0 |
| `tzij-2026-10-raft-bt-s3` + hybrid | 18.4 | 18.3 | 18.3 | 1.7 s | 4.7 s | $0 |
| `tzij-2026-10-raft-bt-s3` + hybrid + MBR4 (**David on stage**) | 21.9 | 21.2 | **21.5** | 4.0 s | 14.2 s | $0 |
| Gemini 3.8 Flash (**Goliath**) | 33.4 | 40.7 | **36.9** | 1.7 s | 4.7 s | $0.29 |
| Gemini 3.8 Flash + same retrieval (vector) | 34.6 | 40.1 | 37.2 | 2.1 s | 6.5 s | $0.95 |

Ablation (both directions): base + vector retrieval 18.5 → + hybrid retrieval 19.4 (+0.9) →
+ RAFT fine-tune with Gemini back-translation 18.3 (−1.1) → + MBR 21.5 (+3.2).

The true picture, for the talk:

- **Goliath is better at translating.** David trails by 15.4 chrF++ points overall and in every
  slice (length, direction, source, domain); it beats Goliath on 74 of 599 sentences (12%) and
  is within 5 points on 23%.
- **Except where David holds a translation memory Goliath lacks.** In the pre-registered niche
  (`evals/niche.md`): Firefox Focus, 144 es→quc pairs David never saw, with Mozilla's other
  products and two terminology lists in his index. There they tie on chrF++ (30.2 vs 28.9, +1.3
  [−2.3, +5.3]), and David uses the right term far more often (78% vs 46%, +32 [+13, +51]).
  Results: `evals/niche_results.md`.
- **Data is what moves David.** Retrieval from ~7,000 licensed dictionary entries and example
  pairs takes base E4B from 11.7 to 18.5; most of the gain is Spanish → K'iche' (7.5 → 18.2),
  the direction a model can't fake. Hybrid search adds +0.9.
- **MBR is the biggest single gain (+3.2), paid in latency:** p50 1.7 → 4.0 s, p95 14 s.
- **The fine-tune alone didn't help with retrieval (−1.1); with MBR it adds +0.8** over the
  base model with MBR (21.5 vs 20.7). It is worse than base on short phrases (13.7 vs 16.4).
  At an equal 1/4-epoch budget, adding back-translated pairs is worth +1.1 (15.7 vs 14.6).
- **Goliath teaches once in the cloud, David serves forever offline.** One-time costs: Gemini
  back-translation $0.12, fine-tuning $3.09 (5 L4 Cloud Run jobs).
- **Where David wins outright:** cost ($0 vs $0.29 per 1,000 translations, and the cloud price
  doubles in 2027) and availability. With no internet Goliath produces nothing, and David's
  scores are unchanged: model, index and embeddings all live on the laptop.

Variants compared in `make eval` (results in `evals/report.md`): each Gemma in
`BASE_MODEL_TAGS` and each fine-tuned tag in `FINETUNED_MODEL_TAGS`, plain, with vector
retrieval, with hybrid retrieval and with hybrid retrieval + MBR; Gemini alone and Gemini with
the same retrieval. The David that goes on stage is the best local variant with p50 ≤ 5 s.

## Data

Everything comes from licensed web sources listed in `data/SOURCES.md`; counts, splits and
drop reasons are in `data/DATASHEET.md` (generated). Dataset `20261002-022500`:

- **Train / retrieval:** 7,169 pairs per direction from UD K'iche'-IU (ALMG dictionary
  examples and 104 bilingual stories, used with ALMG's permission), the UT Austin COERLL
  course, the UDHR, Mozilla Pontoon, the Totonicapán New Testament (capped at 30% of training
  sentences), and the GATITOS, PanLex and Wiktionary dictionaries. 115 dev pairs for tuning.
- **Translation memory added for the niche** (lexicon rows, retrieval only, never trained): Unicode
  CLDR K'iche' emoji names (Unicode License V3, 1,164 pairs) and the FLORES-Mayas glossary
  (Apache-2.0, 407 pairs; never used with a FLORES-based test). Dataset `20261002-173447` holds
  out the Pontoon product Firefox Focus as `test_niche.jsonl`.
- **Held-out test:** 1,654 pairs per direction from MINEDUC children's books on Bloom
  Library and Meta's BOUQuET benchmark (evaluation only, per its terms). No test source is
  ever used for training or retrieval; train pairs repeating a test sentence are removed.
- **No synthetic K'iche'.** Gemini never writes K'iche': it would teach David its own
  mistakes. Every K'iche' record is `origin=web`, with a URL and a license. The one controlled
  use of Gemini in the data is **back-translation**: 405 licensed monolingual K'iche' sentences
  (K'iche' Wikipedia on Wikimedia Incubator, CC BY-SA 4.0; Space Scoop, CC BY 4.0) translated
  into Spanish → 399 pairs tagged `origin=back_translated_gemini` (model, prompt, seed 2027 and
  $0.12 cost in `data/train/back_translated_gemini.meta.json`). They train Spanish → K'iche'
  only, and never enter test or the retrieval index.
- **Orthography.** Glottal stops unified to `'` and lax vowels folded (`data/normalize.py`);
  the screen shows the modifier letter apostrophe `ʼ`.
- **Fine-tuning threshold** (2,000 clean sentence pairs outside test): met with 2,849, of
  which 2,029 are non-religious.
- **Training recipe of `tzij-2026-10-raft-bt-s3`.** LoRA (r=16, alpha=32, lr 2e-4) on Gemma 4
  E4B, 1 epoch over 5,579 examples: the train split in both directions plus the back-translated
  pairs, religious ≤30%. Every prompt carries the same hybrid retrieval context David sees on
  stage, with the pair itself excluded from its own context (RAFT, 0 answer leaks). Batch 2 ×
  grad-accum 8, max 1,024 tokens, in 4 chunks of 1/4 epoch (`-s0` … `-s3`, each continuing the
  previous adapter) as Cloud Run Jobs on one L4 in europe-west4, to stay under the 1 h GPU task
  limit. Merge and GGUF (Q4_K_M) finished on the laptop because the 16 GB merged checkpoint
  doesn't fit the job's 32 GiB. Runs in `train/runs/`.

## Evaluation

- chrF++ (corpus level, normalized text) per direction and per test source, latency p50/p95,
  cost per 1,000 translations and the ablation: `evals/report.md`. Retrieval tuning on dev:
  `evals/tuning.md`.
- Token fertility: K'iche' costs 2.64 Gemma 4 E4B tokens per word vs 1.41 for Spanish
  (`evals/fertility.md`).
- Test references are validated automatically (`pipeline/validate_test.py`: source-level split,
  cleaning, 0.5–2.0 length ratio, Spanish side looks Spanish, no overlap with train) and marked
  `auto_validated`; no human step is required. A native-speaker review (`make review-test`,
  `make apply-review`) is optional and upgrades pairs to `validated`.
- Optional blind human rating template (adequacy and fluency, 50 items per model): `evals/human_eval.md`.

## Intended use

A live demonstration that a small, offline model with the right data can compete with a
frontier model on a language the big models barely know. Also teaching material: the code
shows how the data was gathered, licensed, split and evaluated.

## Not intended for

Legal, medical or official translation; any decision about a person; replacing
professional K'iche' translators or interpreters. Outputs are unverified machine
translations and can be wrong in ways a non-speaker cannot detect.

## Known limitations

- Small data: about 2,000 non-religious sentence pairs. Religious and software
  (Firefox) registers are over-represented compared with everyday speech.
- K'iche' varies by region (Nahualá, Totonicapán, Santa Cruz del Quiché, Cantel); the data
  mixes varieties and the model does not choose one on purpose.
- chrF++ rewards character overlap with one reference; a correct paraphrase can score low.
  Live rounds are judged by a native speaker for that reason.
- Some test pairs (children's books) are page-aligned and paraphrased; the native review is
  the final filter.

## Ethics and community

K'iche' data belongs to its speakers and institutions. Sources that require authorization
(ALMG publications beyond the permitted examples, PLFM, SIL dictionaries) are listed as
"needs permission" and are not used. The optional validator view lets a native speaker, not a
metric, judge live rounds when one is present; the demo never depends on it.
