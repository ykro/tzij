# Model card — Tzij "David" (Spanish ↔ K'iche')

## What it is

David is a small Gemma model that translates between Spanish and K'iche' (`quc`), helped by a
retrieval index built from licensed K'iche' data. It is served from its own GPU on Cloud Run.
In the demo it translates side by side with Goliath, a frontier model (Gemini) used as anyone would
use it, on one public page.

| | David | Goliath |
| --- | --- | --- |
| Model | `LOCAL_MODEL_TAG` (now `tzij-2026-10-mix-s7`, a LoRA on Gemma 4 E4B) served by Ollama | `GEMINI_MODEL` (now `gemini-3.8-flash`) on Vertex AI |
| Extra knowledge | Hybrid retrieval index: 8,453 dictionary entries and example pairs per direction (BM25 over SQLite FTS5 + EmbeddingGemma in sqlite-vec, fused with RRF; exact and fuzzy glossary) | None |
| Decoding | MBR: 4 samples at temperature 0.7, keep the one with the highest mean chrF++ against the others (`DAVID_MBR=1`) | One answer, temperature 0.2 |
| Runs on | Cloud Run `tzij-david` (`europe-west4`): 1× NVIDIA L4, Ollama, private, scales to zero | Vertex AI (`global`) |
| Cost per translation | $0.00027 with one person using it (0.9 s × $0.0002907/s: L4 + 4 vCPU + 16 GiB while the instance is up); $0.000189 at full load (about 5,500 per hour) | $0.00012 (107 tokens × the 2026 list price); $0.00024 from January 1, 2027 |
| Time per translation (26 examples × 3) | Median 0.81 s, p95 1.43 s | Median 1.47 s, p95 3.09 s |

**In the demo now:** `tzij-2026-10-mix-s7` + hybrid retrieval + MBR (4 samples), the best David
variant in `evals/report.md`. It never saw Firefox Focus, so
it can be measured on the specialty test, and the demo's example sentences come from there.

Run `final-20261002`, dataset `20261002-173447` (its test split is identical to that of
`20261002-022500`, where the rows before `mix-s7` were run), 600 held-out sentences (Bloom +
BOUQuET, references `auto_validated`). Retrieval tuned on dev only; test used once. Gemma variants
were measured on a laptop (Apple Silicon, Ollama) before David moved to the cloud; latencies are
from that machine. On the Cloud Run L4, the page gets David's MBR-4 translation in a median 0.9 s.

| Variant | es→quc | quc→es | both | p50 | p95 | cost / 1,000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 E4B, base | 7.5 | 16.7 | 11.7 | 1.3 s | 3.6 s | $0 |
| Gemma 4 E4B + vector retrieval | 18.2 | 18.8 | 18.5 | 1.8 s | 4.8 s | $0 |
| Gemma 4 E4B + hybrid retrieval | 19.0 | 19.8 | 19.4 | 1.8 s | 4.7 s | $0 |
| Gemma 4 E4B + hybrid + MBR4 | 20.4 | 20.9 | 20.7 | 4.6 s | 16.3 s | $0 |
| `tzij-2026-10-raft-bt-s3` + hybrid | 18.4 | 18.3 | 18.3 | 1.7 s | 4.7 s | $0 |
| `tzij-2026-10-raft-bt-s3` + hybrid + MBR4 (previous David) | 21.9 | 21.2 | 21.5 | 4.0 s | 14.2 s | $0 |
| `tzij-2026-10-mix-s7` + hybrid | 26.9 | 23.2 | 25.1 | 1.6 s | 4.3 s | $0 |
| `tzij-2026-10-mix-s7` + hybrid + MBR4 (**the demo's David**) | 27.0 | 24.3 | **25.7** | 4.1 s | 13.4 s | $0 |
| Gemini 3.8 Flash (**Goliath**) | 33.4 | 40.7 | **36.9** | 1.7 s | 4.7 s | $0.29 |
| Gemini 3.8 Flash + same retrieval (vector) | 34.6 | 40.1 | 37.2 | 2.1 s | 6.5 s | $0.95 |

Ablation (both directions): base + vector retrieval 18.5 → + hybrid retrieval 19.4 (+0.9) →
+ RAFT fine-tune with Gemini back-translation 18.3 (−1.1) → + MBR 21.5 (+3.2) → + data without
Focus, 2 epochs, Bloom back-translation and distillation 25.7 (+4.1).

What the numbers say, for the talk:

- **Where David holds a translation memory Goliath lacks, he wins.** In the pre-registered niche
  (`evals/niche.md`): Firefox Focus, 144 es→quc pairs David never saw, with Mozilla's other
  products and two terminology lists in his index. The demo's David scores 37.4 vs 28.9 chrF++,
  +8.5 [+4.7, +12.7]. On terminology they tie (61% vs 46%, +15 [−2, +32]); the base model with the
  same index uses the right term 78% of the time but ties on chrF++ (30.2). Results:
  `evals/niche_results.md`.
  Re-run on October 7 with David on the cloud L4: 35.3 vs 28.9 (+6.4 [+2.5, +10.5]; MBR sampling
  moves a run by about 2 points), and 36.5 vs 30.4 (+6.1 [+3.0, +9.2]) on 105 newer Firefox Focus
  strings that are in no split (`evals/tm_new_results.md`). On Mozilla Monitor's newer strings, a
  marketing website, Goliath wins (32.6 vs 22.0).
- **In general, Goliath is better at translating.** David trails by 11.2 chrF++ points (15.4 with
  the previous David) and in every slice (length, direction, source, domain): the gap is general
  K'iche' competence. It beats Goliath on 130 of 599 sentences (22%) and is within 5 points on
  34%. Gemini 3.1 Pro ties Gemini 3.8 Flash in K'iche', so model size is not Goliath's edge.
- **Data is what moves David.** Retrieval from ~7,000 licensed dictionary entries and example
  pairs takes base E4B from 11.7 to 18.5; most of the gain is Spanish → K'iche' (7.5 → 18.2),
  the direction a model can't fake. Hybrid search adds +0.9.
- **MBR was the biggest single gain for the previous David (+3.2), paid in latency:** p50 1.7 →
  4.0 s, p95 14 s. For the current David it adds +0.6 on test and +1.5 on the niche.
- **The first fine-tune didn't help with retrieval (−1.1); with MBR it added +0.8** over the
  base model with MBR (21.5 vs 20.7). At an equal 1/4-epoch budget, adding back-translated pairs
  was worth +1.1 (15.7 vs 14.6).
- **The fine-tune pays off when its data looks like the test's domain:** `tzij-2026-10-mix-s7`
  beats the base model with the same retrieval by +5.7 (25.1 vs 19.4) and the previous David by
  +4.1 [+3.6, +4.7].
- **Goliath teaches once; afterwards David translates without it.** One-time costs: first
  back-translation $0.12 and fine-tune $3.09 (5 L4 Cloud Run jobs); the data round behind the
  current David about $24.3 (L4 $8.52; Gemini back-translation, distillation and a Gemini Pro
  measurement; `docs/BITACORA.md`, sections 10–11).
- **Served in the cloud, David is faster for one person and cheaper only with heavy use.** He
  answers first in 74 of 78 translations. The GPU bills $1.05 per hour while it's up, so with
  little use Gemini is cheaper; at Gemini's 2027 price David is cheaper above about 4,300
  translations per hour (README, Proyecciones).

Variants compared in `make eval` (results in `evals/report.md`): each Gemma in
`BASE_MODEL_TAGS` and each fine-tuned tag in `FINETUNED_MODEL_TAGS`, plain, with vector
retrieval, with hybrid retrieval and with hybrid retrieval + MBR; Gemini alone and Gemini with
the same retrieval. The David in the demo is the best David variant.

## Data

Everything comes from licensed web sources listed in `data/SOURCES.md`; counts, splits and
drop reasons are in `data/DATASHEET.md` (generated). Dataset `20261002-173447`, the demo's, derived
from `20261002-022500` by holding out the Pontoon product Firefox Focus as `test_niche.jsonl`
(144 es→quc pairs, `pipeline/niche.py`):

- **Train / retrieval:** 8,453 pairs per direction (2,541 sentence pairs, the rest dictionary and
  glossary entries) from UD K'iche'-IU (ALMG dictionary examples and 104 bilingual stories, used
  with ALMG's permission), the UT Austin COERLL course, the UDHR, Mozilla Pontoon (without
  Firefox Focus), the Totonicapán New Testament (capped at 30% of training sentences), and the
  GATITOS, PanLex and Wiktionary dictionaries. 115 dev pairs for tuning.
- **Translation memory added for the niche** (lexicon rows, retrieval only, never trained): Unicode
  CLDR K'iche' emoji names (Unicode License V3, 1,164 pairs) and the FLORES-Mayas glossary
  (Apache-2.0, 407 pairs; never used with a FLORES-based test). Both are counted in the 8,453.
- **Held-out test:** 1,654 pairs per direction from MINEDUC children's books on Bloom
  Library and Meta's BOUQuET benchmark (evaluation only, per its terms). No test source is
  ever used for training or retrieval; train pairs repeating a test sentence are removed.
- **Gemini's K'iche' only in training, filtered.** Every K'iche' record in the dataset, the
  retrieval index, dev and test is `origin=web`, with a URL and a license. Gemini contributes
  training-only data in two controlled ways:
  - **back-translation:** licensed monolingual K'iche' (K'iche' Wikipedia on Wikimedia Incubator,
    CC BY-SA 4.0; Space Scoop, CC BY 4.0; K'iche'-only Bloom books, CC BY 4.0) translated into
    Spanish: 2,397 pairs tagged `origin=back_translated_gemini` (model, prompt, seed and cost in
    `data/train/back_translated_gemini.meta.json`). The K'iche' side is human-written; since
    2026-10-04 the pairs train both directions;
  - **distillation** (`origin=distilled_gemini`, `pipeline/distill.py`): everyday Spanish written
    by Gemini in BOUQuET's domains, translated into K'iche' with David's retrieved context and
    kept only if it passes the ALMG alphabet, length and round-trip filters (2,409 pairs in
    training). A second batch of 1,877 pairs ($6.98, included in the ~$14 of Gemini and the
    ~$24.3 of the data round) was generated but not used in `tzij-2026-10-mix-s7`.
- **Orthography.** Glottal stops unified to `'` and lax vowels folded (`data/normalize.py`);
  the screen shows the modifier letter apostrophe `ʼ`.
- **Fine-tuning threshold** (2,000 clean sentence pairs outside test): met with 2,656, of
  which 1,894 are non-religious (2,849 and 2,029 before Firefox Focus was held out).
- **Training recipe of the previous David, `tzij-2026-10-raft-bt-s3`.** LoRA (r=16, alpha=32, lr 2e-4) on Gemma 4
  E4B, 1 epoch over 5,579 examples: the train split in both directions plus the back-translated
  pairs, religious ≤30%. Every prompt carries the same hybrid retrieval context David sees when
  translating, with the pair itself excluded from its own context (RAFT, 0 answer leaks). Batch 2 ×
  grad-accum 8, max 1,024 tokens, in 4 chunks of 1/4 epoch (`-s0` … `-s3`, each continuing the
  previous adapter) as Cloud Run Jobs on one L4 in europe-west4, to stay under the 1 h GPU task
  limit. Merge and GGUF (Q4_K_M) ran outside the job because the 16 GB merged checkpoint
  doesn't fit its 32 GiB (today: a Cloud Batch VM with 64 GB, `make train-finish`). Runs in `train/runs/`.
- **Training recipe of `tzij-2026-10-mix-s7` (the demo's David).** The same RAFT recipe for 2 epochs on
  data without Firefox Focus (`tzij-2026-10-tm-a-e2-s4`), continued in 8 chunks (`-s0` … `-s7`)
  with the Bloom back-translation in both directions, the distilled pairs and 30% of the web
  pairs as replay: 10,692 examples. Decisions were made on the `dev_domain` split
  (`evals/dev_domain_report.md`), never on test.

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

A live demonstration that a small model with the right data can beat a
frontier model where it holds data the big model lacks (a translation memory), on a language the
big models barely know. Also teaching material: the code
shows how the data was gathered, licensed, split and evaluated.

## Not intended for

Legal, medical or official translation; any decision about a person; replacing
professional K'iche' translators or interpreters. Outputs are unverified machine
translations and can be wrong in ways a non-speaker cannot detect.

## Known limitations

- Small data: about 1,900 non-religious sentence pairs. Religious and software
  (Firefox) registers are over-represented compared with everyday speech.
- K'iche' varies by region (Nahualá, Totonicapán, Santa Cruz del Quiché, Cantel); the data
  mixes varieties and the model does not choose one on purpose.
- chrF++ rewards character overlap with one reference; a correct paraphrase can score low.
  A native speaker can rate translations blind with `make human-eval-sheet` (`evals/human_eval.md`).
- Some test pairs (children's books) are page-aligned and paraphrased; the automatic
  length-ratio filter (0.5–2.0) drops the worst ones, and chrF++ on the rest is noisier.

## Ethics and community

K'iche' data belongs to its speakers and institutions. Sources that require authorization
(ALMG publications beyond the permitted examples, PLFM, SIL dictionaries) are listed as
"needs permission" and are not used. A native speaker, not a metric, can rate translations blind
with `make human-eval-sheet` (`evals/human_eval.md`); the demo never depends on it.
