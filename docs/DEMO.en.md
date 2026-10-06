# Demo script — Tzij

One page, in the cloud: you type a Spanish sentence (or tap an example) and, at the same time,
**David**, a fine-tuned Gemma 4 E4B (`tzij-2026-10-mix-s7`) with its translation memory, and
**Goliath**, Gemini 3.8 Flash, translate it into K'iche'. The two translations appear side by side.
For the examples, the page also shows the correct translation, made by people, and how close each
one got to it.

Length: about 3 minutes. [Versión en español](DEMO.md). *The UI is in Spanish; the lines to say
are given in Spanish, as in the talk.*

![David and Goliath translate an example](demo/pagina-3-ejemplo.png)

## Before the talk

Nothing to run. About 5 minutes before, open in Chrome, full screen (`⌃⌘F`):

```
https://tzij-611681112050.europe-west4.run.app
```

(`make page-url` prints it.) The page wakes David up: his cloud GPU turns itself off when nobody
uses it. While it starts, the top right says «Preparando a David…» and the buttons wait; it takes
about 3 minutes. When it says **«David listo»**, it's ready. While the page stays open, David stays
awake.

![The page while David starts](demo/pagina-0-preparando.png)

## On stage

### 1. The page (30 s)

![The page, ready](demo/pagina-1-lista.png)

- **What you see:** the text box, the example sentences and the two columns: David, a small model,
  and Goliath, a frontier model.
- **What to say:** "A la izquierda, David: un modelo pequeño, ajustado con datos Kʼicheʼ con
  licencia. A la derecha, Goliath: Gemini. Los dos van a traducir lo mismo, del español al
  Kʼicheʼ, el idioma maya más hablado de Guatemala."

### 2. Two examples (1 min 30 s)

![Both columns while translating](demo/pagina-2-traduciendo.png)

![A translated example](demo/pagina-3-ejemplo.png)

- **What to do:** tap **Conexión segura**. Each column fills when its model answers. Then tap
  **Información de licencia**.
- **What you see:** on top, the correct translation. In each column, the translation and how close
  it is to the correct one: for «Conexión segura», David 100 % and Goliath 12–16 %; for
  «Información de licencia», David about 70 % and Goliath 9–17 %.
- **What to say:** "Son frases de Firefox Focus, el navegador de Mozilla. La traducción correcta la
  hicieron personas, y ninguno de los dos la vio. David tiene la memoria de traducción de los demás
  productos de Mozilla: las palabras que esa comunidad ya decidió. Por eso se acerca más."

### 3. A typed sentence (1 min)

![A typed sentence, translated](demo/pagina-4-escrita.png)

- **What to do:** type a short sentence of the same kind, app or browser text, and press
  **Traducir** (or `Enter`).
- **What you see:** the two translations, side by side. A typed sentence has no correct
  translation to compare with.
- **What to say:** "No hace falta que sea un ejemplo: escribo lo que quiera y los dos lo traducen."

## The talk's numbers

| | David | Gemini 3.8 Flash |
| --- | ---: | ---: |
| Translation memory: Firefox Focus, 144 sentences David never saw (chrF++) | **37.4** | 28.9 |

+8.5 points, 95 % confidence interval +4.7 to +12.7 ([`evals/niche_results.md`](../evals/niche_results.md)).

General translation (the full test set, both directions) is not part of the talk, because Gemini
wins there (36.9 vs 25.7). It's in the [README](../README.en.md#experiments), with every
experiment, and in [BITACORA.md](BITACORA.md) (Spanish). For the same reason the page also
translates K'iche' into Spanish (the ⇄ button), but the talk doesn't show that direction.

## The example sentences

They live in [`duel/examples.json`](../duel/examples.json), with their correct translation, source
(Mozilla Pontoon, Firefox Focus), license (MPL-2.0) and the measured translations and scores. Each
one was translated 3 times by the cloud David and by Goliath, as the page does; only those where
every time David came close to the correct one (chrF++ ≥ 50) and at least 15 points closer than
Goliath stayed. There are 11. To re-check them, e.g. after changing the model: `make examples`.

## If something fails

| What happens | What to do |
| --- | --- |
| Still «Preparando a David…» after 5 minutes | Reload the page. After 6 minutes the page says «David no responde: recarga la página». |
| A column says «No pudo traducir esta frase» | Tap the example again. |
| A column says «No hay conexión con la página» | The venue's internet dropped: wait for it and reload. |
