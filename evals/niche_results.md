# Niche results — a translation memory Goliath doesn't have

Run `niche`, dataset `20261002-173447`: 144 held-out es→quc pairs of the Pontoon product `focus-for-android` (Firefox Focus). Definition and protocol pre-registered in [`evals/niche.md`](niche.md). Goliath = `gemini-3.8-flash`. Paired bootstrap, 2,000 resamples, seed 2027.

## chrF++ (primary)

| slice | n | David chrF++ | Goliath chrF++ | David − Goliath [95% CI] | David wins [95% CI] | ties | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `gemma4:e4b+hybrid+mbr4` | 144 | 30.2 | 28.9 | **+1.3** [-2.3, +5.3] | 49% [42, 58] | 4 | empate |
| `tzij-2026-10-mix-s7+hybrid` | 144 | 35.9 | 28.9 | **+7.0** [+2.9, +11.1] | 56% [49, 64] | 3 | David |
| `tzij-2026-10-mix-s7+hybrid+mbr4` | 144 | 37.4 | 28.9 | **+8.5** [+4.7, +12.7] | 57% [49, 65] | 2 | David |

## Term exact-match accuracy (secondary)

| David variant | pairs with terms | terms | David | Goliath | David − Goliath [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gemma4:e4b+hybrid+mbr4` | 37 | 41 | 78% | 46% | **+32** [+13, +51] |
| `tzij-2026-10-mix-s7+hybrid` | 37 | 41 | 59% | 46% | **+12** [-7, +32] |
| `tzij-2026-10-mix-s7+hybrid+mbr4` | 37 | 41 | 61% | 46% | **+15** [-2, +32] |
