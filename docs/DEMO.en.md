# Demo script — Tzij on stage

One page: the translator. You type a Spanish sentence (or tap an example) and, at the same time, it
is translated into K'iche' by **David**, a fine-tuned Gemma 4 E4B (`tzij-2026-10-mix-s7`) with its
translation memory, running on this laptop without internet, and by **Goliath**, Gemini 3.8 Flash
in the cloud. The two translations appear side by side, each with its time and cost. For the
examples, the page also shows the correct translation, the one people made, and how close each one
got to it.

Length: about 4 minutes. [Versión en español](DEMO.md)

![David and Goliath translate an example](demo/traductor-3-ejemplo.png)

## Before the talk

1. **Once, with internet**, if the laptop doesn't have the data and the model yet:

   ```bash
   make data-pull && make niche-data
   make pull-model TAG=tzij-2026-10-mix-s7
   ```

2. **Start Tzij.** In one terminal:

   ```bash
   make up
   ```

3. **Warm up and check.** In another terminal:

   ```bash
   make stage-on && make warmup && make preflight
   ```

   `warmup` loads David and its index and makes one Gemini call, so the first translation isn't
   cold. `preflight` checks the model, the index, the page and the examples: it translates one
   live with both and checks that David stays close to the correct translation and clearly closer
   than Goliath. It must end in "preflight ok"; each `[FALLA]` says how to fix it. Without
   internet, the Gemini checks show as `[aviso]` (notice), not as failures.

4. **Open the page** in Chrome, full screen (`⌃⌘F`):

   ```
   http://127.0.0.1:8787/traductor/
   ```

5. **Notifications and screen saver off:** "Do Not Disturb" and `caffeinate -d &`.

After the talk: `make stage-off` (in Tzij it only confirms there is nothing in the cloud to scale down).

## On stage

### 1. The page (30 s)

![The translator, ready](demo/traductor-1-lista.png)

- **On screen:** the box to type in, the example sentences and, below, the two columns: David
  (on this laptop) and Goliath (in the cloud).
- **Say:** "On the left, David: a small model running on this laptop. On the right, Goliath:
  Gemini, in the cloud. Both will translate the same thing, from Spanish into K'iche', the most
  widely spoken Mayan language in Guatemala."

### 2. An example (1 min 30 s)

![The two columns while they translate](demo/traductor-2-traduciendo.png)

![An example translated](demo/traductor-3-ejemplo.png)

- **Do:** tap **Conexión segura**. Each column fills when its model answers, in 1 to 3 seconds.
  Then tap **Bloquear cookies entre sitios**.
- **On screen:** at the top, the correct translation. In each column, the translation, how close
  it is to the correct one (for example, David 100% and Goliath 22%), the time and the cost:
  "Gratis" (free) for David and a hundredth of a cent or so for Goliath.
- **Say:** "These are sentences from Firefox Focus, Mozilla's browser. People made the correct
  translation, and neither model saw it. David has the translation memory of Mozilla's other
  products: the words that community already chose. That's why it gets closer. And it does it for
  free."

### 3. A typed sentence (1 min)

![A typed sentence, translated](demo/traductor-4-escrita.png)

- **Do:** type a short sentence of the same kind, text from an app or a browser, for example
  `Agregar otro motor de búsqueda`, and press **Traducir** (or `Enter`).
- **On screen:** the two translations, the time and the cost. Since it's a typed sentence, there
  is no correct translation to compare with.
- **Say:** "It doesn't have to be an example: I type whatever I want, and David translates it right
  here, without sending the text anywhere."

### 4. No internet (1 min)

![No internet: Goliath doesn't answer, David does](demo/traductor-5-sin-internet.png)

- **Do:** turn the laptop's Wi-Fi off and tap **Conexión insegura**.
- **On screen:** at the top right, "Sin internet: David sigue traduciendo" (no internet: David keeps
  translating). Goliath says "Sin conexión" and David translates as usual.
- **Say:** "Without a network, Goliath doesn't exist. David keeps going: the model, the translation
  memory and the index live on this laptop."
- Turn the Wi-Fi back on afterwards.

## The talk's numbers

| | David (laptop) | Gemini 3.8 Flash (cloud) |
| --- | ---: | ---: |
| Translation memory: Firefox Focus, 144 sentences (chrF++) | **37.4** | 28.9 |
| Cost per 1,000 translations | **$0** | $0.29 |
| No internet | **still translates** | doesn't translate |

General translation (the full test set, both directions) is not part of the talk, because Gemini
wins it (36.9 vs 25.7). It's in the [README](../README.en.md#experiments), with every experiment,
and in [BITACORA.md](BITACORA.md) (Spanish). For the same reason, the page also translates K'iche'
into Spanish (with the ⇄ button), but that direction is not shown in the talk.

## The example sentences

They live in [`duel/examples.json`](../duel/examples.json), with their correct translation, source
(Mozilla Pontoon, Firefox Focus), license (MPL-2.0) and the measured translations and scores. Each
was translated live 3 times by David and by Goliath; only the ones where, all 3 times, David stayed
close to the correct translation (chrF++ 50 or more) and at least 15 points closer than Goliath
were kept. To check them again, for example after changing a model:

```bash
make examples
```

## If something fails

| What happens | What to do |
| --- | --- |
| The page doesn't open | `make up` in a terminal and reload. |
| A column says "No hay conexión con el servicio de Tzij" | The service went down: `make up` and tap the example again. |
| David says "No pudo traducir esta frase" | `ollama list`; if the model is missing, `make pull-model TAG=tzij-2026-10-mix-s7` and `make up`. |
| Goliath says "Sin conexión" with Wi-Fi on | The venue's network blocks Vertex AI: use it as the no-internet moment. |
| David's first translation takes more than 10 s | It was cold: wait, the next one is fast. Next time run `make warmup` first. |
| The examples don't show | `make preflight` says what's missing (`make examples` or `make web`). |
| Everything fails | Rehearsal without models: `make up MOCK_AI=1` (both answer with examples from the licensed data). |
