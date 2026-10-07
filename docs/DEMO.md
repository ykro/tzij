# Guion de la demo — Tzij

Una sola página, en la nube: se escribe una frase en español (o se toca un ejemplo) y, al mismo
tiempo, la traducen al Kʼicheʼ **David**, Gemma 4 E4B ajustado (`tzij-2026-10-mix-s7`) con su
memoria de traducción, y **Goliath**, Gemini 3.8 Flash. Las dos traducciones salen lado a lado,
cada una con lo que tardó y lo que costó. En los ejemplos, la página muestra también la traducción
correcta, la que hicieron personas, y qué tanto se parece a ella cada una.

Duración: unos 3 minutos. [English version](DEMO.en.md)

![David y Goliath traducen un ejemplo](demo/pagina-3-ejemplo.png)

## Antes de la charla

No hay que correr nada. Unos 5 minutos antes, abre en Chrome, en pantalla completa (`⌃⌘F`):

```
https://tzij-611681112050.europe-west4.run.app
```

(`make page-url` la imprime.) La página despierta a David: su GPU en la nube se apaga sola cuando
nadie la usa. Mientras arranca, arriba a la derecha dice «Preparando a David…» y los botones
esperan; tarda unos 40 s (39 s medido con la GPU apagada; antes, 3 min 24 s). Cuando dice **«David listo»**, ya está. Mientras la página siga abierta,
David se queda despierto.

La página también se ve bien en un teléfono: si quieres que el público la pruebe, la misma
dirección funciona ahí.

## En el escenario

### 1. La página (30 s)

![La página lista](demo/pagina-1-lista.png)

- **Qué se ve:** el cuadro para escribir, los ejemplos en tres grupos (interfaz de Firefox Focus,
  palabras de un diccionario y nombres de emoji), cada uno con su resultado en todo el conjunto y las dos columnas: David, un modelo pequeño, y Goliath, un modelo frontera.
- **Qué decir:** "A la izquierda, David: un modelo pequeño, ajustado con datos Kʼicheʼ con
  licencia. A la derecha, Goliath: Gemini. Los dos van a traducir lo mismo, del español al
  Kʼicheʼ, el idioma maya más hablado de Guatemala."

### 2. Dos ejemplos (1 min 30 s)

![Las dos columnas mientras traducen](demo/pagina-2-traduciendo.png)

![Un ejemplo traducido](demo/pagina-3-ejemplo.png)

- **Qué hacer:** toca **Conexión segura**. Cada columna se llena cuando su modelo responde. Después
  toca **gafas de sol**, de los nombres de emoji.
- **Qué se ve:** arriba, la traducción correcta. En cada columna, la traducción, qué tanto se
  parece a la correcta, cuánto tardó y cuánto costó. En «Conexión segura», David 100 % y Goliath
  entre 8 y 26 %; en «gafas de sol», David 100 % y Goliath entre 16 y 32 %.
  David suele responder en menos de un segundo; Goliath, en uno o dos.
- **Qué decir:** "Son frases de Firefox Focus, el navegador de Mozilla. La traducción correcta la
  hicieron personas, y ninguno de los dos la vio. David tiene la memoria de traducción de los demás
  productos de Mozilla: las palabras que esa comunidad ya decidió. Por eso se acerca más, y además
  responde antes. Lo mismo con un diccionario: David consulta el suyo."
- **Si preguntan qué es «se parece a la correcta»:** "Compara cada traducción con la de las
  personas en pedacitos de letras y palabras: 100 % es idéntica. Se llama chrF++." (El pie de la
  página lo explica con un ejemplo.)
- **Si preguntan por el costo:** "Goliath cobra por frase y David por hora de GPU. Con una persona
  usándolo, Gemini sale más barato por frase; con miles de frases por hora y la tarifa de Gemini de
  2027, que es el doble, sale más barato David." Números en el
  [README](../README.md#proyecciones-costo-y-tiempo).

### 3. Una frase escrita (1 min)

![Una frase escrita y traducida](demo/pagina-4-escrita.png)

- **Qué hacer:** escribe una frase corta del mismo tipo, texto de una aplicación o de un navegador
  (por ejemplo `Bloquear rastreadores de anuncios`), y pulsa **Traducir** (o `Enter`).
- **Qué se ve:** las dos traducciones, con tiempo y costo. Si la frase está en los datos con
  licencia, la página la reconoce y la mide como un ejemplo. Si no, dice que no hay contra qué
  medir y, para juzgar, muestra las 3 frases más parecidas de la memoria de traducción, traducidas
  por personas, y marca en cada columna las palabras que también usan esas traducciones.
- **Qué decir:** "No hace falta que sea un ejemplo: escribo lo que quiera y los dos lo traducen. Las
  palabras marcadas son las que la comunidad de Mozilla ya usa para cosas parecidas."

## Los números de la charla

| | David | Gemini 3.8 Flash |
| --- | ---: | ---: |
| Memoria de traducción: Firefox Focus, 144 frases que David nunca vio (chrF++, pre-registrado) | **37.4** | 28.9 |
| Lo mismo, repetido con David en la nube | **35.3** | 28.9 |
| 105 frases de Firefox Focus más nuevas que el dataset, en la nube | **36.5** | 30.4 |
| Tiempo por traducción en la página, mediana (26 ejemplos × 3) | **0.81 s** | 1.47 s |

La primera fila es la medición pre-registrada (+8.5, IC 95 % de +4.7 a +12.7,
[`evals/niche_results.md`](../evals/niche_results.md)); las otras dos la repiten con David en la
nube (+6.4 y +6.1). El tiempo: David respondió primero en 74 de 78 traducciones.

La traducción general (el conjunto de prueba completo, en las dos direcciones) no es parte de la
charla, porque ahí gana Gemini (36.9 contra 25.7). Tampoco el costo con poco uso, donde Gemini es
más barato. Los dos están en el [README](../README.md#experimentos), con todos los experimentos y
las proyecciones, y en [BITACORA.md](BITACORA.md). Por la misma razón la página también traduce
del Kʼicheʼ al español (con el botón ⇄), pero esa dirección no se muestra en la charla.

## Las frases de ejemplo

Salen solo de casos de uso que David gana como conjunto completo, no de frases sueltas: la interfaz
de Firefox Focus (6 frases, de 144 donde David saca 37.4 y Goliath 28.9), palabras cotidianas del
diccionario GATITOS (8, de 150: 57.5 contra 22.1) y nombres de emoji de Unicode CLDR (7, de 100:
60.9 contra 25.7). Están en [`duel/examples.json`](../duel/examples.json), con su traducción
correcta, su fuente, su licencia y las traducciones y puntajes medidos. Cada una se tradujo 3 veces
con el David de la nube y con Goliath; quedaron solo las que, las 3 veces, David tradujo cerca de la
correcta (chrF++ de 50 o más) y por lo menos 15 puntos más cerca que Goliath. Para volver a
revisarlas: `make examples`.


## En el teléfono

![La página en un teléfono](demo/pagina-3-ejemplo-telefono.png)

En pantallas angostas todo va en una columna, David arriba de Goliath, y los ejemplos se deslizan
de lado.

## Si algo falla

| Qué pasa | Qué hacer |
| --- | --- |
| Sigue diciendo «Preparando a David…» después de 3 minutos | Recarga la página. Si pasa de 6 minutos, la página dice «David no responde: recarga la página». |
| Una columna dice «No pudo traducir esta frase» | Vuelve a tocar el ejemplo. |
| Una columna dice «No hay conexión con la página» | El internet del lugar se cayó: espera a que vuelva y recarga. |
