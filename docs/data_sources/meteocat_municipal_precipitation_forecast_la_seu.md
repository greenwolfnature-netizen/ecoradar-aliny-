# Previsió municipal de precipitació per a la Seu d'Urgell

Data de verificació: 2026-07-25

## Font oficial

- **Nom:** Predicció municipal de Meteocat, municipi `252038`.
- **Organisme:** Servei Meteorològic de Catalunya / Generalitat de Catalunya.
- **Pàgina oficial:** <https://www.meteo.cat/prediccio/municipal/252038>.
- **Servei automatitzable:** fitxers JSON de primera part que alimenten el giny
  oficial de predicció municipal.
- **Exemple:** `https://static-m.meteo.cat/ginys/models/postProcessament/variables/prec_acum/intervals/1/prec_acum-1_1h.json`.
- **Format:** JSON; EcoRadar el normalitza a CSV.
- **Variable:** precipitació horària acumulada prevista, instant de validesa i
  instant de sortida del model.
- **Resolució:** municipal. No és una malla de carrers.
- **Credencials:** no necessàries.
- **Actualització:** operativa; EcoRadar conserva l'instant `dataSortida`
  publicat per cada resposta i la comprova en el procés diari.
- **Llicència:** el fitxer inspeccionat no declara una llicència específica.
  Es manté atribució a Meteocat i Generalitat i no se'n pressuposa cap altra.
- **Estat:** `verified`.

## Ús a EcoRadar

El connector descarrega els fitxers públics dels dies 1, 2 i 3, selecciona
únicament el municipi `252038` i retorna una taula horària. No calcula risc
hidrològic. L'Analysis Engine agrega després la precipitació prevista de les
properes 24 i 48 hores per contextualitzar la situació hidrològica.

La previsió no és una observació, no representa la distribució de pluja dins
del municipi i no substitueix avisos del Servei Meteorològic de Catalunya,
Protecció Civil, CHE o ACA.
