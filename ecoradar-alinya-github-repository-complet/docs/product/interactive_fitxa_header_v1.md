# Capçalera oficial de les fitxes interactives EcoRadar v1

Estat: `frozen`

Referència visual validada: EcoRadar Muntanya d'Alinyà, 24/07/2026.

## Estructura obligatòria

1. Bloc superior a amplada completa, immediatament abans de la navegació o del
   contingut interactiu.
2. Títol EcoRadar i nom de l'àmbit a l'esquerra.
3. Títol funcional i descripció breu al centre.
4. Logotips EcoRadar i Green Wolf Nature i distintiu de traçabilitat a la
   dreta.
5. Fons clar amb paleta EcoRadar i motiu radar discret construït amb gradients
   CSS, sense convertir-lo en una dada o una capa cartogràfica.

## Criteris de reutilització

- Es manté la mateixa jerarquia, espaiat, fons radar, mides de logotips i
  comportament responsiu.
- Només canvien el tipus d'EcoRadar, el nom de l'àmbit, el subtítol funcional i
  la descripció pròpia del projecte.
- La capçalera no modifica dades, mapes, lectures, càlculs ni funcionalitats.
- Els logotips s'incorporen des dels actius oficials del projecte i han de
  conservar text alternatiu.
- Alinyà i la Seu d'Urgell són les dues implementacions de referència.

## Implementacions

- `tools/export_ecoradar_alinya_netlify.py`
- `tools/render_la_seu_urban_map.py`

