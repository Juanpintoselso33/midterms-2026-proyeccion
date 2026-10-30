# Fuentes base - proyección midterms 2026 (armado 2026-10-30)

Raíz de datos: `/Users/juan/dev/midterms-2026-proyeccion/data/base/` (rutas abajo relativas a ella).
Nota técnica: MEDSL (Harvard Dataverse) exige "guestbook"; se baja con POST a `/api/access/datafile/<id>` (devuelve signedUrl). No se usó Tavily/Exa.

## 0. Mapas realmente vigentes para nov-2026 (verificado en Wikipedia + geometría)
Fuente: https://en.wikipedia.org/wiki/2025%E2%80%932026_United_States_redistricting y https://en.wikipedia.org/wiki/2026_United_States_House_of_Representatives_elections
Mapas nuevos EN VIGOR (9): **TX, CA (Prop 50), NC, UT (mapa judicial), OH, FL, TN, AL, LA**.
- **MO**: mapa 2025 aprobado pero BLOQUEADO para 2026 (SCOTUS 25-sep-2026 dejó el mapa 2022); referéndum en nov-2026 define 2028.
- **VA**: enmienda/referéndum invalidado por la Corte Suprema de Virginia: mapa viejo.
- IN, NY, MD, SC, WI, KS, IL, etc.: sin cambios. MD: sesión especial agosto 2026 fue por enmienda constitucional (efecto 2028).
- Cotejo independiente con geometría: comparando TIGER2025 cd119 vs TIGER2026 cd120 cambian exactamente AL, CA, FL, LA, MO, NC, OH, TN, TX, UT. (El cd120 de Census trae el mapa de MO bloqueado: NO usarlo para MO.)
- **LA**: primaria cerrada de la Cámara el 3-nov; general de la Cámara el **12-dic** (nuevo sistema/mapa). No se decide el 3-nov.

## 1. Presidencial 2024 por condado
- `pres2024_county/medsl_countypres_2000-2024.tab` - MEDSL doi:10.7910/DVN/VOQCHQ (v20, 2026-02-25), crudo, 94.151 filas candidato/modo.
- `pres2024_county/pres_2024_county_medsl_clean.csv` (3.154 filas) y `pres_2020_county_medsl_clean.csv` (3.154): dem/rep/total por FIPS. Regla: modo TOTAL si existe en el condado, si no suma de modos (ID NC RI SD UT WA WV WI WY no traen TOTAL).
- `pres2024_county/tonmcg_2024.csv` (3.160) y `tonmcg_2020.csv` (3.152): https://github.com/tonmcg/US_County_Level_Election_Results_08-24 (cruce).
- Chequeo: MEDSL 2024 Trump 77.302.467 / Harris 75.012.514 (oficial ~77,3M / ~75,0M OK). 2020: Biden 81,26M / Trump 74,22M OK. tonmcg 2024: 77.294.799 / 75.006.739 OK.
- Huecos/ojo: Alaska = 40/41 distritos de la Cámara estatal (FIPS 02xxx), no boroughs. Nueva Inglaterra: MEDSL usa condados (CT = 8 condados viejos, no regiones de planificación; MA/ME/NH/VT/RI condados, no pueblos). tonmcg tiene DC mal (36.882 D) y difiere en MO-Jackson (KC separado), ME-Cumberland y OR (pequeñas diferencias); preferir MEDSL. 11 FIPS solo en MEDSL y 17 solo en tonmcg (AK/CT/otros).

## 2. Midterm 2022 por condado
- `county_2022/senate_2022_county.csv` (2.114 filas, 34 contiendas + OK especial): MEDSL doi:10.7910/DVN/YB60EJ (crudo `medsl_senate_county_2022.tab`). dem/rep/total. Total de 2022 cotejado: GA 3,94M, FL 7,76M, etc. OK. Fuera: AK y VT sólo traen resultado estatal (fips `STATEWIDE`; AK = primera vuelta, RCV). Sin D en UT (McMullin). GA corresponde a la general, no al balotaje.
- `county_2022/governor_2022_county.csv` (2.092 filas, 36 estados): armado agregando los precintos MEDSL doi:10.7910/DVN/OAARCY (`STATE_precinct_general.csv`, 863 MB, no guardado) + AZ/MD/MI/AR del dataset UYQIEP. Columnas dem_votes, rep_votes, other, total_votes, quality_flag.
- Chequeo contra oficial (candidatos): Hobbs 1.287.877 (oficial 1.287.891), Newsom 6,47M, Kemp 2.111.572, Abrams 1.813.673, DeSantis 4,61M, Abbott 4,44M, Hochul 3.156.467 (OK).
- **PROBLEMAS**: (a) **ID gobernador NO CONFIABLE** (MEDSL da Little 682.840 vs ~358.600 real; total ~2x). Proxy: usar `senate_2022_county.csv` de ID (Crapo/Roth, cuentas sanas). (b) MI ~1% corto (Whitmer 2.403.861 vs 2.430.505). (c) AK en distritos; NY/MN/NM/VT/WY resueltos por nombre de candidato (fusión de líneas, DFL), con asignación manual de partido: Walz, Lujan Grisham, Ronchetti, Siegel (VT D/Prog), Livingston (WY, MEDSL la rotula libertaria; la cuento como D, a verificar). (d) Gobernador no incluye votos de modos faltantes si el condado carece de TOTAL y MEDSL no los trae.
- Presidente 2020 por condado: ver `pres_2020_county_medsl_clean.csv` (arriba).
- Nueva Inglaterra por pueblos: NO obtenido (sólo condados). Si hace falta, MEDSL precinct (state files) permite agregar a municipio.

## 3. Presidencial 2024 por distrito, mapas 2026
- `cd_pres2024/pres2024_by_cd_2026maps_clean.csv` (435 filas; district, harris, trump, total, other, dem_share_2way, + 2020 sólo para 262 distritos sin cambio de mapa). Crudo: `downballot_pres2024_by_cd_2026maps_votes.csv` / `_pct.csv`, `downballot_info_sheet.csv`.
- Fuente: The Downballot, https://www.the-downballot.com/p/the-downballots-calculations-of-presidential (hoja Google 1eZfaFI-c-PFOoKx1-zZA2MP0_dxRq_LVK0re3BOQqy0, export CSV). Es la versión con "los mapas que se usan en 2026".
- Chequeo: Harris 74.725.325 + Trump 77.282.962 sobre 435 distritos (falta DC: 0,29M de Harris, cuadra con 75,01M). Harris gana 201, Trump 234. Spot-checks de mapa: AL-02 (Harris 42%, mapa legislativo nuevo), TN-09 (39%), LA-06 (34%), UT-01 (62% D: distrito de Salt Lake nuevo), VA y MO con mapa viejo (VA-01 47%, MO-05 61%): consistente con la sección 0.
- Gap: la columna `incumbent_in_sheet` está desactualizada (p.ej. UT-01 muestra Blake Moore); usar los incumbentes de `races2026/house_2026_candidates_wikipedia.csv`. El detalle por condado/pedazo de distrito está en hojas por estado enlazadas desde la página (no bajadas).
- `house_2024/house_2024_by_district_medsl_clean.csv` (436 filas: 435 + DC?): resultados de la Cámara 2024 (MEDSL doi:10.7910/DVN/IG0UN2, v15) **en las líneas de 2024**; NO son comparables 1:1 en TX CA NC UT OH FL TN AL LA (mapas nuevos). Suma D 70,82M / R 74,41M (D incompleto por los distritos con D=0/uncontested y top-two). `flag_uncontested`=38 (incluye D-vs-D / R-vs-R de CA y WA, y votos codificados "1" en FL/OK). MEDSL no trae incumbente; el incumbente viene de la sección 4. Crudo `house_2024/medsl_house_1976-2024.tab`.
- Gap CRÍTICO / proxy: no existe resultado de la Cámara 2024 recalculado sobre los mapas 2026. Proxy sugerido: usar la presidencial 2024 (Downballot) como línea base y el rendimiento relativo del incumbente 2024 (Cámara - presidencial) sólo en distritos con mapa sin cambio; en los 9 estados redibujados, partir de presidencial + efecto incumbencia estimado.
- Senado estatal 1976-2024: `senate_state/medsl_senate_state_1976-2024.tab` (MEDSL PEJ5QU).

## 4. Lista de carreras 2026 (Wikipedia, extraída el 2026-10-30)
Todas via la API de Wikipedia (render HTML). Páginas: 2026 United States Senate elections / gubernatorial elections / House of Representatives elections.
- `races2026/senate_2026_wikipedia.csv`: 35 filas = 33 Clase 2 + 2 especiales (FL: Moody vs Nixon y Gillespie(I); OH: Husted vs Sherrod Brown, Levy(I), Redpath(L)). Incluye incumbente, estado de nominación, candidatos con partido. Ratings: `senate_2026_ratings_wikipedia.csv` (Cook, DDHQ, Econ, Fox, IE, NBC, RCP, Sabato... al 28-30 oct).
- `races2026/governors_2026_wikipedia.csv`: 40 filas (36 estados + DC, Guam, N. Marianas, etc.). Ratings: `governors_2026_ratings_wikipedia.csv`.
- `races2026/house_2026_candidates_wikipedia.csv`: 435 distritos (códigos `XX-NN`, `XX-AL`) con incumbente, partido, estado (jubilado/perdió primaria), `open_seat` (80), nº de candidatos por partido, `system`, `flag_uncontested` (18, sin D o sin R en estados no top-two), `flag_same_party_general` (9: CA-04, 07, 11, 12, 14, 29, 34, 37 D-vs-D y CA-40 Calvert vs Kim R-vs-R). Filas redistritadas con dos incumbentes aparecen unidas con `;`.
- Sistemas: top-two = CA y WA (en WA ningún distrito quedó con dos del mismo partido); RCV en general = AK y ME (AK Senado/Cámara/gob con primera "top-4"); LA = ver sección 0; Senado LA 2026 aparece como Letlow vs Davis.
- Gaps: el listado es de Wikipedia (editable, puede haber partidos mal rotulados, p.ej. Kevin Kiley como Independiente en CA-06; los votos de terceros y write-in no están). No incluye candidatos de balotajes de diciembre (LA, GA si hubiera). Voto 2024 por distrito para esos candidatos no aplica.

## 5. Voto anticipado/por correo 2026
- Fuente: UF Election Lab (Michael McDonald), https://election.lab.ufl.edu/early-vote/2026-early-voting/ ; los CSV salen del JS de la página: `https://election.lab.ufl.edu/data-downloads/earlyvote/2026/{US,<ST>_county,<ST>_cd,house_tossup_races}.csv`. CC BY-NC-ND 4.0: atribuir, no uso comercial.
- `early_vote/US.csv`: 49 filas (todos menos **AL y NH** que no reportan), último update 10/30/2026 (30 estados), 10/29 (18), 10/26 (1). Columnas request/accept/inperson/voted por total y por partido/edad/género/raza, `turn_2022`. Suma nacional voted_all = **47.520.770** (correo aceptado 22,26M + en persona 25,38M). Top: TX 6,44M, CA 5,06M, FL 4,41M, GA 2,51M, NC 2,35M.
- `early_vote/county/<ST>_county.csv` (47 estados) y `early_vote/cd/<ST>_cd.csv` (22 estados con corte por distrito), `house_tossup_races.csv`. Algunos estados no reportan por partido; los datos de partido son por registro, no voto. AZ reporta como "request" las boletas enviadas. Los `*_cd.csv` están en filas distrito x condado (sumar). TX, FL, TN, AL y LA no tienen archivo cd (sólo 22 estados lo publican).
- Scripts del sitio guardados: `early_vote/2026-early-voting*.js`.
- Gap: sin series históricas diarias (esta es una foto); para comparar con 2022 hay `turn_2022` (total votado 2022) y la página de 2022 del Election Lab.

## 6. Geometría
- `geometry/counties-10m.json` (842 KB): us-atlas@3 counties-10m (jsdelivr) tal cual.
- `geometry/congressional_districts_2026_inforce.geojson` (444 features: 435 + territorios y áreas "ZZ"; filtrar CD != 'ZZ'): TIGER2026 `cd120` (Census, por estado, zips en `geometry/tiger2026_cd120/`) para todos los estados salvo **MO**, que usa TIGER2025 cd119 (líneas 2022, porque el mapa nuevo de MO está bloqueado). Columna `map_source` lo indica.
- `geometry/cb_2025_us_cd119_500k.zip`: cartográfico 119º (líneas 2024, mapas viejos) para comparación. No existe `cb_2026_..._cd120` (404).
- Chequeo: ver sección 0 (cd120 vs cd119 cambia exactamente en los 9 estados vigentes + MO). Las geometrías TIGER no están generalizadas (pesadas); para web usar mapshaper/simplificar.
- Gap: las fuentes oficiales por estado (TX, CA, FL, etc.) no se contrastaron una por una; la correspondencia con Downballot se validó sólo por spot-check de PVI/Harris.

## Resumen de lo que NO se pudo conseguir
1. Cámara 2024 recalculada sobre los mapas 2026 (proxy: presidencial 2024 de Downballot, sección 3).
2. Gobernador 2022 de Idaho confiable (proxy: Senado 2022 ID); MI ~1% corto.
3. Pueblos de Nueva Inglaterra y boroughs de Alaska (sólo condados y distritos estatales).
4. Voto anticipado de AL y NH; corte por distrito sólo en 22 estados.
5. Verificación independiente (fuente oficial) de las listas de candidatos de Wikipedia.
