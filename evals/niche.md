# The niche: a translation memory Goliath doesn't have (pre-registered)

Written and committed **before** any test computation for this slice (commit `65d6f9f`, pushed
to GitHub before the first niche prediction). Results: [`niche_results.md`](niche_results.md).

**Hypothesis:** David can beat Goliath where he holds a translation memory Goliath lacks. Text
that is on the open web (children's books, UD) Goliath has probably seen.

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

## Definition (code: `pipeline/niche.py`)

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
- **Dataset and index:** the niche is `test_niche.jsonl` of the dataset built by
  `pipeline/niche.py` (now `20261002-173447`). Dev is untouched, and the retrieval index is rebuilt
  from this train split. The 30% religious cap is re-applied after the removal (58 religious pairs
  dropped).
- **Translation memory added later:** two terminology sources were added as lexicon (index only,
  never trained) after registration: Unicode CLDR (1,164 pairs) and the FLORES-Mayas glossary
  (407). They are deduplicated against dev, the test set and the niche. The niche and its terms
  don't change. Results with and without them are reported side by side.
- **Terms (WMT-style exact match):** frozen in `evals/niche_terms.json`. 41 terms on 37 pairs.
  - A term is a train entry left after the holdout. It must be either a dictionary row
    (`kind=lexicon`) or a string from Pontoon's own `terminology` project.
  - Its Spanish side has 1–3 words with at least one content word, and that Spanish appears in
    the source.
  - Its K'iche' side appears in the reference.

## Evaluation protocol

- **Slice:** all 144 es→quc pairs (no sampling).
- **Goliath:** `gemini-3.8-flash`, no retrieval.
- **David:** two variants, both with retrieval from the index built without the held-out product.
  1. `gemma4:e4b+hybrid+mbr4`, the base model, which is clean by construction.
  2. The stage configuration of a fine-tune **retrained from scratch without the held-out
     product**, i.e. a model that never saw it.

  `tzij-2026-10-raft-bt-s3` was trained on the held-out pairs, so it is excluded from any niche
  claim.
- **Primary metric:** corpus chrF++ for each side and David − Goliath, with a paired bootstrap
  (2,000 resamples, seed 2027) and a 95% interval.
- **Secondary metric:** term exact-match accuracy, as the share of the 41 terms whose K'iche'
  form appears in the hypothesis. It is reported for each side, with the bootstrap difference
  over the 37 pairs that have terms. Win rate is also reported.
- **Decision rule:**
  - David wins the niche only if the 95% interval of the chrF++ difference is entirely above 0.
  - If the interval contains 0, it is a tie.
  - If it is entirely below 0, Goliath wins.

  The rule is applied separately to each David variant, and both results are reported.
