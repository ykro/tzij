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
