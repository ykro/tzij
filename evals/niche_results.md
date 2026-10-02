# Niche results — a translation memory Goliath doesn't have

Run `niche`, dataset `20261002-173447`: 144 held-out es→quc pairs of the Pontoon product `focus-for-android` (Firefox Focus). Definition and protocol pre-registered in [`evals/niche.md`](niche.md). Goliath = `gemini-3.8-flash`. Paired bootstrap, 2,000 resamples, seed 2027.

## chrF++ (primary)

| slice | n | David chrF++ | Goliath chrF++ | David − Goliath [95% CI] | David wins [95% CI] | ties | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4:e4b+hybrid+mbr4` | 144 | 30.2 | 28.9 | **+1.3** [-2.3, +5.3] | 49% [42, 58] | 4 | empate |
| `gemma4:e4b+hybrid+mbr4@pre-registered-index` | 144 | 29.7 | 28.9 | **+0.9** [-2.8, +4.6] | 51% [42, 59] | 4 | empate |

## Term exact-match accuracy (secondary)

| David variant | pairs with terms | terms | David | Goliath | David − Goliath [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gemma4:e4b+hybrid+mbr4` | 37 | 41 | 78% | 46% | **+32** [+13, +51] |
| `gemma4:e4b+hybrid+mbr4@pre-registered-index` | 37 | 41 | 83% | 46% | **+37** [+17, +56] |
