# Cabals en temps real del Segre i el Valira a la Seu d'Urgell

Data de verificació inicial: 2026-07-26  
Darrera reverificació operativa: 2026-07-27

## Font oficial

- **Nom de la font:** Sistema Automàtic d'Informació Hidrològica de la conca de l'Ebre (SAIH Ebro), valors actuals d'estacions d'aforament.
- **Organisme responsable:** Confederació Hidrogràfica de l'Ebre (CHE), Ministeri per a la Transició Ecològica i el Repte Demogràfic.
- **Estació del Valira:** `A022`, riu Valira a la Seu d'Urgell.
- **Estació del Segre:** `A023`, riu Segre a la Seu d'Urgell.
- **URL oficial A022:** <https://www.saihebro.com/tiempo-real/estacion-aforos-A022-valira-seu>.
- **URL oficial A023:** <https://www.saihebro.com/tiempo-real/estacion-aforos-A023-segre-seu>.
- **Servei automatitzable verificat:** `https://www.saihebro.com/api/ficha/procesarTablaValoresActuales?estacion={CODI}`.
- **Tipus de servei:** consulta HTTP pública de valors actuals; resposta JSON amb la taula de senyals de l'estació.
- **Format normalitzat per EcoRadar:** CSV tabular, una fila per estació.
- **Sistema de referència:** les fitxes oficials publiquen coordenades projectades en fus 30 i la consulta d'informació general permet obtenir latitud i longitud. EcoRadar conserva les coordenades oficials en EPSG:4326; no transforma les coordenades de fus sense una declaració explícita del datum a la resposta.
- **Variables emprades:** cabal instantani en m³/s, nivell instantani en metres, precipitació acumulada en 24 hores quan l'estació la publica, data i hora local de cada observació, codi i nom de l'estació, riu, etiqueta de senyal, direcció gràfica publicada i seqüència recent de la minigràfica pública.
- **Freqüència de la font:** transmissió cada 15 minuts.
- **Freqüència EcoRadar:** comprovació automatitzada diària i consulta en
  carregar el visor o en prémer «Actualitza dades». Es conserva sempre
  l'instant real retornat per la font, diferenciat de l'hora de consulta.
- **Credencials:** no necessàries per als valors actuals.
- **Llicència i reutilització:** el punt de servei inspeccionat no declara una llicència oberta específica. EcoRadar mostra la dada amb atribució completa a CHE/SAIH Ebro i manté aquesta limitació documental; no pressuposa una llicència que la font no publica.
- **Estat del connector:** `verified`.

## Verificació HTTP i CORS del 26/07/2026

S'han comprovat directament els dos endpoints amb una capçalera `Origin`
externa:

| Estació | Codi HTTP | Format | CORS | Darrera dada comprovada |
| --- | --- | --- | --- | --- |
| A022, Valira | `200 OK` | `application/json; charset=utf-8` | `Access-Control-Allow-Origin: *` | 27/07/2026 17:45 CEST · 6,12 m³/s |
| A023, Segre | `200 OK` | `application/json; charset=utf-8` | `Access-Control-Allow-Origin: *` | 27/07/2026 17:45 CEST · 1,07 m³/s |

La resposta és un objecte JSON amb el camp `VALORES_ACTUALES`, que conté
files HTML de la taula oficial. El preflight `OPTIONS` va retornar `204 No
Content`, `Access-Control-Allow-Origin: *`, el mètode `GET` permès i la
capçalera sol·licitada autoritzada. Per tant, en aquesta verificació la CHE no
bloqueja la lectura per CORS.

La verificació amb el runtime Node de la funció va detectar una incidència TLS
diferent de CORS: `saihebro.com` servia només el certificat final i no enviava
l'intermedi `FNMT-RCM / AC Componentes Informáticos`. El `fetch` de Node
retornava `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, encara que Safari, `curl` i Python
podien completar la cadena amb els seus magatzems o mecanismes propis.

La funció incorpora l'intermedi oficial indicat per l'AIA del mateix certificat
de la CHE, amb empremta SHA-256
`F0:38:42:1F:07:F2:0D:63:A2:0D:36:91:E5:A1:78:AB:84:59:EB:E5:70:C1:64:7B:76:90:55:4E:F2:38:76:AB`
i vigència fins al 24/06/2028. S'afegeix a les arrels públiques de Node només
per a la consulta CHE. No es desactiva la comprovació TLS ni s'accepten
certificats no verificats.

EcoRadar manté, tanmateix, una funció intermediària pròpia:

```text
GET /api/refresh-reading?reading=river_flow_valira
GET /api/refresh-reading?reading=river_flow_segre
```

La redirecció de Netlify executa `netlify/functions/refresh-reading.mjs`.
Aquesta funció consulta en paral·lel els dominis oficials `www.saihebro.com`,
`ap.saihebro.com` i `internet.saihebro.com`, força IPv4 per evitar rutes
sortints incompletes del runtime serverless, valida el codi HTTP, el
`Content-Type`, el JSON, el camp `VALORES_ACTUALES`, el senyal i la data, i
retorna una resposta CORS amb `Cache-Control: no-store`. Cada intent té un
límit de 4,5 segons. Si fallen tots els dominis, retorna la causa de cada
intent en lloc d'un missatge genèric.

El 26/07/2026 es va comprovar una incidència específica del desplegament,
reconfirmada el 27/07/2026:
l'endpoint principal de la CHE responia directament amb HTTP 200 en menys
d'un segon, mentre la connexió sortint de la funció de Netlify acabava amb
temps d'espera. Com que el CORS oficial permet la consulta des del navegador,
el visor prova primer la connexió directa a la CHE i utilitza la funció
intermediària com a reserva. Així no depèn d'una única ruta de xarxa.

El visor consulta automàticament els dos cabals en carregar-se, repeteix la
consulta cada 15 minuts mentre la pàgina roman oberta i visible, i conserva el
botó individual «Actualitza dades». Cada lectura mostra el valor, la data i
hora de l'observació CHE, l'hora de consulta EcoRadar, la font, l'estació, la
freqüència, la provisionalitat i les limitacions. Quan la marca temporal
retornada coincideix amb la lectura mostrada, el missatge especifica que la
dada CHE ja està al dia i que encara no existeix un interval oficial posterior;
no presenta aquesta situació com un error. Si fallen tant la consulta
directa com la funció intermediària, mostra separadament el motiu de cada via
i conserva el darrer valor vàlid.

## Exemple de connexió

```text
GET https://www.saihebro.com/api/ficha/procesarTablaValoresActuales?estacion=A022
GET https://www.saihebro.com/api/ficha/procesarTablaValoresActuales?estacion=A023
```

El connector `ecoradar.connectors.connector_che_saih` descarrega i normalitza
els valors. No calcula tendències, alertes, perill ni cap altre indicador.

La minigràfica pública retorna una seqüència recent de valors sense publicar-ne
els instants individuals. EcoRadar la conserva només com a suport per calcular
una direcció qualitativa recent. No li assigna dates inventades. El servei
d'històric amb instants datats requereix un compte CHE i queda documentat amb
l'estat `requires_credentials`.

El senyal de precipitació acumulada en 24 hores publicat per A022 i verificat
el 26/07/2026 és `A022O83PA24H`.

## Regla d'interpretació

Les lectures són observacions puntuals a dues estacions d'aforament diferents:

- `A022` descriu el cabal mesurat al Valira a la Seu d'Urgell.
- `A023` descriu el cabal mesurat al Segre a la Seu d'Urgell.

No són una mitjana del riu, no representen tots els trams urbans i no s'han de
sumar per obtenir un “cabal de la Seu”. Les seccions d'aforament i les corbes de
desguàs poden canviar amb el temps.

## Provisionalitat i limitacions

El SAIH adverteix que les dades de temps real:

- arriben cada quinze minuts sense filtratge ni depuració previs;
- són provisionals fins que el Servei d'Hidrologia de la CHE les revisa;
- poden estar afectades per gel, troncs o fullatge, algues, sediments i
  incidències dels equips o de les comunicacions;
- no s'han d'utilitzar soles per prendre decisions amb conseqüències per a la
  seguretat o conseqüències econòmiques o operatives substancials.

Per això EcoRadar les etiqueta com a **dada provisional SAIH**. La lectura
derivada de situació hidrològica combina les dues estacions amb pluja observada
i prevista, sensibilitat a l'escorrentia i zones inundables, però no converteix
el cabal ni el nivell en una declaració d'inundació. Sense llindars oficials
d'estació publicats i sense un avís oficial, els valors puntuals no poden
demostrar una inundació actual.
