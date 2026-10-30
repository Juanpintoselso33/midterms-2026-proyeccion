#!/bin/zsh
# Wait for the ballot-box download, build section units, run the state-level model on sections and on municipalities.
D=/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad
cd $D
while pgrep -f "fetch_bu.py" > /dev/null; do sleep 10; done
echo "descarga terminada $(date +%H:%M)"
uv run -q --with duckdb --with numpy --with pandas python $D/build_sec.py > $D/build_sec.log 2>&1 || { echo "build_sec falló"; exit 1; }
tail -2 $D/build_sec.log
NOEPS=1 uv run -q --with torch --with numpy --with scipy --with tqdm python $D/vi_ei2.py $D/units_sec.npz $D/vi_ei2_sec.json > $D/vi_ei2_sec.log 2>&1
echo "mesas listo (exit $?) $(date +%H:%M)"
NOEPS=1 uv run -q --with torch --with numpy --with scipy --with tqdm python $D/vi_ei2.py $D/units_mun.npz $D/vi_ei2_mun.json > $D/vi_ei2_mun.log 2>&1
echo "municipios listo (exit $?) $(date +%H:%M)"
