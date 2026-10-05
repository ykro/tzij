# Niche results — a translation memory Goliath doesn't have

Run `niche`, dataset `20261002-173447`: 144 held-out es→quc pairs of the Pontoon product `focus-for-android` (Firefox Focus). Definition and protocol pre-registered in [`evals/niche.md`](niche.md). Goliath = `gemini-3.8-flash`. Paired bootstrap, 2,000 resamples, seed 2027.

## chrF++ (primary)

| slice | n | David chrF++ | Goliath chrF++ | David − Goliath [95% CI] | David wins [95% CI] | ties | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4:e4b+hybrid+mbr4` | 144 | 30.2 | 28.9 | **+1.3** [-2.3, +5.3] | 49% [42, 58] | 4 | empate |
| `tzij-2026-10-tm-a-e2-s4+hybrid` | 144 | 35.2 | 28.9 | **+6.4** [+2.2, +11.2] | 59% [51, 67] | 2 | David |
| `tzij-2026-10-tm-a-e2-s4+hybrid+mbr4` | 144 | 36.4 | 28.9 | **+7.5** [+3.8, +11.7] | 60% [53, 69] | 2 | David |

## Term exact-match accuracy (secondary)

| David variant | pairs with terms | terms | David | Goliath | David − Goliath [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gemma4:e4b+hybrid+mbr4` | 37 | 41 | 78% | 46% | **+32** [+13, +51] |
| `tzij-2026-10-tm-a-e2-s4+hybrid` | 37 | 41 | 61% | 46% | **+15** [-3, +33] |
| `tzij-2026-10-tm-a-e2-s4+hybrid+mbr4` | 37 | 41 | 63% | 46% | **+17** [-0, +37] |
