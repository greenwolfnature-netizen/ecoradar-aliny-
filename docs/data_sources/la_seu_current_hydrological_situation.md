# Situació hidrològica actual — metodologia EcoRadar

Data metodològica: 2026-07-25

## Finalitat

La lectura combina observacions, previsió i sensibilitat territorial per oferir
un cribratge contextual. No declara que hi hagi una inundació i no substitueix
els avisos de CHE, ACA, Meteocat, Protecció Civil o els serveis d'emergència.

## Entrades

- cabal i nivell provisionals CHE/SAIH de les estacions A022 (Valira) i A023
  (Segre), cada quinze minuts;
- direcció recent calculada sobre la minigràfica pública CHE, sense assignar
  dates als valors individuals perquè la font no les publica;
- precipitació de les darreres 24 hores a l'estació XEMA CD;
- precipitació municipal prevista per Meteocat a 24 i 48 hores;
- presència de zones inundables Q100 del SNCZI;
- escorrentia potencial EcoRadar basada en impermeabilització Copernicus HRL i
  pendent LiDAR ICGC.

Els cabals i nivells absoluts es mostren, però no es transformen en alarma
perquè el servei actual inspeccionat no publica llindars oficials específics de
les dues estacions.

## Índex i regles de seguretat

| Component | Pes |
|---|---:|
| Precipitació observada 24 h | 25 % |
| Precipitació prevista 24 h | 25 % |
| Tendència recent dels cabals | 25 % |
| Tendència recent dels nivells | 10 % |
| Sensibilitat estructural d'escorrentia i Q100 | 15 % |

La pluja s'escala de manera lineal entre 0 i 60 mm només com a llindar operatiu
EcoRadar de cribratge, no com a llindar oficial. Els components disponibles es
renormalitzen i la confiança disminueix quan en falta algun.

- **normal:** índex inferior a 25;
- **vigilància:** 25–49,9;
- **elevada:** 50–74,9 i corroboració mínima de 20 mm observats o 30 mm
  previstos en 24 h;
- **molt elevada:** índex igual o superior a 75 i corroboració mínima de 40 mm
  observats o 60 mm previstos en 24 h.

Sense aquesta corroboració, una puntuació elevada causada per tendència, nivell,
cabal o sensibilitat territorial queda limitada a **vigilància**. Per tant, el
cabal sol no pot produir una afirmació d'inundació actual.

## Limitacions

Les dades CHE són provisionals. La minigràfica pública no inclou timestamps
individuals. La previsió Meteocat és municipal. El proxy d'escorrentia no inclou
sòl, clavegueram, drenatge ni una pluja de projecte, i el Q100 és una delimitació
estructural. La fitxa sempre conserva les dates reals de cada font, la confiança
i aquestes limitacions.
