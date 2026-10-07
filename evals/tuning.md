# Retrieval tuning (dev split)

Model `gemma4:e4b`, dataset `20260930-220035`, 222 dev sentence records (5% of the training sources, never indexed, never used for fine-tuning). Test is not used here.

| config | es → quc | quc → es | both | p50 |
| --- | ---: | ---: | ---: | ---: |
| vector k6 (baseline) | 32.0 | 29.8 | **30.9** | 1.14 s |
| hybrid k6 | 32.1 | 30.0 | **31.1** | 1.08 s |
| hybrid k6 + fuzzy | 31.3 | 30.3 | **30.8** | 1.05 s |
| hybrid k6 + fuzzy, best last | 33.2 | 31.6 | **32.5** | 1.04 s |
| hybrid k4 + fuzzy | 31.4 | 30.0 | **30.8** | 0.88 s |
| hybrid k8 + fuzzy | 33.8 | 31.5 | **32.7** | 1.18 s |

**Chosen:** hybrid k6 + fuzzy, best last → `RAG_MODE=hybrid`, `RAG_K=6`, `RAG_ORDER=best_last`, `RAG_FUZZY=1`.
It is within 0.2 points of the top score (k8, 32.7) — inside the noise of 222 sentences — with
25% shorter prompts, which matters twice: latency on stage, and how much retrieval-augmented
fine-tuning fits in a 1 h Cloud Run GPU task. Putting the closest example last (right before the
sentence to translate) is the single biggest change (+1.7 over the same config best-first).

## Order re-checked with the final David (2026-10-07)

The order was tuned with the base model. With the demo's David (`tzij-2026-10-mix-s7` + hybrid + MBR-4,
the cloud David through `make david-proxy`, the index of `20261002-173447`) it was measured again on the three
use cases of the page, with the same items and the same Goliath outputs; only `RAG_ORDER` changes.
Paired bootstrap of best last − best first (2,000 resamples, seed 2027):

| use case | n | best last | best first | best last − best first [95% CI] | Goliath |
| --- | ---: | ---: | ---: | ---: | ---: |
| Firefox Focus (test_niche) | 144 | 36.2 | 36.7 | −0.5 [−2.2, +1.2] | 28.9 |
| GATITOS words | 150 | 55.6 | 57.2 | −1.6 [−6.5, +3.5] | 22.1 |
| CLDR emoji names | 100 | 62.5 | 60.1 | +2.4 [−2.2, +7.7] | 25.7 |

No difference: every interval includes zero, and two runs with the same order differ as much (MBR samples):
Firefox Focus 35.3 (`niche-cloud`) and 36.2, GATITOS 57.5 (`evals/usecases.py`) and 55.6, CLDR 60.9 and 62.5.
`best_last` stays: it is what David was trained and evaluated with. Runs `niche-order-best_first`, `niche-order-best_last` and
`usecases-order` in `evals/runs/`.
