# Tzij — a Spanish ↔ K'iche' translator: a small model against Gemini

Demo for the talk **"David vs. Goliath: cómo un modelo pequeño le gana a un modelo frontier"** ("David vs. Goliath: how a small model beats a frontier model"). Tzij ("word" in K'iche') translates between Spanish and K'iche' (ISO 639-3 `quc`), Guatemala's most widely spoken Mayan language.

- **David** is Gemma 4 E4B fine-tuned with LoRA (`tzij-2026-10-mix-s7`), with a hybrid retrieval index built only from licensed K'iche' data, and MBR decoding. It runs in Ollama on its own GPU (an NVIDIA L4 on Cloud Run) that turns itself off when nobody uses it.
- **Goliath** is Gemini 3.8 Flash on Vertex AI, used the way anyone would use it.

The demo is a single public page on Cloud Run (`make page-url`): you type a sentence (or tap an example) and David and Goliath translate it at the same time, side by side. For the examples, sentences from the Firefox Focus interface, the page also shows the correct translation, the one people made, and how close each translation got to it; for every sentence, how long each translation took and what it cost. Nothing to run on talk day: open the page a few minutes before and it wakes David up.

The Spanish [README.md](README.md) is the primary document; this is a faithful English version.

![The page: David and Goliath translate the same Firefox Focus sentence](docs/demo/pagina-3-ejemplo.png)

## What you'll learn

1. **Licensed data and a split by source:** every K'iche' record carries a URL and a license, and a source is either entirely test or entirely training.
2. **What each step buys you:** retrieval is the biggest jump; the fine-tune started to pay off (+5.7) once its data looked like the test's domain.
3. **Goliath teaches once:** Gemini back-translates licensed K'iche' and writes distillation data for about $14; afterwards David translates without it.
4. **A pre-registered niche:** with a translation memory Goliath lacks, David wins by +8.5 chrF++.
5. **A small model in the cloud:** David, his index and his decoding in one image, on a Cloud Run GPU that starts when the page opens and turns itself off.

## Hands-on codelab

The codelab for this talk is “Train your own David” ([codelabs-2027/entrena-tu-david](https://github.com/ykro/codelabs-2027/tree/main/entrena-tu-david)), in Spanish: you fine-tune Gemma 4 E2B with LoRA on Colab and measure it against the base model. It runs in the browser with a Google account and ends with something that works.

## The demo: the page

| | David | Goliath |
| --- | --- | --- |
| What it is | Fine-tuned Gemma 4 E4B (`tzij-2026-10-mix-s7`) + hybrid retrieval + MBR-4 | Gemini 3.8 Flash, no extra data |
| Where it runs | Cloud Run with 1× NVIDIA L4 (`tzij-david`, private) | Vertex AI |

- **Examples, by use case:** only from use cases David wins as a whole measured set ([use cases](#use-cases-where-david-wins)): 6 Firefox Focus interface strings (Mozilla Pontoon, MPL-2.0), 8 everyday words from the GATITOS dictionary (Google Research, CC BY 4.0) and 6 emoji names from Unicode CLDR (Unicode License V3), each with its correct translation. Each group says how both did on its full set. Each was translated 3 times by the cloud David and by Goliath, as the page does, and only the ones where David always stayed close to the correct translation (chrF++ 50 or more) and at least 15 points closer than Goliath were kept. They live in [`duel/examples.json`](duel/examples.json), with the measured outputs and scores; `make examples` re-checks them.
- **"Se parece a la correcta"** (how close to the correct one): compares each translation with the one people made, in small pieces of letters and words, and says how much they share: 100 % is identical, 0 % shares nothing. If the correct one is «Chajital tʼiqonem», «Chajital tʼiqoj» scores 66 % and «Jikilik tʼiqoj» 16 %. It's chrF++, the usual measure for comparing machine translators; [details below](#what-chrf-is).
- **A typed sentence:** if it's in the licensed data (the test sets, David's translation memory or the dictionary), the page recognizes it, shows its correct translation and measures both sides like an example. If not, there's nothing to measure against and the page says so; to help judge, it shows the 3 closest sentences in the translation memory, translated by people, and marks in each column the words those translations also use (the memory's terminology). It is not a score. A word-by-word dictionary check was discarded: on the examples, Goliath's wrong translations had more dictionary words than David's right ones, so it would have misled.
- **Time and cost:** each column shows how long that translation took and what it cost. David runs on his own GPU, billed per second while it's up: his cost is the seconds he worked × the instance's price per second (L4 + 4 vCPU + 16 GiB in `europe-west4`: $0.0002907/s, $1.05 per hour). Goliath bills per token, at Gemini's list price of the day ($0.75 / $3.75 per million; from January 1, 2027, $1.50 / $7.50). Who wins when: [Projections](#projections-cost-and-time).
- **David wakes up on his own:** his GPU has a minimum of 0 instances. When the page opens it says «Preparando a David…» for about 40 s (it used to be 3 min 24 s; see [cold start](#cold-start)) and then «David listo»; while the page stays open, it keeps him awake.
- **On a phone:** the page adapts to phones and tablets: one column, David above Goliath, and the examples scroll sideways.
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

**Repeated with David in the cloud** (October 7, same model and same index, on the Cloud Run L4; runs `cloud-20261007`, `niche-cloud` and `tm-new`):

| | David | Goliath | David − Goliath [95% CI] |
| --- | ---: | ---: | ---: |
| Specialty: the 144 Firefox Focus sentences | **35.3** | 28.9 | **+6.4** [+2.5, +10.5] |
| Specialty: 105 more Firefox Focus sentences, newer than the dataset ([`evals/tm_new_results.md`](evals/tm_new_results.md)) | **36.5** | 30.4 | **+6.1** [+3.0, +9.2] |
| General: the same 600 test sentences | 25.8 | **36.9** | −11.1 |

In the cloud David scores the same on the general test (25.8 vs 25.7) and answers faster (median 1.77 s vs 4.14 s on the laptop). On the 144 Firefox Focus sentences it scores 35.3 instead of 37.4: MBR picks among 4 sampled translations, so two runs don't give the same number; the lead over Goliath holds in both (+6.4 and +8.5, and the interval excludes zero). The 105 new Firefox Focus sentences confirm it with sentences that were in no earlier run ([experiment 13](#what-each-experiment-told-us)).

### Use cases where David wins

Besides the translation memory, other use cases were measured as sets, with fixed seeded samples never picked by result ([`evals/usecases.py`](evals/usecases.py), [`evals/usecases_results.md`](evals/usecases_results.md), against the cloud David):

| Use case | n | David | Goliath | David − Goliath [95 % CI] | Exact translation: David | Goliath | Goliath with the same glossary |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Firefox Focus interface (translation memory, unseen sentences) | 144 | **37.4** | 28.9 | +8.5 [+4.7, +12.7] | — | — | — |
| Everyday words from the GATITOS dictionary (Google Research) | 150 | **57.5** | 22.1 | +35.4 [+28.0, +42.6] | 37 % | 9 % | 85 % |
| Emoji names from Unicode CLDR | 100 | **60.9** | 25.7 | +35.2 [+28.1, +42.5] | 42 % | 1 % | 91 % |
| General sentences (Bloom, BOUQuET), any length or source | 600 | 25.8 | **36.9** | −11.1 | — | — | — |

- **The dictionaries are a data advantage, not a model one.** Those words are in the dictionary David consults; Goliath, used as anyone uses it, doesn't have it. With the same glossary in the prompt, Gemini gets more right than David (88.6 and 94.4 chrF++): the fine-tuned model with MBR doesn't always copy the glossary entry exactly. The use case is real (an organization with its own glossary), but what wins is having the data.
- **No other use case was won by David.** By source, direction and length (1 to 3 words, 4 to 6, 7 to 10 and more) on the 600 test sentences, Goliath wins all of them except 4–6-word Spanish → K'iche' sentences, a tie (30.1 vs 29.7). Mozilla Monitor, another Mozilla interface, is also lost ([experiment 13](#what-each-experiment-told-us)).
- **The context order doesn't change these numbers.** David gets the closest example last, right next to the sentence (`RAG_ORDER=best_last`, as he was trained). Measured again with the final David in the cloud, with the closest example first: Firefox Focus 36.7 vs 36.2, GATITOS 57.2 vs 55.6, CLDR 60.1 vs 62.5; all three intervals include zero, and two runs with the same order vary as much because of MBR ([evals/tuning.md](evals/tuning.md)).

### What chrF++ is

It's the measure each translation is scored with against the one people made, and what the page calls «se parece a la correcta». It splits both translations into pieces of 1 to 6 letters in a row and into single words and word pairs, and counts how many pieces they share: 100 is identical, 0 shares nothing. It gives partial credit to an almost-right word, which matters more in K'iche' (long words with prefixes and suffixes) than in other languages. Example, with the correct «Chajital tʼiqonem»: «Chajital tʼiqoj» scores 66 and «Jikilik tʼiqoj», 16. It doesn't understand meaning: a correct synonym lowers the score. That's also why the specialty was pre-registered and a speaker can validate the test set.

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
| 12 | EmbeddingGemma 2 in retrieval (in the cloud) | `mix-s7` + index built with `embeddinggemma-2` | 23.9 (vs 25.8) | dev 38.8 vs 39.9; specialty 37.0 vs 35.3 | — | $0 | Out: no gain |
| 13 | Newer Pontoon strings (in the cloud) | `tzij-2026-10-mix-s7+hybrid+mbr4` | — | Firefox Focus 36.5 vs 30.4; Mozilla Monitor 22.0 vs 32.6 | — | $0.03 Gemini | Firefox Focus to the page; Mozilla Monitor no |

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

**More sentences of the same case** ([experiment 13](#what-each-experiment-told-us), not pre-registered). Pontoon's public translation memory has strings newer than the dataset. Those in no split and not in the index ([`evals/tm_new.py`](evals/tm_new.py)), measured with David in the cloud ([`evals/tm_new_results.md`](evals/tm_new_results.md)):

| Product | Sentences | David chrF++ | Goliath chrF++ | David − Goliath [95% CI] | Sentences David wins |
| --- | ---: | ---: | ---: | ---: | ---: |
| Firefox Focus (the held-out product) | 105 | **36.5** | 30.4 | **+6.1** [+3.0, +9.2] | 64% |
| Mozilla Monitor (David has its older strings in the index) | 57 | 22.0 | **32.6** | −10.7 [−20.2, −0.5] | 30% |

On Firefox Focus, David wins again with sentences that had never been measured. On Mozilla Monitor's new strings he loses: they are long marketing-website texts with little vocabulary repeated from the memory. That's why the page uses only Firefox Focus sentences.

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

**12. EmbeddingGemma 2 in retrieval.** It was tried to update to the new version; version 1 works better (dev 39.9 vs 38.8, general 25.8 vs 23.9), so version 1 is used. On October 7 we tried EmbeddingGemma 2, the successor Google had just published (270M text parameters, 768 dimensions, 8K context). We rebuilt the index with its vectors (computed with `sentence-transformers` in a Cloud Run job, with the same sentence-similarity prefix) and measured David in the cloud with everything else unchanged:

| Split | EmbeddingGemma (the demo's) | EmbeddingGemma 2 |
| --- | ---: | ---: |
| dev (230 sentences) | **39.9** | 38.8 |
| general test (600) | **25.8** | 23.9 |
| specialty, Firefox Focus (144) | 35.3 | 37.0 |

It loses on dev and on the test set; on the specialty it gains 1.7, within how much MBR varies between runs (35.3 and 37.4 with the same index). Also, Ollama doesn't serve it on Linux yet (its Ollama builds require the MLX runtime, which the L4 doesn't have). *We learned:* a newer embedding model doesn't improve K'iche' retrieval by itself; the demo keeps EmbeddingGemma.

**13. Newer Pontoon strings.** Pontoon's public translation memory (TMX per project, MPL-2.0) has strings newer than the Hugging Face copy the dataset uses. Joined with the Spanish one through the English string, and dropping any that are in a split or in the index, 167 pairs remain: 105 from Firefox Focus, 57 from Mozilla Monitor, 3 from Mozilla accounts and 2 from Firefox Send ([`evals/tm_new.py`](evals/tm_new.py)). On Firefox Focus David wins +6.1 [+3.0, +9.2]; on Mozilla Monitor he loses −10.7 [−20.2, −0.5]. *We learned:* the translation memory helps when the new product looks like what was already translated (short UI strings); a marketing website doesn't. 15 of the page's 26 examples come from these sentences.

### David on the Cloud Run GPU

The page runs on Cloud Run and David on another Cloud Run service with an NVIDIA L4 (`europe-west4`, 4 vCPU, 16 GiB), with the model, EmbeddingGemma, the index and its already-compiled GPU kernels inside the image. Measured on October 7 with [`david/bench.py`](david/bench.py) ([results](david/bench-results.json)): the 26 examples, 3 times each, against a copy of David's service nobody else was using, so no other measurement slowed it down; Goliath through the page.

| | David (L4) | Goliath (Vertex AI) |
| --- | ---: | ---: |
| Time, median of 78 translations | **0.81 s** | 1.47 s |
| Time, p95 | **1.43 s** | 3.09 s |
| Translations where David answered first | **74 of 78** | — |
| Cost of one translation, as the page shows it | $0.00027 (0.9 s of GPU × $0.0002907/s) | **$0.00012** (107 tokens, 2026 price) |
| Start from zero (GPU off) | **39 s** (was 3 min 24 s) | — |

One person using the page: David almost always answers first, and each translation costs him more than Gemini at the 2026 price. At the 2027 price (double), Gemini would charge $0.00024 for the same sentence and David would stay at $0.00027. Where the math flips: [Projections](#projections-cost-and-time).

#### Cold start

David turns himself off about 15 minutes after the last request (minimum 0 instances: with the page closed he costs nothing). When waking up, most of the time went into something other than loading the model: Ollama's CUDA libraries compile part of their code for the L4 the first time they run ("JIT" compilation), and on a new instance that happened every time. Measured in Cloud Run's logs, from the instance starting to «David listo»:

| Phase | Before | After |
| --- | ---: | ---: |
| Start the container | 4 s | 5 s |
| Ollama finds the GPU | 15 s | 14 s |
| Load the model on the GPU | 66 s | 12 s |
| Load EmbeddingGemma | 26 s | 2 s |
| First full translation (retrieval + MBR-4) | 69 s | 2 s |
| **Total** | **3 min 1 s** | **35 s** |

What changed (in [`infra/20-david.sh`](infra/20-david.sh)):

- **The kernels are compiled once.** After building the image, a Cloud Run Job with an L4 runs it ([`david/warm_cache.py`](david/warm_cache.py)): it loads both models and translates short and long sentences in both directions, the page's examples and batches of 2, 4 and 8 at once. CUDA keeps what it compiles (122 MB) and the final image carries it ([`david/Dockerfile.cache`](david/Dockerfile.cache)). Tested in a job: with the cache, loading the model went from 66 s to 8 s, EmbeddingGemma from 35 s to 2 s and the first translation from 62 s to 1 s; with the cache disabled and everything else the same, back to 62, 39 and 60 s. If Cloud Run changes its GPU driver version, CUDA ignores the cache and compiles again: slower, never wrong; `make deploy-david` regenerates it.
- **The image lives next to the service.** It was in Artifact Registry in `us-central1` while the service runs in `europe-west4`; now both demo images are in `europe-west4`.
- **The first long sentences used to be slow too** (4 to 10 s) because they compiled kernels of other sizes. With the cache, the first minute after waking up has a p95 of 1.2 s.
- **What didn't help:** turning off Ollama's search for Vulkan GPUs (finding the GPU still took about 14 s; it stays off because David only uses CUDA) and 8 vCPU and 32 GiB instead of 4 and 16 (same time per translation, 36 % more per hour).

### Cost of training David

| Runs | Jobs | Job duration | L4 cost |
| --- | ---: | ---: | ---: |
| `tzij-2026-09` | 1 | 30 min | $0.70 |
| `raft-s0`, `raft-bt-s0` … `s3` | 5 | 130 min | $3.09 |
| `n2a`, `n2b` (synthetic A/B) | 4 | 103 min | $2.44 |
| `tm-a`, `tm-a-e2`, `tm-b` (epochs) | 10 | 260 min | $6.16 |
| `bl`, `dst`, `mix` (data round) | 17 | 360 min | $8.52 |

Gemini as teacher: $0.12 (first back-translation) + $2.09 (synthetic, discarded) + $13.94 (data round) + $1.85 (Gemini Pro measurement). Every run is in [`train/runs/`](train/runs/), with machine, duration and cost per stage.

## Projections: cost and time

With the numbers measured above ([`david/bench-results.json`](david/bench-results.json)), what happens with more use. Cloud Run prices in `europe-west4` (Cloud Billing catalog, October 7, 2026): L4 without zonal redundancy $0.0001867/s, vCPU $0.000018/s, GiB $0.000002/s. Gemini 3.8 Flash: $0.75 / $3.75 per million input / output tokens until December 31, 2026, and $1.50 / $7.50 from January 1, 2027.

**The formulas.**

- David's hour = $0.0001867 + 4 × $0.000018 + 16 × $0.000002 = $0.0002907 per second = **$1.0465 per hour** while up, translating or not.
- Goliath's translation = input tokens × input price + output tokens × output price: **$0.000122** in 2026 and **$0.000243** in 2027 (average over the 26 examples: 107 tokens).
- David's translation = $1.0465 ÷ translations per hour. How many one L4 can do was measured by sending it several sentences at once:

| Sentences at once | Translations per hour | Median | p95 |
| ---: | ---: | ---: | ---: |
| 1 | 3,970 | 0.87 s | 1.17 s |
| 2 | 4,951 | 1.34 s | 2.08 s |
| 4 | **5,548** | 2.29 s | 4.14 s |
| 8 | 5,338 | 4.87 s | 6.36 s |

  With 4 at once the L4 reaches its maximum: about **5,500 translations per hour**, at **$0.000189** each. With a single person using it, $0.00027.

**Cost: who wins where.** David costs the same per hour with 1 or 5,500 translations; Goliath, the same per translation. The break-even point is $1.0465 ÷ the cost of one Goliath translation:

| | Gemini 2026 price | Gemini 2027 price |
| --- | ---: | ---: |
| Break-even, translations per hour | 8,600 (more than one L4 can do) | **4,300** |
| David cheaper | never, with one L4 on Cloud Run | **above 4,300 translations per hour** |
| At full load (5,500 per hour) | David $0.000189, Goliath **$0.000122** | **David $0.000189**, Goliath $0.000243 (David 22 % cheaper) |

Per month, with David always on (730 hours, $764):

| Translations per month | Goliath 2026 | Goliath 2027 | David (1 L4) |
| ---: | ---: | ---: | ---: |
| 100,000 | **$12** | **$24** | $764 |
| 1,000,000 | **$122** | **$243** | $764 |
| 3,140,000 (2027 break-even) | **$382** | $764 | $764 |
| 4,050,000 (one L4 at full load) | **$493** | $986 | **$764** |

And for a talk: the page open for an hour plus the 15 minutes David takes to turn off cost $1.31 of GPU; 200 Gemini translations, $0.02.

**What this says.**

- **With little use, Goliath is cheaper,** by far: you pay only for what you translate. A GPU on for one person is expensive.
- **With heavy use and the 2027 price, David is cheaper:** from about 4,300 translations per hour (3.1 million per month with the GPU always on), and 22 % cheaper at full load. At the 2026 price, a single L4 on Cloud Run doesn't get there.
- **Outside this math:** on owned hardware (the laptop where the experiments ran, or a GPU already paid for) each David translation costs $0 extra; and a dedicated L4 machine or a committed-use discount costs less per hour than Cloud Run, which lowers the break-even. Not measured here.

**Time: who wins where.**

- **One person at a time (the demo): David,** 0.81 s against 1.47 s median and 1.43 s against 3.09 s at p95; he answered first in 74 of 78.
- **Up to 2 sentences at once:** David barely ahead on the median (1.34 s against 1.47 s) and better at p95 (2.08 s against 3.09 s).
- **4 or more at once:** Goliath wins. One L4 splits its capacity and David goes up to 2.3 s median with 4 and 4.9 s with 8; Gemini scales on its own. For more traffic, more David instances (`--max-instances`), each with its cost per hour.
- **Waking up:** if David was off, the first sentence waits for the cold start (35 s from the instance starting); Gemini doesn't have that cost.

## Why the demo uses only the final model

The page shows a single David: `tzij-2026-10-mix-s7` + hybrid retrieval + MBR-4. The other variants are measured above but don't appear in the demo, for these reasons:

- **It's the best on both measures.** 25.7 on the general test, vs 21.5 for the previous David and 20.7 for the best base, and 37.4 on the specialty, vs 30.2 for the base with the same index.
- **It's the only one that can play the specialty cleanly.** The earlier fine-tunes (`tzij-2026-09`, `raft-s0`, `raft-bt-s0` … `s3`) trained on Firefox Focus before it was held out; with them the examples would measure memory, not translation.
- **MBR-4 is worth it.** Without MBR, `mix-s7` scores 25.1 (35.9 on the specialty); with MBR-4, 25.7 (37.4). On the laptop it took 4.14 s; on the Cloud Run L4 the page gets it in 0.9 s (median). Experiment 8's multi-prompt MBR scored higher on dev but took 7.1 s on the laptop.
- **The demo shows the case David wins.** On the translation memory, David translates better than Goliath; that is what the page compares. In general translation Goliath stays ahead (36.9 vs 25.7), most clearly in K'iche' → Spanish (−16.4). Those numbers are above and in the [logbook](docs/BITACORA.md), but the talk doesn't show that direction or those sentences.
- **A per-sentence comparison has to be fair to both.** Buttons only come from use cases David wins as a set, never from single wins inside a losing use case. Each was translated 3 times live by both models, and stays only if all 3 times David scores 50 or more and beats Goliath by 15 or more. Of Firefox Focus, 37 were tried and 26 passed; the page shows 6, the easiest for anyone to understand. Of the dictionaries, 27 words were tried and 15 passed. The measured outputs and scores are in [`duel/examples.json`](duel/examples.json).
- **Retrieval stays with EmbeddingGemma 1.** EmbeddingGemma 2 was tried to update to the new version; version 1 works better (dev 39.9 vs 38.8, general 25.8 vs 23.9), so version 1 is used ([experiment 12](#what-each-experiment-told-us)).

## Quickstart

```bash
cp .env.example .env                       # models, buckets and regions; .env is never committed
uv sync
gcloud auth login && gcloud auth application-default login
make deploy                                # project, jobs, David on his GPU and the page
open "$(make -s page-url)"                 # David and Goliath side by side
make test                                  # tests with mock models (MOCK_AI=1): no GPU, no cloud
```

**Reproducing it in your project.** Models, datasets and the index live in this project's private buckets (`gs://ai-experiments-487722-tzij-*`): they're not published, because some sources only allow private redistribution (BOUQuET) and the models derive from all of them. Everything rebuilds from the licensed sources: in `.env`, set `GOOGLE_CLOUD_PROJECT`, `DATA_BUCKET_URI`, `MODELS_BUCKET` and `STAGING_BUCKET` to your project and buckets, create the `hf-token` secret with a Hugging Face token that accepted Gemma's terms (and BOUQuET's, for the full test set) and run `make deploy`: it builds the datasets (`make data-cloud`), the index, training on Cloud Run Jobs (`make train`, `make train-finish`), David and the page. You need Cloud Run L4 GPU quota in `DEMO_REGION`. Reference costs in [Cost of training David](#cost-of-training-david). Step by step in [docs/ONBOARDING.md](docs/ONBOARDING.md) (Spanish).

**Licenses.** The code is Apache 2.0 ([`LICENSE`](LICENSE)); data and models keep their licenses, listed in [`THIRD_PARTY.md`](THIRD_PARTY.md).

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
