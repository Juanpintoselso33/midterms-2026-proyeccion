# Fuente principal: JSON públicos del NYT (datos AP)

Encontrada el 2026-10-30 a partir de `alex/nyt-2020-election-scraper` (1.757★), que hizo
git-scraping del CDN del NYT en 2020.

## Endpoints verificados (curl, 200)
Base: `https://static01.nyt.com/elections-assets/pages/data/2026-11-03/`

| Archivo | Tamaño hoy | Contenido |
|---|---|---|
| `results-senate.json` | 650 KB | 35 carreras (incluye especiales FL y OH), solo unidad estatal |
| `results-governor.json` | 611 KB | 36 carreras |
| `results-house.json` | 6,8 MB | 436 carreras, con 3.737 unidades de condado + ciudades/pueblos |

Por estado (patrón confirmado con 2024, todavía 404 para 2026; se publican cerca de la
elección): `results-{estado}-us-senate.json`, `results-{estado}-governor.json`,
`results-{estado}-us-house-{n}.json`. 2024: `.../2024-11-05/results-pennsylvania-us-senate.json` → 200.

## Campos clave por unidad de reporte
- `total_votes`, `total_expected_vote` (denominador de votos esperados, de AP)
- `eevp` (% estimado del voto esperado), `eevp_by_vote_type`,
  `expected_vote_by_vote_type` con `advance` / `election_day_in_person` / `provisional`
- `precincts_reporting` / `precincts_total`
- `candidates[].votes.total`, `candidate_metadata` (partido)
- `nyt_model_estimates` (el modelo propio del NYT, con cuantiles y probabilidad de victoria)
  → útil como comparación, no como insumo
- `rating` (calificación de la carrera), `pollClosingTimes`

## Uso
Uso personal, sin fines comerciales, citando a AP/NYT. Sondeo cortés: cada 60–120 s,
pocos hilos. Los feeds oficiales verificados (`feeds_*.md`) quedan como control cruzado.

## Ensayo
Los archivos de 2024 (`2024-11-05/`) tienen el resultado final con el mismo esquema. Para
la línea de tiempo del ensayo, el historial de git de `alex/nyt-2020-election-scraper` trae
snapshots de 2020.

## Modelo de referencia
`washingtonpost/elex-live-model` (código abierto, activo en oct-2026): regresión por
cuantiles contra una base histórica + predicción conformal para votos pendientes.
Candidato a motor o a punto de comparación.
