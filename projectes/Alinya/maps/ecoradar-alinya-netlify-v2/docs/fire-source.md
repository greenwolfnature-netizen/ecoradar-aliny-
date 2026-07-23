# Font d'incendis forestals

El visor no utilitza IncendisCat com a font de dades.

La geometria local incorporada prove de les capes ja processades al projecte:
`projectes/Alinya/maps/incendis/incendis_historics_alinya_clip.geojson`.

La propietat `font` dels elements indica:
`Generalitat de Catalunya WFS VEGETACIO:VEGETACIO_INCENDIS`.

Estat: font oficial documentada localment al projecte. L'index integrat combina
el mapa estructural oficial 2024 amb LST estival Landsat, NDMI, tipus de coberta
i concurrencia territorial. El risc operatiu requereix meteorologia diaria,
Pla Alfa i combustible i humitat fina validats.

## Actualitzacio de concurrencia

La capa `Concurrencia` es calcula dins l'ambit d'Alinya amb els perimetres
historics oficials com a base de comparacio:

1. Manté la similitud ambiental base ja processada per EcoRadar: coberta,
   habitat, pendent, orientacio, altitud i accessibilitat.
2. Utilitza nomes els dos perimetres historics oficials dins l'ambit com a base
   de comparacio.
3. No incorpora registres recents sense perimetre, FIRMS ni geometries externes.
4. No converteix aquest resultat en probabilitat oficial ni en risc diari.
