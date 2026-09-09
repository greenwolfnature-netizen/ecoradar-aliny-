# Registre únic de lectures d’EcoRadar Alinyà

`projectes/Alinya/metadata/reading_registry.json` és el contracte de metadades
que comparteixen les lectures, els RADAR, la completesa, el visor i el
generador d’informes. Es genera després de recalcular les dependències i abans
de l’històric i l’exportació web.

Cada execució crea un `snapshot_id` determinista a partir de l’hora comuna de
comprovació, els valors i dates de les lectures, el QA, els resultats CORE i
les versions de les fonts. Tots els productes públics reben aquest mateix
identificador. El registre anterior es conserva a
`projectes/Alinya/history/snapshots/` quan canvia l’estat.

Per a cada lectura el registre publica, quan existeix:

- font i URL o endpoint;
- data d’observació o període, separada de `checked_at_utc`;
- resolució, cobertura i denominador;
- suport espacial, quadrícula i màscara;
- QA, vigència i freqüència d’actualització;
- regla de compatibilitat temporal i espacial;
- tipus de mesura: lectura directa, context d’inventari, derivació o puntuació sintètica.

Una dada antiga o un compost multitemporal pot romandre com a context, però no
es converteix en una observació actual. Una dada absent no es converteix en
zero. La funció Netlify rebutja lectures, històric, perill o registre amb
`snapshot_id` diferents.

L’àmbit actual prové d’una exportació aportada d’Instamaps. El CRS, la
geometria i la superfície de treball estan documentats, però l’organisme autor,
la URL de la capa original i la llicència continuen en
`pending_verification`; el visor l’anomena “Àmbit de treball”.
