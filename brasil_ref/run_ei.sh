#!/bin/zsh
# Bayesian RxC EI on CPU, stratified sample per region, one region at a time (finished regions are skipped).
D=/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad
cd $D
uv run -q --with pyei --with numpyro --with jax --with requests --with tqdm --with scipy \
  python $D/ei.py Norte Centro-Oeste Sul Sudeste Nordeste > $D/ei_run.log 2>&1
echo "EI terminado (exit $?) $(date +%H:%M)"
