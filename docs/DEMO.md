# Guion de la demo — Tzij en el escenario

Una sola página: el traductor de David. David es Gemma 4 E4B ajustado (`tzij-2026-10-mix-s7`), con
su índice de recuperación y su memoria de traducción, y corre en la laptop sin internet. Se escribe
una frase en español (o se toca un ejemplo), se pulsa **Traducir** y aparece la traducción al
Kʼicheʼ.

Duración: unos 3 minutos. [English version](DEMO.en.md)

![El traductor con un ejemplo traducido](demo/traductor-2-ejemplo.png)

## Antes de la charla

1. **Una vez, con internet**, si la laptop no tiene ya los datos y el modelo:

   ```bash
   make data-pull && make niche-data
   make pull-model TAG=tzij-2026-10-mix-s7
   ```

2. **Levantar Tzij.** En una terminal:

   ```bash
   make up
   ```

3. **Precalentar y revisar.** En otra terminal:

   ```bash
   make stage-on && make warmup && make preflight
   ```

   `warmup` carga a David y su índice para que la primera traducción no salga en frío.
   `preflight` revisa el modelo, el índice, la página y las frases de ejemplo: traduce una en vivo y
   la compara con su traducción de referencia. Tiene que terminar en «preflight ok»; cada `[FALLA]`
   dice cómo arreglarlo.

4. **Abrir la página** en Chrome, en pantalla completa (`⌃⌘F`):

   ```
   http://127.0.0.1:8787/traductor/
   ```

5. **Notificaciones y salvapantallas apagados:** «No molestar» y `caffeinate -d &`.

Después de la charla: `make stage-off` (en Tzij solo lo confirma: no hay nada en la nube).

## En el escenario

### 1. La página (30 s)

![El traductor listo](demo/traductor-1-lista.png)

- **Qué se ve:** el cuadro para escribir, el cuadro de la traducción y los ejemplos debajo.
- **Qué decir:** "Este es David: un modelo pequeño que corre en esta laptop, sin internet. Traduce
  del español al Kʼicheʼ, el idioma maya más hablado de Guatemala."

### 2. Un ejemplo (1 min)

![Un ejemplo traducido](demo/traductor-2-ejemplo.png)

- **Qué hacer:** toca **Conexión segura**, y después **Bloquear cookies entre sitios**. Cada
  traducción tarda 2 o 3 segundos.
- **Qué decir:** "Son frases de Firefox Focus, el navegador de Mozilla. Su traducción al Kʼicheʼ
  la hicieron personas, y David nunca la vio al entrenar. Lo que sí tiene es la memoria de
  traducción de los demás productos de Mozilla: las palabras que esa comunidad ya decidió. Con esa
  memoria, David traduce mejor que Gemini en estas frases."

### 3. Una frase escrita (1 min)

![Una frase escrita y traducida](demo/traductor-3-escrita.png)

- **Qué hacer:** escribe una frase corta del mismo tipo, texto de una aplicación o de un navegador,
  por ejemplo `+ Agregar otro motor de búsqueda`, y pulsa **Traducir** (o `Enter`).
- **Qué decir:** "No hace falta que sea un ejemplo: escribo lo que quiera y David traduce aquí
  mismo, gratis y sin mandar el texto a ninguna parte."

### 4. Sin internet (30 s)

- **Qué hacer:** apaga el Wi-Fi de la laptop y toca otro ejemplo, por ejemplo **Conexión insegura**.
- **Qué decir:** "Sin red, David sigue igual: el modelo, la memoria de traducción y el índice
  viven en esta laptop. Cada traducción cuesta cero."
- Vuelve a encender el Wi-Fi al terminar.

## Los números de la charla

Solo los casos que David gana:

| | David (laptop) | Gemini 3.8 Flash (nube) |
| --- | ---: | ---: |
| Memoria de traducción: Firefox Focus, 144 frases (chrF++) | **37.4** | 28.9 |
| Costo por 1,000 traducciones | **$0** | $0.29 |
| Sin internet | **traduce igual** | no traduce |

La traducción general (el conjunto de prueba completo, en las dos direcciones) no es parte de la
charla porque ahí gana Gemini. Está documentada con sus números en
[DECISIONES.md](DECISIONES.md#resultados) y [BITACORA.md](BITACORA.md). Por la misma razón, la
página también traduce del Kʼicheʼ al español (con el botón ⇄), pero esa dirección no se muestra
en la charla.

## Las frases de ejemplo

Están en [`duel/examples.json`](../duel/examples.json), con su traducción de referencia, su fuente
(Mozilla Pontoon, Firefox Focus) y su licencia (MPL-2.0). Cada una se tradujo en vivo con David 3
veces, y todas las traducciones quedaron cerca de la referencia (chrF++ de 50 o más). Para volver a
revisarlas, por ejemplo después de cambiar de David:

```bash
make examples
```

## Si algo falla

| Qué pasa | Qué hacer |
| --- | --- |
| La página no abre | `make up` en una terminal y recarga. |
| Dice «David no pudo traducir» | `ollama list`; si falta el modelo, `make pull-model TAG=tzij-2026-10-mix-s7`, y después `make up`. |
| La primera traducción tarda más de 10 s | Estaba en frío: espera, la siguiente sale rápido. La próxima vez corre `make warmup` antes. |
| No aparecen los ejemplos | `make preflight` dice qué falta (`make examples` o `make web`). |
| Todo falla | Ensayo sin modelos: `make up MOCK_AI=1` (David responde con ejemplos de los datos con licencia). |
