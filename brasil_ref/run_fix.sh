#!/bin/zsh
# Reprocess sections whose log was misread (multi-file .jez), 4 processes.
cd /private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late
export PREFIX=fix SECS=/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late/zero_secs.json
uv run -q --with requests --with asn1tools --with tqdm python late2.py 0 4 12 > /private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late/fix0.log 2>&1 &
uv run -q --with requests --with asn1tools --with tqdm python late2.py 1 4 12 > /private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late/fix1.log 2>&1 &
uv run -q --with requests --with asn1tools --with tqdm python late2.py 2 4 12 > /private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late/fix2.log 2>&1 &
uv run -q --with requests --with asn1tools --with tqdm python late2.py 3 4 12 > /private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late/fix3.log 2>&1 &
wait
grep -h parte /private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late/fix*.log
