# Tzij — a Spanish ↔ K'iche' translator: a small model against Gemini

Demo for the talk **"David vs. Goliath: cómo un modelo pequeño le gana a un modelo frontier"** ("David vs. Goliath: how a small model beats a frontier model"). Tzij ("word" in K'iche') translates between Spanish and K'iche' (ISO 639-3 `quc`), Guatemala's most widely spoken Mayan language.

- **David** is Gemma 4 E4B fine-tuned with LoRA (`tzij-2026-10-mix-s7`), with a hybrid retrieval index built only from licensed K'iche' data, and MBR decoding. It runs in Ollama on its own GPU (an NVIDIA L4 on Cloud Run) that turns itself off when nobody uses it.
- **Goliath** is Gemini 3.8 Flash on Vertex AI, used the way anyone would use it.

The demo is a single public page on Cloud Run (`make page-url`): you type a sentence (or tap an example) and David and Goliath translate it at the same time, side by side. For the examples, sentences from the Firefox Focus interface, the page also shows the correct translation, the one people made, and how close each translation got to it. Nothing to run on talk day: open the page a few minutes before and it wakes David up.

The Spanish [README.md](README.md) is the primary document; this is a faithful English version.

![The page: David and Goliath translate the same Firefox Focus sentence](docs/demo/pagina-3-ejemplo.png)

## What you'll learn

1. **Licensed data and a split by source:** every K'iche' record carries a URL and a license, and a source is either entirely test or entirely training.
2. **What each step buys you:** retrieval is the biggest jump; the fine-tune started to pay off (+5.7) once its data looked like the test's domain.
3. **Goliath teaches once:** Gemini back-translates licensed K'iche' and writes distillation data for about $14; afterwards David translates without it.
4. **A pre-registered niche:** with a translation memory Goliath lacks, David wins by +8.5 chrF++.
5. **A small model in the cloud:** David, his index and his decoding in one image, on a Cloud Run GPU that starts when the page opens and turns itself off.

## The demo: the page

| | David | Goliath |
| --- | --- | --- |
| What it is | Fine-tuned Gemma 4 E4B (`tzij-2026-10-mix-s7`) + hybrid retrieval + MBR-4 | Gemini 3.8 Flash, no extra data |
| Where it runs | Cloud Run with 1× NVIDIA L4 (`tzij-david`, private) | Vertex AI |

- **Examples:** 11 Firefox Focus sentences in Spanish, with their correct K'iche' translation (Mozilla Pontoon, MPL-2.0 license). Each was translated 3 times by the cloud David and by Goliath, as the page does, and only the ones where David always stayed close to the correct translation (chrF++ 50 or more) and at least 15 points closer than Goliath were kept. They live in [`duel/examples.json`](duel/examples.json), with the measured outputs and scores; `make examples` re-checks them.
- **"Se parece a la correcta"** (how close to the correct one): chrF++ against the human translation, as a percentage. It only shows for examples: a typed sentence has no correct translation to compare with, so the page shows the two translations.
- **David wakes up on his own:** his GPU has a minimum of 0 instances. When the page opens it says «Preparando a David…» for about 3 minutes and then «David listo»; while the page stays open, it keeps him awake.
- **Direction:** the examples and the demo are Spanish → K'iche', the case David wins. The page also translates K'iche' → Spanish (the ⇄ button), but that direction is not shown in the talk (see [below](#why-the-demo-uses-only-the-final-model)).

The script, with screenshots and timings, is in [docs/DEMO.en.md](docs/DEMO.en.md).

![Architecture: everything on Google Cloud](docs/diagrams/architecture.png)

## Results (evaluation)

Measured with `make eval` (run `final-20261002`, dataset `20261002-173447`) and `make niche`. Details in [evals/report.md](evals/report.md) and [evals/niche_results.md](evals/niche_results.md).

| | David (`mix-s7` + hybrid + MBR-4) | Goliath (`gemini-3.8-flash`) |
| --- | ---: | ---: |
| **Specialty:** translation memory, Firefox Focus, 144 es → quc sentences (chrF++) | **37.4** | 28.9 |
| General: 600 test sentences from Bloom and BOUQuET, both directions (chrF++) | 25.7 | **36.9** |

On the specialty David wins by **+8.5** [95% CI: +4.7, +12.7] on a product it never saw. In general translation Goliath leads by 11.2 points; the gap is general K'iche', not one kind of sentence ([experiment 10](#what-each-experiment-told-us)).

## Experiments

Every number comes from [`evals/`](evals/), [`train/runs/`](train/runs/) and the [logbook](docs/BITACORA.md) (Spanish), which has the full story with dates. Rules: the 600 test sentences (150 per source and direction, from Bloom and BOUQuET) are never in the index or in training; decisions are made on a development split (dev, and from experiment 10 on, `dev_domain`); the test set is used for the final number. chrF++ goes from 0 to 100: higher is better.

### Summary

The experiments ran with David on the laptop (Apple Silicon, Ollama), before everything moved to the cloud: the latencies in these tables are from that machine. In the cloud, see [David on the Cloud Run GPU](#david-on-the-cloud-run-gpu).

| # | Experiment | Variant | chrF++ test (600) | Other measure | p50 latency | One-off cost | Outcome |
| ---: | --- | --- | ---: | --- | ---: | ---: | --- |
| 0 | Base, no data | `gemma4:e4b` | 11.7 | — | 1.31 s | $0 | Starting point |
| 1 | + vector retrieval | `gemma4:e4b+rag` | 18.5 | — | 1.84 s | $0 | The biggest gain |
| 2 | Fine-tune without retrieval context | `tzij-2026-09` + retrieval | 17.6* | — | — | $0.70 (+$0.41 cancelled) | Dead end |
| 3 | Hybrid retrieval (BM25 + vectors) | `gemma4:e4b+hybrid` | 19.4 | dev 30.9 → 32.5 | 1.75 s | $0 | Kept |
| 4 | RAFT + Gemini back-translation, 1 epoch | `tzij-2026-10-raft-bt-s3+hybrid` | 18.3 | — | 1.72 s | $3.09 L4 + $0.12 Gemini | Doesn't help on its own |
| 5 | + MBR (4 samples) | `tzij-2026-10-raft-bt-s3+hybrid+mbr4` | 21.5 | — | 3.96 s | $0 | The demo's David from Oct 2 to 5 |
| 6 | The pre-registered niche (Firefox Focus) | `gemma4:e4b+hybrid+mbr4` | — | specialty 30.2 vs 28.9 | — | $0 | Tie in chrF++, wins on terminology |
| 7 | Dictionary-anchored synthetic data | `tzij-2026-10-n2b-s1` | — | dev 33.8 vs 34.2 | — | $2.09 Gemini + $1.14 L4 | Dropped |
| 8 | Logit bias toward the dictionary | `n2a-s1` + llama-server | — | dev 33.8 vs 35.0 | 5.2 s | $0 | Dropped |
| 9 | More epochs and more Spanish → K'iche' | `tzij-2026-10-tm-a-e2-s4` | — | dev 37.5 vs 36.6 | 4.5 s | $6.16 L4 | Tie |
| 10 | Why David loses; Gemini Pro | `gemini-3.1-pro-preview` | — | `dev_domain` 40.5 vs 40.6 | — | $1.85 | The gap is general K'iche' |
| 11 | Back-translated Bloom + distillation | `tzij-2026-10-mix-s7+hybrid+mbr4` | **25.7** | specialty **37.4** vs 28.9 | 4.14 s | $8.52 L4 + $13.94 Gemini | **The demo's David** |

\* Measured on the September 30 dataset (same test sources). There, the base with retrieval scored 18.4.

### Every variant on the test set

The 600 test sentences, run `final-20261002` ([evals/report.md](evals/report.md)). Latencies on the laptop; the last column is Gemini's API cost.

| Variant | es → quc | quc → es | Both | p50 | p95 | API / 1,000 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gemma4:e4b` | 7.5 | 16.7 | 11.7 | 1.31 s | 3.56 s | $0 |
| `gemma4:e4b+rag` | 18.2 | 18.8 | 18.5 | 1.84 s | 4.76 s | $0 |
| `gemma4:e4b+hybrid` | 19.0 | 19.8 | 19.4 | 1.75 s | 4.73 s | $0 |
| `gemma4:e4b+hybrid+mbr4` | 20.4 | 20.9 | 20.7 | 4.59 s | 16.33 s | $0 |
| `tzij-2026-10-raft-s0+hybrid` (1/4 epoch, no back-translation) | 13.9 | 15.5 | 14.6 | 1.64 s | 4.65 s | $0 |
| `tzij-2026-10-raft-bt-s0+hybrid` (1/4 epoch, with back-translation) | 14.9 | 16.5 | 15.7 | 1.62 s | 4.59 s | $0 |
| `tzij-2026-10-raft-bt-s3` (no retrieval) | 9.2 | 17.4 | 13.0 | 1.20 s | 4.62 s | $0 |
| `tzij-2026-10-raft-bt-s3+hybrid` | 18.4 | 18.3 | 18.3 | 1.72 s | 4.67 s | $0 |
| `tzij-2026-10-raft-bt-s3+hybrid+mbr4` | 21.9 | 21.2 | 21.5 | 3.96 s | 14.21 s | $0 |
| `tzij-2026-10-mix-s7+hybrid` | 26.9 | 23.2 | 25.1 | 1.64 s | 4.28 s | $0 |
| **`tzij-2026-10-mix-s7+hybrid+mbr4`** | **27.0** | **24.3** | **25.7** | 4.14 s | 13.43 s | $0 |
| `gemini-3.8-flash` | 33.4 | 40.7 | 36.9 | 1.73 s | 4.71 s | $0.292 |
| `gemini-3.8-flash+rag` (Gemini with David's index) | 34.6 | 40.1 | 37.2 | 2.08 s | 6.46 s | $0.947 |

**Fine-tune vs. base, with the same retrieval and decoding:** `mix-s7` adds +5.7 with hybrid retrieval (25.1 vs 19.4) and +5.0 with MBR (25.7 vs 20.7). The previous David, `raft-bt-s3`, took away −1.1 with hybrid retrieval and only added +0.8 with MBR.

**Ablation** (what each step bought, up to the October 2 David and then the final one):

| Step | Variant | Both | Δ | p50 |
| --- | --- | ---: | ---: | ---: |
| Base + vector retrieval | `gemma4:e4b+rag` | 18.5 | — | 1.84 s |
| + hybrid retrieval | `gemma4:e4b+hybrid` | 19.4 | +0.9 | 1.75 s |
| + RAFT with back-translation (1 epoch) | `tzij-2026-10-raft-bt-s3+hybrid` | 18.3 | −1.1 | 1.72 s |
| + MBR (4 samples) | `tzij-2026-10-raft-bt-s3+hybrid+mbr4` | 21.5 | +3.2 | 3.96 s |
| + in-domain data, 2 epochs, back-translated Bloom and distillation | `tzij-2026-10-mix-s7+hybrid+mbr4` | 25.7 | +4.2 | 4.14 s |

### The specialty, pre-registered

A translation memory is the real case where a small model can win: an organization has already translated its products and wants to translate a new one with the same words. To test it without cheating:

- a whole Mozilla Pontoon product, **Firefox Focus**, was held out: 144 Spanish → K'iche' pairs that are neither in training nor in the index;
- Mozilla's other products stay in David's index as the translation memory;
- the rule, the product and the 41 terms were published in git ([`evals/niche.md`](evals/niche.md)) before computing anything;
- chrF++ and WMT-style terminology accuracy are measured with a paired bootstrap (2,000 resamples, 95% CI).

| David | David chrF++ | Goliath chrF++ | David − Goliath [95% CI] | Sentences David wins | Terminology, David | Terminology, Goliath |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base + hybrid + MBR-4 (pre-registered index) | 29.7 | 28.9 | +0.9 [−2.8, +4.6] | — | 83% | 46% |
| Base + hybrid + MBR-4 (+ CLDR and FLORES-Mayas in the index) | 30.2 | 28.9 | +1.3 [−2.3, +5.3] | 49% | 78% | 46% |
| `mix-s7` + hybrid | 35.9 | 28.9 | +7.0 [+2.9, +11.1] | 56% | 59% | 46% |
| **`mix-s7` + hybrid + MBR-4** | **37.4** | 28.9 | **+8.5** [+4.7, +12.7] | 57% | 61% | 46% |

With the final David, the chrF++ difference no longer includes zero. On terminology it is +15 points, but that interval does include zero ([−2, +32]).

### What each experiment told us

**0. The base.** Gemma 4 E4B with the same instructions as Gemini, no context. 11.7 chrF++, and 7.5 in Spanish → K'iche': the model barely writes K'iche'. *We learned:* this is what anyone downloading a small model gets; the starting point has to be measured.

**1. Vector retrieval.** A local index of about 7,000 licensed pairs and dictionary entries, with EmbeddingGemma and `sqlite-vec`; David gets 6 examples and 6 glossary entries per sentence. 11.7 → 18.5 (Spanish → K'iche': 7.5 → 18.2). *We learned:* a small model doesn't know K'iche', but it copies and adapts what we give it well. No other step moved David as much.

**2. Fine-tune without context (`tzij-2026-09`).** LoRA r=16, 1 epoch with 5,180 examples, trained without the retrieval context; 22 min of L4 on Cloud Run, $0.70. On its own it lifts the base from 11.5 to 15.2; with retrieval it scores 17.6, 0.8 below the base with retrieval (18.4). *We learned:* if David translates with retrieval, it has to train with it.

**3. Hybrid retrieval.** BM25 (SQLite FTS5) next to the vectors, fused with Reciprocal Rank Fusion, an exact and fuzzy glossary, and the closest example last. Tuned on dev only ([evals/tuning.md](evals/tuning.md)):

| Configuration (dev, 222 sentences) | Both | p50 |
| --- | ---: | ---: |
| Vectors, k=6 | 30.9 | 1.14 s |
| Hybrid, k=6 | 31.1 | 1.08 s |
| Hybrid, k=6 + fuzzy | 30.8 | 1.05 s |
| **Hybrid, k=6 + fuzzy, best example last** | **32.5** | 1.04 s |
| Hybrid, k=4 + fuzzy | 30.8 | 0.88 s |
| Hybrid, k=8 + fuzzy | 32.7 | 1.18 s |

On the test set: 18.5 → 19.4. *We learned:* BM25 finds the rare words and names that embeddings blur, and context order matters: putting the closest example last added +1.7 by itself. k=8 ties within the noise with 25% longer prompts, so k=6 stayed.

**4. RAFT + back-translation.** The fine-tune sees the same retrieved context David gets when translating (RAFT). Gemini translated 405 licensed K'iche' sentences into Spanish (399 pairs, $0.12), which only train Spanish → K'iche'. 1 epoch with 5,579 examples in 4 chunks of 1/4 epoch, because of the 1 h limit of a Cloud Run GPU task ($3.09 of L4). With hybrid retrieval: 18.3, −1.1 against the hybrid base. On the same 1/4-epoch budget, back-translation did help: 15.7 vs 14.6. *We learned:* fine-tuning on this data still didn't beat the base with good retrieval.

**5. MBR.** David generates 4 translations at temperature 0.7 and keeps the one with the highest average chrF++ against the others. 18.3 → 21.5 (+3.2), and the fine-tune now adds +0.8 over the base with MBR. p50 goes from 1.7 to 4.0 s. *We learned:* consensus is the second biggest gain and costs no money; it fit the laptop's 5 s budget and turns off with `DAVID_MBR=0`.

**6. The niche.** A first definition (rare dictionary words) didn't work: Goliath still won. Dev showed where David won (Pontoon 48.3 vs Gemini's 26.2; COERLL 39.3 vs 30.7; UD 36.3 vs 45.0), and Firefox Focus was pre-registered on that basis. With the base: 30.2 vs 28.9, a chrF++ tie, but 78% vs 46% on terminology. *We learned:* David's ground is a translation memory Goliath doesn't have; it was the first slice where David wasn't behind.

**7. Dictionary-anchored synthetic data.** Gemini wrote sentences with each dictionary entry, and words in UD sentences were swapped for attested forms: 5,295 + 198 pairs filtered by alphabet, duplicates and round trip ($2.09). A/B on dev with the same budget: 33.8 with 20% synthetic (`n2b-s1`) vs 34.2 without (`n2a-s1`). *We learned:* they lower the training loss because they're easy text, but they don't translate better. Dropped.

**8. Logit bias toward the dictionary.** With `llama-server`, the first token of an exact dictionary translation gets a bias, combined with 8-sample MBR and varied prompts. On dev (230 sentences, `n2a-s1`):

| Decoding | dev chrF++ | p50 |
| --- | ---: | ---: |
| Greedy | 34.2 | 1.2 s |
| MBR 4 | 34.1 | 4.2 s |
| MBR 8 multi-prompt | 35.0 | 7.1 s |
| MBR 8 multi-prompt + bias | 33.8 | 5.2 s |

*We learned:* the bias makes it worse (−1.2 against the same MBR without bias). Multi-prompt MBR adds +0.8, but its 7.1 s p50 exceeds the 5 s limit. Neither went in.

**9. More epochs and more Spanish → K'iche'.** The RAFT recipe with back-translation, in 1/5-epoch chunks that continue the previous adapter ($6.16 of L4). On dev (230 sentences):

| David | es → quc | quc → es | Both | With MBR-4 | p50 (MBR-4) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `raft-bt-s3` (1 epoch) | 37.8 | 35.3 | 36.6 | 37.6 | 3.9 s |
| `tm-a-s4` (1 epoch, es → quc ×1.5) | 36.7 | 34.7 | 35.8 | 36.7 | 4.0 s |
| `tm-a-e2-s4` (2 epochs) | 39.8 | 35.1 | 37.5 | 38.1 | 4.5 s |
| `tm-b-s1` (es → quc ×2, 0.4 epochs) | 35.4 | 31.8 | 33.7 | — | — |
| Goliath | 33.7 | 43.9 | 38.6 | — | 1.6 s |

Two epochs vs one: +0.9 [−1.0, +2.9] without MBR and +0.5 [−1.2, +2.4] with MBR. *We learned:* these are ties; training longer doesn't buy a measurable improvement, and neither does raising Spanish → K'iche' to ×2. The 2-epoch adapter was kept as the starting point of experiment 11.

**10. Why David loses in general.** The dev split (UD, Pontoon, COERLL, DUDH) didn't look like the test set, so `dev_domain` was created (514 BOUQuET and Bloom sentences outside the test sample). On the test set David was 11 to 22 points behind across every source, domain and length. David had 2,541 licensed sentence pairs (about 31,000 K'iche' words); MINGOB's news alone, unlicensed, is about 1 million. And a bigger Goliath doesn't translate better: `gemini-3.1-pro-preview` scored 40.5 vs Flash's 40.6 on `dev_domain`, with 3 times the latency and 21 times the cost. Also, Gemma's tokenizer splits a K'iche' word into 2.64 tokens vs 1.41 for Spanish ([evals/fertility.md](evals/fertility.md)). *We learned:* the gap is how much K'iche' is on the web, not model size; the only way out is more in-domain data.

**11. Back-translated Bloom + distillation (`mix-s7`).** From the 2-epoch adapter, three runs in parallel on 3 L4s, each with 30% of the web pairs as replay. Back-translated Bloom: 1,998 new pairs, both directions. Distillation: Gemini wrote 10,585 everyday Spanish sentences in the test's domains, translated 6,000 into K'iche' with David's context, and 2,409 survived the filters; they never enter the dataset, the index, dev or the test set. On `dev_domain`, against the starting adapter (22.1):

| Run | Δ both [95% CI] | By direction |
| --- | ---: | --- |
| Back-translated Bloom (`bl-s3`) | +1.5 [+0.7, +2.2] | quc → es +4.3; es → quc −1.2 |
| Distillation (`dst-s4`) | +2.1 [+1.5, +2.8] | es → quc +3.0 |
| **Both (`mix-s7`): 25.8** | **+3.6** [+2.9, +4.3] | +3.7 in each direction |

On the test set, 25.7: +4.1 [+3.6, +4.7] over the previous David, and the gap with Goliath shrinks from 15.4 to 11.2. On the specialty, 37.4 vs 28.9. *We learned:* the two effects add up. Goliath acts as a teacher once, for $13.94, and afterwards David translates without it. A second distillation batch (1,877 pairs, $6.98) was generated but didn't go into `mix-s7`.

### David on the Cloud Run GPU

The page runs on Cloud Run and David on another Cloud Run service with an NVIDIA L4 (`europe-west4`), with the model, EmbeddingGemma and the index inside the image. Measured from the page with the 11 examples, 3 times each (`duel/examples.json`):

| | David (L4, `tzij-david`) | Goliath (Vertex AI) |
| --- | ---: | ---: |
| Time, median of 33 translations | 0.9 s | 2.0 s |
| Translations where David answered first | 26 of 33 | — |
| Start from zero (GPU off) | about 3 min | — |
| Cost of one translation | about $0.0004 (L4 + 8 vCPU + 32 GiB at $0.000395 per second while the instance is up) | about $0.0001 (tokens) |

David usually answers first, but not always; and in the cloud he costs more per translation than Gemini, and the GPU bills while it's up (about $1.42 per hour; it turns itself off about 15 minutes after the last request). That's why the page shows neither time nor cost: it only compares the translations. With the page closed, David costs nothing.

### Cost of training David

| Runs | Jobs | Job duration | L4 cost |
| --- | ---: | ---: | ---: |
| `tzij-2026-09` | 1 | 30 min | $0.70 |
| `raft-s0`, `raft-bt-s0` … `s3` | 5 | 130 min | $3.09 |
| `n2a`, `n2b` (synthetic A/B) | 4 | 103 min | $2.44 |
| `tm-a`, `tm-a-e2`, `tm-b` (epochs) | 10 | 260 min | $6.16 |
| `bl`, `dst`, `mix` (data round) | 17 | 360 min | $8.52 |

Gemini as teacher: $0.12 (first back-translation) + $2.09 (synthetic, discarded) + $13.94 (data round) + $1.85 (Gemini Pro measurement). Every run is in [`train/runs/`](train/runs/), with machine, duration and cost per stage.

## Why the demo uses only the final model

The page shows a single David: `tzij-2026-10-mix-s7` + hybrid retrieval + MBR-4. The other variants are measured above but don't appear in the demo, for these reasons:

- **It's the best on both measures.** 25.7 on the general test, vs 21.5 for the previous David and 20.7 for the best base, and 37.4 on the specialty, vs 30.2 for the base with the same index.
- **It's the only one that can play the specialty cleanly.** The earlier fine-tunes (`tzij-2026-09`, `raft-s0`, `raft-bt-s0` … `s3`) trained on Firefox Focus before it was held out; with them the examples would measure memory, not translation.
- **MBR-4 is worth it.** Without MBR, `mix-s7` scores 25.1 (35.9 on the specialty); with MBR-4, 25.7 (37.4). On the laptop it took 4.14 s; on the Cloud Run L4 the page gets it in 0.9 s (median). Experiment 8's multi-prompt MBR scored higher on dev but took 7.1 s on the laptop.
- **The demo shows the case David wins.** On the translation memory, David translates better than Goliath; that is what the page compares. In general translation Goliath stays ahead (36.9 vs 25.7), most clearly in K'iche' → Spanish (−16.4). Those numbers are above and in the [logbook](docs/BITACORA.md), but the talk doesn't show that direction or those sentences.
- **A per-sentence comparison has to be fair to both.** The examples were chosen among sentences neither model saw, and checked live with both models. The measured outputs, scores and times are in [`duel/examples.json`](duel/examples.json).

## Quickstart

```bash
cp .env.example .env                       # models, buckets and regions; .env is never committed
uv sync
gcloud auth login && gcloud auth application-default login
make deploy                                # project, jobs, David on his GPU and the page
open "$(make -s page-url)"                 # David and Goliath side by side
make test                                  # tests with mock models (MOCK_AI=1): no GPU, no cloud
```

No model is downloaded to the laptop. To measure against the cloud David (`make eval`, `make index`), `make david-proxy` ([details](docs/COMANDOS.en.md)).

## Documentation

- [docs/DEMO.en.md](docs/DEMO.en.md): demo script (the page) with screenshots, talk points and timings.
- [docs/ONBOARDING.md](docs/ONBOARDING.md): prerequisites, setup, cloud, data, training, tests, troubleshooting and talk day (Spanish).
- [docs/BITACORA.md](docs/BITACORA.md): David's story iteration by iteration, with dates and costs (Spanish).
- [docs/DECISIONES.en.md](docs/DECISIONES.en.md): every technical decision, full results and versions.
- [docs/COMANDOS.en.md](docs/COMANDOS.en.md): deploying, measuring and every `make` command.
- [docs/ESTRUCTURA.en.md](docs/ESTRUCTURA.en.md): what runs where in the cloud, pipeline and repository map.
- [docs/CREDITOS.en.md](docs/CREDITOS.en.md): data sources, owners and licenses.
- [MODEL_CARD.md](MODEL_CARD.md): what David is, its data, results and limits.
- [evals/report.md](evals/report.md): evaluation report by source, length, domain and failure.
- [docs/diagrams/](docs/diagrams/): architecture, pipeline, results and logbook (HTML, SVG and PNG).
- [data/SOURCES.md](data/SOURCES.md) and [data/DATASHEET.md](data/DATASHEET.md): sources and counts per source.
