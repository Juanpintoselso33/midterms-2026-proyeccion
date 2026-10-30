# Proyección en vivo — midterms EE.UU. 2026 (martes 3-nov-2026)

Réplica más sofisticada del tablero de Brasil (`~/dev/brasil-2026-proyeccion`).
Alcance: TODO — Senado, gobernaciones y Cámara, 50 estados.

- `research/` relevamientos (feeds por estado, fuentes de base)
- `data/base/` bases históricas (los archivos pesados no se commitean)
- `model/` scrapers + modelo de proyección
- `dash/` tablero (Leaflet + Chart.js, GitHub Pages)
- `brasil_ref/` scripts de Brasil recuperados, como referencia

Reglas: siempre ambos partidos en gráfico, tabla e IC; scrapers con pocos hilos y backoff
(Retry-After); procesos largos con claude_tqdm y en background; nada en /tmp.
