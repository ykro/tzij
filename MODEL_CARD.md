# Model card — Tzij "David" (Spanish ↔ K'iche')

## What it is

David is a small Gemma model that translates between Spanish and K'iche' (`quc`) on a
laptop, with no internet, helped by a retrieval index built from licensed K'iche' data.
On stage it competes against Goliath, a frontier model (Gemini) used as anyone would use it.

| | David | Goliath |
| --- | --- | --- |
| Model | `LOCAL_MODEL_TAG` (now `gemma4:e4b`) served by Ollama | `GEMINI_MODEL` (now `gemini-3.8-flash`) on Vertex AI |
| Extra knowledge | Retrieval index: ~7,000 dictionary entries and example pairs per direction (EmbeddingGemma + sqlite-vec) | None |
| Runs on | The presenter's laptop, offline | Google Cloud, needs internet |
| Cost per translation | $0 (hardware already paid for) | Tokens × list price (shown live) |

**On stage now:** `gemma4:e4b` + retrieval, the best local variant in `evals/report.md`.

| Variant (600 held-out sentences, Bloom + BOUQuET) | es→quc | quc→es | both | p50 | cost / 1,000 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 E4B, base | 7.4 | 16.3 | 11.5 | 1.2 s | $0 |
| Gemma 4 E4B + retrieval (**David on stage**) | 18.0 | 18.9 | **18.4** | 1.7 s | $0 |
| `tzij-2026-09` (LoRA on E4B, 1 epoch) | 13.8 | 16.8 | 15.2 | 1.1 s | $0 |
| `tzij-2026-09` + retrieval | 17.5 | 17.8 | 17.6 | 1.8 s | $0 |
| Gemini 3.8 Flash (**Goliath**) | 32.8 | 40.4 | **36.4** | 1.8 s | $0.26 |
| Gemini 3.8 Flash + same retrieval | 34.3 | 40.4 | 37.2 | 2.3 s | $1.00 |

The true picture, for the talk:

- **Goliath is better at translating.** David trails by 18 chrF++ points overall and in every
  slice (length, direction, domain); it beats Goliath on 45 of 598 sentences (8%) and is within
  5 points on 18%.
- **Data is what moves David.** Retrieval from ~7,000 licensed dictionary entries and example
  pairs takes base E4B from 11.5 to 18.4 (+60%); most of the gain is Spanish → K'iche'
  (7.4 → 18.0), the direction a model can't fake.
- **Fine-tuning helped, but less than retrieval.** One LoRA epoch on 2,590 sentence pairs lifts
  E4B alone from 11.5 to 15.2, but with retrieval it is 0.8 points *below* base + retrieval
  overall (it does better on short phrases, 13.9 vs 11.2, and worse on long sentences). With
  under 2,000 non-religious pairs, retrieval is the better investment; the fine-tune stays in
  the report, not on stage.
- **Where David wins outright:** cost ($0 vs $0.26 per 1,000 translations, and the cloud price
  doubles in 2027) and availability. With no internet Goliath produces nothing, and David's
  scores are unchanged: model, index and embeddings all live on the laptop.

Variants compared in `make eval` (results in `evals/report.md`): each Gemma in
`BASE_MODEL_TAGS` with and without retrieval, fine-tuned tags in `FINETUNED_MODEL_TAGS`
with and without retrieval, Gemini alone, and Gemini with the same retrieval. The David
that goes on stage is the best local variant in that report.

## Data

Everything comes from licensed web sources listed in `data/SOURCES.md`; counts, splits and
drop reasons are in `data/DATASHEET.md` (generated). Dataset `20260930-220035`:

- **Train / retrieval:** 7,025 pairs per direction from UD K'iche'-IU (ALMG dictionary
  examples, used with ALMG's permission), the UT Austin COERLL course, the UDHR, Mozilla
  Pontoon, the Totonicapán New Testament (capped at 30% of training sentences), and the
  GATITOS, PanLex and Wiktionary dictionaries.
- **Held-out test:** 1,654 pairs per direction from MINEDUC children's books on Bloom
  Library and Meta's BOUQuET benchmark (evaluation only, per its terms). No test source is
  ever used for training or retrieval; train pairs repeating a test sentence are removed.
- **No synthetic K'iche'.** Gemini is never used to generate K'iche' data: it would teach
  David its own mistakes. Every record has `origin=web`, a URL and a license.
- **Orthography.** Glottal stops unified to `'` and lax vowels folded (`data/normalize.py`);
  the screen shows the modifier letter apostrophe `ʼ`.
- **Fine-tuning threshold** (2,000 clean sentence pairs outside test): met with 2,701, of
  which 1,924 are non-religious. `tzij-2026-09` is a LoRA (r=16) on Gemma 4 E4B, 1 epoch over
  the train split (5,180 examples, both directions, religious ≤30%), trained as a Cloud Run Job
  on one L4 in europe-west4 (22 min of training; merge and GGUF finished on the laptop because
  the 16 GB checkpoint doesn't fit the job's 32 GiB). Runs in `train/runs/`.

## Evaluation

- chrF++ (corpus level, normalized text) per direction and per test source, latency p50/p95
  and cost per 1,000 translations: `evals/report.md`.
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

- Small data: fewer than 2,000 non-religious sentence pairs. Religious and software
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
