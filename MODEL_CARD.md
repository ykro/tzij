# Model card — Tzij "David" (Spanish ↔ K'iche')

## What it is

David is a small Gemma model that translates between Spanish and K'iche' (`quc`) on a
laptop, with no internet, helped by a retrieval index built from licensed K'iche' data.
On stage it competes against Goliath, a frontier model (Gemini) used as anyone would use it.

| | David | Goliath |
| --- | --- | --- |
| Model | `LOCAL_MODEL_TAG` (Gemma 4, base or LoRA fine-tuned) served by Ollama | `GEMINI_MODEL` on Vertex AI |
| Extra knowledge | Retrieval index: ~7,000 dictionary entries and example pairs per direction (EmbeddingGemma + sqlite-vec) | None |
| Runs on | The presenter's laptop, offline | Google Cloud, needs internet |
| Cost per translation | $0 (hardware already paid for) | Tokens × list price (shown live) |

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
  which 1,924 are non-religious. The LoRA (`make train`) trains on the train split only.

## Evaluation

- chrF++ (corpus level, normalized text) per direction and per test source, latency p50/p95
  and cost per 1,000 translations: `evals/report.md`.
- Token fertility: K'iche' costs 2.68 Gemma tokens per word vs 1.45 for Spanish
  (`evals/fertility.md`).
- Test references are `pending_native_review` until a native speaker validates them
  (`make review-test`, `make apply-review`); report scores are provisional until then.
- Blind human rating template (adequacy and fluency, 50 items per model): `evals/human_eval.md`.

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
"needs permission" and are not used. The validator view puts a native speaker, not a
metric, in charge of live verdicts.
