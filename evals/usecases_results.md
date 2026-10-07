# Casos de uso medidos como conjunto

Generado por `evals/usecases.py` contra el David de la nube (recuperación híbrida + MBR-4, como la página), Goliath (`gemini-3.8-flash` solo) y Goliath con el mismo contexto recuperado de David. Muestra fija con semilla 2027, español → Kʼicheʼ. Los términos están en el índice de David: se mide una organización con su propio glosario, no traducir texto nuevo.

| Caso de uso | n | David chrF++ | Goliath chrF++ | David − Goliath [IC 95 %] | Exacta: David | Goliath | Goliath + glosario |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Vocabulario cotidiano del diccionario GATITOS (Google Research, CC BY 4.0) | 150 | **57.5** | 22.1 | +35.4 [+28.0, +42.6] | 37 % | 9 % | 85 % |
| Nombres de emoji de Unicode CLDR (Unicode License V3) | 100 | **60.9** | 25.7 | +35.2 [+28.1, +42.5] | 42 % | 1 % | 91 % |

chrF++ de Goliath + glosario: Vocabulario cotidiano del diccionario GATITOS 88.6, Nombres de emoji de Unicode CLDR 94.4.
