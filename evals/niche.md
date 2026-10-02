# Pre-registered niche: vocabulary from our dictionaries

This file was written and committed **before** any per-sentence test result was looked at
for this slice. The thresholds were chosen on the dev split, without using any model output.
Results go to `evals/niche_results.md`. This file doesn't change after registration: if the
niche turns out badly for David, the report says so.

What was already known when this was written: the aggregate test slices in
`evals/report.md` (by direction, length, source and domain) and the overall count "David beats
Goliath on 74 of 599 sentences". The niche slice itself had not been computed.

## Hypothesis

David's advantage is the licensed data on the laptop. Where a sentence uses words that our
dictionaries know and that barely exist in web K'iche' (what a frontier model was trained on),
David should do relatively better than Goliath, and may beat him.

## Definition (code: `pipeline/niche.py`)

- **Content word:** a token of the source sentence, normalized with `data/normalize.py` and
  `match_key`, that is not one of the 150 most frequent word types of the reference corpus of
  its language.
- **In our dictionaries:** a single-word entry of the training lexicon (`kind=lexicon` in the
  train split of dataset `20261002-022500`: GATITOS, COERLL vocabulary, PanLex, Pontoon terms,
  Wiktionary) has exactly that normalized key on the same-language side.
- **Rare in web K'iche':** the K'iche' side occurs at most `F_MAX` times in the web K'iche'
  reference corpus. For a K'iche' word (quc→es) that's the word itself. For a Spanish word
  (es→quc) it's every K'iche' rendering in the dictionary, and the most frequent rendering
  decides, so a word with one common rendering doesn't count as rare.
- **Niche sentence:** at least `N_MIN` distinct content words that are in our dictionaries
  and rare in web K'iche'.

**Web K'iche' reference corpus** (frozen, sha256 prefix `6f4c85ccce3437eb`): 9,101
K'iche' lines, 211,516 tokens. It holds the whole Totonicapán New Testament (the most widely
published K'iche' text on the web), the monolingual web K'iche' in `data/monolingual/quc.jsonl`
(Wikipedia on Incubator, Space Scoop) and the K'iche' side of the Pontoon and UDHR pairs. The
Spanish function-word list comes from the Spanish Bible (BLM) and the Spanish side of Pontoon
and UDHR. Dictionaries, courses and the test sources are left out on purpose. "Rare on the web"
must not be measured with the dictionary itself or with the test set.

## Thresholds, chosen on dev only

Dev coverage (dev sentence records that fall in the niche) for each candidate pair. The table
comes from `uv run python -m pipeline.niche grid` and uses no model output:

| N_MIN | F_MAX | dev es→quc | dev quc→es |
| ---: | ---: | ---: | ---: |
| 1 | 0 | 40/115 | 14/115 |
| 1 | 1 | 46/115 | 18/115 |
| 1 | 2 | 53/115 | 25/115 |
| 1 | 5 | 61/115 | 39/115 |
| 1 | 10 | 66/115 | 49/115 |
| 1 | 20 | 68/115 | 55/115 |
| 2 | 0 | 10/115 | 1/115 |
| 2 | 1 | 13/115 | 2/115 |
| 2 | 2 | 13/115 | 2/115 |
| 2 | 5 | 18/115 | 4/115 |
| 2 | 10 | 22/115 | 9/115 |
| 2 | 20 | 28/115 | 17/115 |
| 3 | 0 | 2/115 | 0/115 |
| 3 | 1 | 4/115 | 0/115 |
| 3 | 2 | 4/115 | 0/115 |
| 3 | 5 | 7/115 | 1/115 |
| 3 | 10 | 9/115 | 1/115 |
| 3 | 20 | 12/115 | 3/115 |

**Rule:**
1. Keep the pairs that cover at least 10% of dev in **each** direction, so the test slice is
   big enough for a confidence interval.
2. Among those, take the rarest words (smallest `F_MAX`), then the largest `N_MIN`.

**Chosen:** `F_MAX = 0`, `N_MIN = 1`. A niche sentence has at least one content word from our
dictionaries whose K'iche' form never appears in the web reference corpus. Dev sentences are
short (median 5 words), so `N_MIN = 2` leaves almost nothing in quc→es.

Frozen members: `evals/niche_members.json` (`uv run python -m pipeline.niche freeze`), 1,220 of
the 3,308 test sentence records (865 es→quc, 355 quc→es). The list is frozen, so later data,
synthetic pairs or a new dictionary never move the slice.

## Evaluation protocol

- **Contenders:**
  - David is the stage variant (`tzij-2026-10-raft-bt-s3+hybrid+mbr4` today, or whichever
    variant is on stage when re-evaluated).
  - Goliath is `gemini-3.8-flash` without retrieval.
- **Slice:** the niche members that are in the standard `make eval` sample (150 pairs per
  source and direction, the stable hash sample), so both sides use predictions already
  produced by the normal evaluation.
- **Metrics, both directions together and per direction:**
  - corpus chrF++ for each side;
  - the difference (David − Goliath);
  - the win rate, meaning the share of sentences where David's sentence chrF++ is strictly
    higher (ties are reported separately).
- **Uncertainty:** paired bootstrap over sentences, 2,000 resamples, seed 2027, with 95%
  percentile intervals for the chrF++ difference and the win rate.
- **Decision rule:**
  - David **wins the niche** only if the 95% interval of the corpus chrF++ difference is
    entirely above 0.
  - If the interval contains 0, it is a tie.
  - If the interval is entirely below 0, Goliath wins.
- **Honest companion slices:** the same numbers for the whole test sample, by direction, by
  length and by domain.

## Known limitations of the definition

- K'iche' nouns usually appear possessed in running text (`uchaq'`, `nuja`). Bare dictionary
  forms can therefore look rarer than the word really is.
- The web reference is dominated by the New Testament. Everyday rural vocabulary (maize,
  beans, yeast) counts as rare because the Bible rarely uses it. That bias is in the definition
  on purpose: it is also roughly what a frontier model saw.
- BOUQuET sentences count for the evaluation, but the stage never shows them (their terms).

---

# Niche v2: a translation memory Goliath doesn't have (pre-registered)

Written and committed **before** any test computation for this slice. Niche v1 (above) stays as
it is: David lost it (`evals/niche_results.md`). A likely reason: Bloom has been on the open web
since 2012, so Goliath has probably seen it. A win is plausible only where David holds a
translation memory that Goliath lacks.

## Dev evidence that motivated it (dev split only)

Run `dev-rounds` (`evals/dev_report.md`). David is `tzij-2026-10-raft-bt-s3+hybrid+mbr4`; base is
`gemma4:e4b+hybrid`. chrF++ by source and direction:

| dev source · direction | n | David | base | Gemini |
| --- | ---: | ---: | ---: | ---: |
| Pontoon · es→quc | 38 | 48.3 | 40.1 | 26.2 |
| Pontoon · quc→es | 38 | 42.9 | 36.3 | 32.9 |
| COERLL · es→quc | 14 | 39.3 | 30.0 | 30.7 |
| COERLL · quc→es | 14 | 30.0 | 33.7 | 40.2 |
| UD · es→quc | 59 | 36.3 | 31.2 | 45.0 |
| UD · quc→es | 59 | 31.3 | 27.9 | 54.3 |
| UDHR · es→quc | 4 | 29.4 | 23.4 | 27.9 |
| UDHR · quc→es | 4 | 34.3 | 31.0 | 42.7 |

## Definition (code: `pipeline/niche2.py`)

- **Unit held out:** one whole Pontoon product, Spanish → K'iche'.
  - The Hugging Face snapshot has no product column. Pontoon's public K'iche' translation memory
    (`https://pontoon.mozilla.org/translation-memory/quc.all-projects.tmx`, same MPL-2.0 strings)
    labels each string with its project. Each pair is matched through its English pivot.
  - We considered whole COERLL lessons instead (seed 2027, at least 150 pairs) and rejected them
    before computing anything: 117 of their 166 pairs were course vocabulary rows in notation
    such as `venir => pet(ik)`, which aren't translation.
- **Rule:** hold out the product whose number of unambiguous es→quc train pairs is closest to 150.
  Counts in train: mozilla-monitor-website 397, **focus-for-android 144**, terminology 77,
  test-pilot-firefox-send 38, mozilla-accounts 22, focus-for-android-po 20, firefox 1.
  **Held out: `focus-for-android`** (Firefox Focus for Android): 144 es→quc pairs, 123 sentences and
  21 short UI terms.
- **Translation memory kept:** every other Pontoon product stays in train, in the retrieval
  index and in fine-tuning.
- **Removed from train:**
  - every other record of the held-out product, including strings shared with other products;
  - every train record repeating a held-out Spanish or K'iche' text.

  That's 458 records in total, 138 of them duplicates.
- **Dataset and index:** dataset `20261002-022500-niche2`. Dev is untouched. The test slice is
  `test_niche2.jsonl`, and the retrieval index is rebuilt from this train split.
- **Terms (WMT-style exact match):** frozen in `evals/niche2_terms.json`. 41 terms on 37 pairs.
  - A term is a train entry left after the holdout. It must be either a dictionary row
    (`kind=lexicon`) or a string from Pontoon's own `terminology` project.
  - Its Spanish side has 1–3 words with at least one content word, and that Spanish appears in
    the source.
  - Its K'iche' side appears in the reference.

## Evaluation protocol

- **Slice:** all 144 es→quc pairs (no sampling).
- **Goliath:** `gemini-3.8-flash`, no retrieval.
- **David:** two variants, both with retrieval from the niche2 index.
  1. `gemma4:e4b+hybrid+mbr4`, the base model, which is clean by construction.
  2. The stage configuration of a fine-tune **retrained from scratch on the niche2 train split**,
     i.e. a model that never saw the held-out product.

  `tzij-2026-10-raft-bt-s3` was trained on the held-out pairs, so it is excluded from any niche v2
  claim.
- **Primary metric:** corpus chrF++ for each side and David − Goliath, with a paired bootstrap
  (2,000 resamples, seed 2027) and a 95% interval.
- **Secondary metric:** term exact-match accuracy, as the share of the 41 terms whose K'iche'
  form appears in the hypothesis. It is reported for each side, with the bootstrap difference
  over the 37 pairs that have terms. Win rate is also reported.
- **Decision rule:**
  - David wins niche v2 only if the 95% interval of the chrF++ difference is entirely above 0.
  - If the interval contains 0, it is a tie.
  - If it is entirely below 0, Goliath wins.

  The rule is applied separately to each David variant, and both results are reported.
