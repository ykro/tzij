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
