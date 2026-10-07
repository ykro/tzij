# Newer Pontoon strings — more phrases of the translation-memory use case

Run `tm-new`: 167 español → Kʼicheʼ pairs from Pontoon's live translation memory that are in no split of the dataset nor in David's index ([`evals/tm_new.py`](tm_new.py)). Firefox Focus is the held-out product of the niche; for the other products David has their older strings as translation memory. David = `tzij-2026-10-mix-s7+hybrid+mbr4`, Goliath = `gemini-3.8-flash`. Paired bootstrap, 2,000 resamples, seed 2027. Not pre-registered (added on 2026-10-07, after the niche results).

| slice | n | David chrF++ | Goliath chrF++ | David − Goliath [95% CI] | David wins [95% CI] | ties | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| all | 167 | 32.0 | 31.2 | **+0.8** [-3.6, +4.9] | 51% [44, 59] | 5 | empate |
| Firefox Focus | 105 | 36.5 | 30.4 | **+6.1** [+3.0, +9.2] | 64% [54, 73] | 1 | David |
| Mozilla Monitor | 57 | 22.0 | 32.6 | **-10.7** [-20.2, -0.5] | 30% [19, 42] | 2 | Goliath |

Products with fewer than 10 pairs count only in «all»: Firefox Send (2), Mozilla accounts (3).
