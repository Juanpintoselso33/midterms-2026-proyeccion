# Feeds de resultados oficiales — estados MT a WY (25) — relevado 2026-10-30

Metodología: curl (UA de navegador) a 1-5 URLs por estado; la extensión de Chrome sólo para leer el tráfico de red de páginas que cargaban. Donde un WAF devolvió desafío/403 se registra y **no** se intentó esquivar. "verified = yes" sólo si se bajaron datos reales del endpoint. Muestras en `research/samples/<ST>/`.

## Tabla resumen

| State | Platform | Machine-readable | Endpoint pattern | County | District (US House) | Vote type | Verified |
|---|---|---|---|---|---|---|---|
| MT | Desconocida (sosmt.gov detrás de Cloudflare 403) | no (sin comprobar) | — | ? | ? | ? | no |
| NE | SoS ASP.NET + WCF `ResultsAjax.svc` (mismo producto que ND/SD) | partial | `https://neresultswebservice.azurewebsites.us/ResultsAjax.svc/GetVoterTurnoutData?` (JSON); resultados por HTML `electionresults.nebraska.gov` + Export CSV/XML | sí | sí (por HTML) | no confirmado | yes (sólo turnout/precintos) |
| NV | SoS `silverstateelection.nv.gov` (Imperva/Incapsula 307/302) | no (sin comprobar) | — | ? (por regla, no se publican conteos por condado antes del cierre) | ? | ? | no |
| NH | SoS (Access Denied en sos.nh.gov); no hay host ENR resoluble | no (sin comprobar) | — | ? (NH reporta por pueblo) | ? | ? | no |
| NJ | nj.gov (PDF/Excel); sin ENR identificado | no / partial | — | PDF por condado | PDF | no | no |
| NM | `electionresults.sos.nm.gov` (403, servidor "volt-adc") | no (sin comprobar) | — | ? | ? | ? | no |
| NY | `nyenr.elections.ny.gov` (Cloudflare challenge); además cada Board of Elections de condado publica aparte | no (sin comprobar) | — | ? | ? | ? | no |
| NC | NCSBE `er.ncsbe.gov` (JSON propio) | yes | `https://er.ncsbe.gov/enr/{YYYYMMDD}/data/{contest,county,results_{cid},precinct_{cid}}.txt` (JSON) ; zips en `dl.ncsbe.gov/ENRS/` | sí (+precinto) | sí | sí (early/election-day/absentee/provisional) | yes (2024-11-05 y 2026-03-03) |
| ND | SoS ASP.NET + WCF `ResultsAjax.svc` | partial | `https://resultsws.sos.nd.gov/ResultsAjax.svc/GetVoterTurnoutData?`; `results.sos.nd.gov/ResultsSW.aspx?text=All&type=SW&map=CTY` (HTML); Export CSV/XML/RSS por formulario | sí | sí (HTML) | no (hay página de absentee/early stats) | yes (turnout JSON + HTML 2024) |
| OH | `liveresults.ohiosos.gov` (Cloudflare Turnstile) | no (bloqueado) | — | ? | ? | ? | no |
| OK | `results.okelections.us` (403 de balanceador AWS) | no (sin comprobar) | — | ? | ? | ? | no |
| OR | `results.oregonvotes.gov` (hoy redirige a la home de SoS; sólo vivo en la noche) | desconocido | — | ? | ? | ? | no |
| PA | `electionreturns.pa.gov` (Imperva/Incapsula, bloquea incluso el navegador) | no (bloqueado) | — | ? | ? | ? | no |
| RI | Enhanced Voting | yes | `https://electionresults.ri.gov/results/public/api/elections/rhodeisland/{electionId}/data` | sí (40 ciudades/pueblos, `localityElections`) | sí | sí (Election Day / Early Voting / Mail Ballots en `countGroups`) | yes (2026 primary) |
| SC | Scytl ENR (`enr-scvotes.org`), patrón estilo Clarity | yes (con salvedad: id 2026 aún no listado) | `https://www.enr-scvotes.org/SC/{eid}/current_ver.txt` → `.../SC/{eid}/{ver}/json/{sum,ALL,en/summary}.json`, `reports/detailxml.zip` | sí | sí | no confirmado | yes (2024 eid 122436) |
| SD | SoS ASP.NET + WCF (Azure) | partial | `https://sdresws.azurewebsites.us/ResultsAjax.svc/GetVoterTurnoutData?`; HTML `electionresults.sd.gov` | sí | sí (HTML) | no confirmado | yes (turnout, ya con elección 2026) |
| TN | `elections.tn.gov` / sos.tn.gov (403 CloudFront) | no (sin comprobar) | — | ? | ? | ? | no |
| TX | `results.texas-election.com` (Cloudflare challenge). Además feed XML de pago para medios | no (bloqueado) / partial vía feed pago | — | ? | ? | ? | no |
| UT | Enhanced Voting | yes | `https://electionresults.utah.gov/results/public/api/elections/Utah/{electionId}/data` (id 2026: `General11032026`) | sí | sí | no confirmado | yes (2026 primary) |
| VT | Custom Angular + JSON estático | yes | `https://static.electionresults.vermont.gov/elections/elections.json` → `.../elections/{guid}.json` → `.../elections/{guid}-{f,s,sn,h,cty,t,turnout}-{ts}.json` | sí (condado y pueblo) | sí (1 escaño) | no | yes (2026 Aug primary) |
| VA | Enhanced Voting | yes | `https://enr.elections.virginia.gov/results/public/api/elections/virginia/{electionId}/data` (id: `2026-November-General`) | sí (133 localidades) | sí | sí (Early / Election Day / Mailed Absentee / Provisional / Post-Election) | yes (2026 Aug primary) |
| WA | Enhanced Voting | yes | `https://results.votewa.gov/results/public/api/elections/{washington\|king-county-wa…}/{electionId}/data` (id: `20261103`) | sí | sí | no | yes (2026-08-04) |
| WV | SoS ASP.NET MVC `apps.sos.wv.gov/elections/results/` (archivo con selector de año/condado) | no (scraping HTML) | — | sí | ? | ? | no |
| WI | No existe sistema estatal; 72 clerks de condado publican en sus webs | no | — | cada condado aparte | — | — | n/a |
| WY | `sos.wyo.gov/Elections/ElectionResults.aspx`; `wyoresults.com` no resuelve DNS | no / desconocido | — | ? | ? | ? | no |

Cuenta: yes 7 (NC, RI, SC, UT, VT, VA, WA); partial 4 (NE, ND, SD, NJ); no/desconocido/bloqueado 13 (MT, NV, NH, NM, NY, OH, OK, OR, PA, TN, TX, WV, WY); WI n/a (county-run).

## Hallazgos transversales

- **Enhanced Voting (EV)** sirve el mismo API REST a todos sus clientes: `{host}/results/public/api/jurisdictions/{slug}` (lista de elecciones con `publicElectionId`, localidades hijas) y `{host}/results/public/api/elections/{slug}/{publicElectionId}/data` (JSON completo: `ballotItems[]` con `summaryResults.ballotOptions[].voteCount`, `reportingStatus {reportingUnits,totalUnits,asOf}`, `localityElections`, `countGroups` = tipos de voto). Endpoint descubierto leyendo el JS (`/elections/{a}/{p}`, `/stats`, `/turnout`, `/vr`, `/localities`) y el tráfico de red de la página. Para condados: mismo patrón con el `shortName` de `childLocalities` (verificado en WA: `king-county-wa`, 1,5 MB). Puede haber otros estados EV entre los míos (OR y WY son candidatos; no confirmados).
- UT y WA ya tienen la elección general 2026 publicada en el API (vacía, `asOf` 2026-10-21/22, sin contests aún): mismo `electionId` se usará la noche del 3-nov. UT: `General11032026`; WA: `20261103`; RI: `2026StatewideGeneralElection`; VA: `2026-November-General`.
- **Familia ASP.NET/WCF (ND, SD, NE)**: mismo producto, `ServiceRoot` = webservice propio. Funciones útiles vistas en `utils.js`: `GetVoterTurnoutData`, `GetMapData?type=&category=&raceID=&osn=&county=&party=`, `GetDistrictData`, `GetAreaListForExport`. Los resultados de cada contienda salen en HTML (`ResultsSW.aspx?text=All&type=SW&map=CTY`) y por Export (CSV/XML/RSS, por formulario POST; no se probó). SD y NE ya muestran la elección 2026 (precintos totales 671 y 1.322; turnout 0).
- **WAF**: Cloudflare (TX, NY, OH, MT, WI-elections.wi.gov, RI-elections.ri.gov), Imperva/Incapsula (PA, NV), otros 403 (NM volt-adc, OK ELB, TN CloudFront, NH). Registrado, no esquivado. El navegador tampoco pasó en PA (Incapsula) ni OH (Turnstile).

## Secciones por estado

### MT — Montana
1. `sosmt.gov/elections/results/` (SoS). `electionresults.mt.gov` redirige ahí. Plataforma: no identificada.
2. Feed: no comprobado. Todo `sosmt.gov` devuelve 403 (Cloudflare, `__cf_bm`) a curl.
3-4. Desconocido. 5. Probado: curl a 3 URLs. Qué falta: mirar desde un navegador con sesión normal. Nota: MT cuenta mucho por correo/absentee y varios condados reportan lento.

### NE — Nebraska
1. `https://electionresults.nebraska.gov/`. Producto ASP.NET + WCF en `neresultswebservice.azurewebsites.us` (misma familia que ND y SD).
2. JSON verificado: `.../ResultsAjax.svc/GetVoterTurnoutData?` (devuelve `{"d":[{CountyName, PrecinctsReporting, TotalPrecincts, Voters, calcVoterTurnout…}]}`). Resultados por contienda: HTML y Export (CSV/XML/RSS por formulario); no se probó el Export.
3. Condado + precinto-count; distrito congresional en HTML ("U.S. Congressional District"). Tipo de voto: no confirmado.
4. Sí: precintos reportando/totales (1.322) y votantes registrados (1.265.162). 5. Sin robots.txt (404). Nebraska reparte electores por distrito (no aplica a midterm). Muestra: `samples/NE/turnout.json`.

### NV — Nevada
1. `https://silverstateelection.nv.gov/` (SoS). Imperva/Incapsula (307/302 con cookies `visid_incap`).
2. No comprobado. 3. Por regla estatal, el SoS no puede mostrar conteos por condado antes del cierre de votación (según prensa). 5. Nevada cuenta mail ballots llegados hasta 4 días después; Clark publica primero early+mail y luego Election Day. Resultados completos tardan días. Muchos condados (Clark, Washoe) tienen sitio propio.

### NH — New Hampshire
1. SoS `sos.nh.gov/elections/election-results` → "Access Denied" (Akamai). `results.sos.nh.gov` y `nh.electionstats.com` no resuelven/sitio no encontrado. Plataforma: desconocida.
2-4. Sin datos. 5. NH cuenta por pueblo/ward en 300+ municipios; el SoS agrega. Falta: confirmar desde navegador.

### NJ — New Jersey
1. `nj.gov/state/elections/election-information-results.shtml` (Division of Elections): PDFs por condado y turnout (`assets/pdf/election-results/<año>/...`), actualmente con enlaces ya listados para 2026. No se encontró ENR en vivo con API.
2. No machine-readable detectado (PDF; posible Excel). 3. Condado (PDF), distrito (PDF US House). 5. NJ cuenta mail ballots por días y los condados publican antes que el estado (cada clerk de condado tiene su sitio). Estado: partial/sin verificar.

### NM — New Mexico
1. `https://electionresults.sos.nm.gov/` → 403 (servidor "volt-adc"). Plataforma desconocida. 2-4 sin datos. 5. WebFetch también 403.

### NY — New York
1. `https://nyenr.elections.ny.gov/` → Cloudflare challenge (`cf-mitigated: challenge`). Los Boards of Elections de condado/NYC publican por separado la noche. Sin datos del feed.

### NC — North Carolina (verificado)
1. `https://er.ncsbe.gov/` — NCSBE, app propia, JSON en archivos `.txt`.
2. Sí. `elections.txt` lista fechas (incluye 11/03/2026). Por elección: `https://er.ncsbe.gov/enr/{YYYYMMDD}/data/contest.txt` (catálogo de contiendas), `county.txt` (estado por condado), `results_0.txt` (estatal; `results_{countyId}.txt` por condado), `precinct_{countyId}.txt`. `contest.txt` de 20261103 ya responde 200 (catálogo, sin votos). Descarga masiva: `dl.ncsbe.gov/ENRS/{YYYY_MM_DD}/results_pct_{YYYYMMDD}.zip` (HEAD dio 301, no se bajó).
3. Estatal, condado y precinto; US House por distrito ("US HOUSE OF REPRESENTATIVES DISTRICT 01"). Tipo de voto: sí — campos `evc` (early), `ovc` (election day), `avc` (absentee), `pvc` (provisional).
4. Sí: `prt/ptl` precintos reportando/total, `bct` boletas, `rtl` registrados, `imp/sub` timestamps.
5. Muestras: `samples/NC/` (contest, county, results_0, results_1, precinct_1 de 2024-11-05; contest/county de 2026-03-03). NC cuenta early/absentee primero, luego Election Day; fácil de parsear.

### ND — North Dakota
1. `https://results.sos.nd.gov/` (SoS, ASP.NET + `resultsws.sos.nd.gov`). Hoy muestra la general 2024 como elección por defecto; la 2026 se habilita al cargarse.
2. JSON: `https://resultsws.sos.nd.gov/ResultsAjax.svc/GetVoterTurnoutData?` (verificado: por condado, PrecinctsReporting/TotalPrecincts/Voters). Resultados: `ResultsSW.aspx?text=All&type=SW&map=CTY` (HTML verificado, con votos y %). `ResultsExport.aspx` ofrece CSV/Excel/RSS/XML (formulario con POST; no se probó descarga).
3. Estatal, condado, ciudad, distrito legislativo; US House (at-large) en la lista. Tipo de voto: página aparte de absentee/early. 4. Sí (385 precintos; "Precincts Fully/Partially"). Muestras: `samples/ND/`.

### OH — Ohio
1. `https://liveresults.ohiosos.gov/` (SoS). Cloudflare Turnstile ("Un momento…") también en el navegador. Búsqueda: los condados suben archivos al County Submission System del SoS; no hay documentación pública de descarga. No intentado esquivar. Sin datos del feed.
5. Ohio cuenta early/mail primero (publica pronto), luego Election Day.

### OK — Oklahoma
1. `https://results.okelections.us/` (State Election Board). 403 desde balanceador AWS. Plataforma desconocida; sin datos.

### OR — Oregon
1. `https://results.oregonvotes.gov/` — hoy redirige a `sos.oregon.gov` (el sitio de resultados sólo se levanta el día de elección; `/ResultsMain.aspx` y `/results/public/oregon` dan 404). Plataforma sin confirmar (podría ser EV; no verificado). Oregon es 100 % voto por correo; la mayor parte llega el día de la elección y se cuenta tarde. Resultados históricos: records.sos.state.or.us (precinto 2024 general). Falta: comprobar la noche del 3-nov.

### PA — Pennsylvania
1. `https://electionreturns.pa.gov/` (Dept. of State). Imperva/Incapsula bloquea tanto curl como navegador (403 + recurso `_Incapsula_Resource`). Sin datos. No documentado públicamente en búsquedas.
5. Quirk conocido: mail ballots no se pueden abrir hasta el día de elección y se cuentan al final/Dem-heavy; condados reportan a ritmos distintos. Muchos condados (Philadelphia, Allegheny) publican por su cuenta.

### RI — Rhode Island (verificado)
1. `https://electionresults.ri.gov/results/public/rhodeisland` (Enhanced Voting).
2. API: `.../results/public/api/jurisdictions/rhodeisland` (elecciones: `2026StatewideGeneralElection` 2026-11-03, `RI2026StatewidePrimary`…) y `.../api/elections/rhodeisland/{id}/data` (JSON 192 contests en la primaria).
3. Estatal + 40 localidades; Senado y House por distrito. Tipo de voto: `countGroups` Election Day / Early Voting / Mail Ballots. 4. `reportingStatus {reportingUnits,totalUnits}` por contienda (40/40 = ciudades). Muestra: `samples/RI/`.

### SC — South Carolina (verificado en archivo 2024)
1. `https://www.enr-scvotes.org/SC/` (Scytl ENR). `elections.json` hoy vacío (las elecciones se listan al activarse). SoS: scvotes.gov.
2. Patrón estilo Clarity: `/SC/{electionId}/current_ver.txt` → versión; luego `/SC/{eid}/{ver}/json/sum.json`, `json/ALL.json` (por condado), `json/en/summary.json`, `reports/detailxml.zip` (precinto), `reports/summary.zip`. Probado con 2024 general (eid 122436, ver 359624): todos 200.
3. Estatal, condado, precinto (XML); US House por distrito. 4. Sí: `TP` precintos totales / `PR` reportando por contienda. Tipo de voto: no confirmado. Muestras: `samples/SC/`. Aviso: el id de la elección 2026 hay que descubrirlo la noche (aparece en `elections.json`).

### SD — South Dakota
1. `https://electionresults.sd.gov/` (ASP.NET + `sdresws.azurewebsites.us`). Ya muestra "November 3, 2026", 671 precintos, 628.629 registrados, "Testing In Progress".
2. JSON: `.../ResultsAjax.svc/GetVoterTurnoutData?` (verificado, formato `{"d":[...]}` con `__type`). Resultados por HTML/Export. 3-4 como ND/NE. Sin robots.txt. Muestra: `samples/SD/turnout.json`.

### TN — Tennessee
1. `https://elections.tn.gov/` y `sos.tn.gov/elections/results` → 403 (CloudFront). `tnelectionresults.tn.gov` no resuelve. Plataforma desconocida; sin datos. TN cuenta early vote primero (reporta rápido).

### TX — Texas
1. `https://results.texas-election.com/` (SoS). Cloudflare challenge. Búsqueda: el SoS ofrece feed XML a medios por suscripción ($250 en ciclos previos, actualización ~2 min); la web va 5-7 min detrás. Sin datos verificables. Feed pago es un camino legítimo si se quiere TX en tiempo real.
5. TX reporta early vote primero (a las 7 pm CT), luego Election Day; 254 condados.

### UT — Utah (verificado)
1. `https://electionresults.utah.gov/results/public/Utah` (Enhanced Voting).
2. `.../api/jurisdictions/Utah` (id 2026: `General11032026`, `Primary06232026`) y `.../api/elections/Utah/{id}/data` (JSON 169 KB para la primaria; US House incluido como "REP U.S. House District 2"). General 2026 ya responde, `asOf` 2026-10-21, sin contests. 
3. Estatal + 29 condados (`childLocalities`); distrito por contienda. Tipo de voto: no. 4. `reportingStatus` por contienda. Reportes Excel/PDF (`publicReportCategories`, `mediaExportPath`). Utah vota casi todo por correo; muchos ballots llegan en los días siguientes. Muestras: `samples/UT/`.

### VT — Vermont (verificado)
1. `https://electionresults.vermont.gov/` (app Angular propia). 
2. `https://static.electionresults.vermont.gov/elections/elections.json` (lista; general 2026 guid `68d61e96-1d28-4210-8c1d-8e90512ae105`) → `.../elections/{guid}.json` (índice con paths timestamp) → `.../elections/{guid}-{f|s|sn|h|cty|t|turnout}-{timestamp}.json` (f = federal, s = statewide, h = house…). Hay que releer el índice para obtener los timestamps nuevos. Verificado con la primaria de agosto 2026 (federal 525 KB).
3. Pueblo (`tid`), condado; escaño federal único. Tipo de voto: no. 4. `townsReporting` "247 OF 247" y `distReported`. Existe feed RSS. Muestras: `samples/VT/`.

### VA — Virginia (verificado)
1. `https://enr.elections.virginia.gov/results/public/virginia` (Enhanced Voting; `www.elections.virginia.gov/results/` apunta ahí).
2. `.../api/jurisdictions/virginia` y `.../api/elections/virginia/{id}/data`. Ids: `2026-November-General`, `2026-August-Democratic-Primary`… Verificado con la primaria Dem (5 distritos US House, 18/18 unidades reportando). General 2026 ya existe en el API.
3. 133 localidades hijas (condados/ciudades independientes), `crossCounties` por contienda. Tipo de voto: `countGroups` Early Voting / Election Day / Mailed Absentee / Provisional / Post-Election. 4. `reportingStatus` por contienda. VA reporta early/mail en bloque primero (las ciudades "blue" tarde). Muestras: `samples/VA/`.

### WA — Washington (verificado)
1. `https://results.votewa.gov/results/public/washington` (EV; también `results.vote.wa.gov` redirige).
2. `.../api/jurisdictions/washington` (elecciones `20261103`, `20260804`, `20260428`…) y `.../api/elections/{washington|king-county-wa|...}/{id}/data` (estatal 646 KB; King 1,5 MB, ambos 200). Reporte Excel con precintos (`Summary and Precinct Results Excel`).
3. Estatal + 39 condados; US House por distrito (10); `totalVoters` 5.147.877 (denominador registrados). Tipo de voto: no. WA es voto por correo: conteo diario por días, muchas boletas llegan tarde; el primer drop a las 8 pm PT es grande. Muestras: `samples/WA/`.

### WV — West Virginia
1. `https://apps.sos.wv.gov/elections/results/` (SoS, ASP.NET MVC). Hoy es archivo (selector de años 2008-2017+, elección, condado). No se vio feed ni descarga; robots.txt 200. Probable raspado HTML. Plataforma de ENR en vivo no confirmada. Falta: ver el sitio la noche.

### WI — Wisconsin
1. No hay sitio estatal de resultados no oficiales. WEC lo dice expresamente: 72 county clerks publican en sus propios sitios (cada uno con su plataforma; el patrón: municipios → clerk de condado en 2 h tras las 8 pm CT → clerk lo postea en otras 2 h), y los números estatales vienen de AP/medios. `elections.wi.gov` está detrás de Cloudflare (403 a curl). Resultados oficiales: canvass posterior. Milwaukee: mail/absentee central count llega tarde (~madrugada). Para proyección: usar AP o raspar los 72 sitios (varían: Clarity/Enhanced Voting/PDF); no relevado condado por condado.

### WY — Wyoming
1. `https://sos.wyo.gov/Elections/ElectionResults.aspx` (SoS, ASP.NET) con página `2026ElectionInformation.aspx`; `wyoresults.com` no resuelve; no se identificó ENR ni feed. Wyoming tiene 24 condados; se espera subir el EV/KnowInk, sin confirmar. Falta: ver la noche o mirar vía navegador.

---
Cuenta final: yes 7 (NC, RI, SC, UT, VT, VA, WA); partial 3 (NE, ND, SD) + NJ (PDF) ; no/bloqueado/desconocido 14 (MT, NV, NH, NM, NY, OH, OK, OR, PA, TN, TX, WV, WY) ; WI n/a (county-run).
