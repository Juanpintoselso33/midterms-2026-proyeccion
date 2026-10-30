"""Summarize votes cast after 17:00 Brasília across all runoff sections (dedupes repeated sections)."""
import glob, json
import pandas as pd

D = "/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/late"
rows = {}
errs = {}
for p in glob.glob(f"{D}/late2_*.jsonl"):
    for line in open(p):
        j = json.loads(line)
        k = (j["uf"], j["mu"], j["zo"], j["se"])
        if "err" in j:
            errs.setdefault(k, j["err"])
        else:
            rows[k] = j
total_secs = len(json.load(open(f"{D}/../bu/sections_r2.json")))
missing = {k: v for k, v in errs.items() if k not in rows}
df = pd.DataFrame(rows.values())
print(f"mesas con log leído: {len(df)} de {total_secs} · sin dato: {len(missing)} {pd.Series(list(missing.values())).value_counts().to_dict()}")
print(f"votos en logs: {df.votes.sum():,}")
print(f"votos después de las 17:00: {df.after17.sum():,} en {(df.after17 > 0).sum():,} mesas")
print(f"  después de las 18:00: {df.after18.sum():,} · después de las 19:00: {df.after19.sum():,}")
print(f"  entre 17:00 y 17:05: {(df.after17.sum() - 0):,} total; último voto del país: {df['last'].dropna().max()}")
late = df[df.after17 > 0].copy()
by = late.groupby("uf").agg(mesas=("se", "size"), votos=("after17", "sum"), post18=("after18", "sum")).sort_values("votos", ascending=False)
by["pct_del_total"] = (by.votos / by.votos.sum() * 100).round(1)
print(by.head(27).to_string())
mun = late.groupby(["uf", "mu"]).after17.sum().sort_values(ascending=False).head(15)
print(mun.to_string())
# how the late sections voted (whole-section result; the log does not say who each late voter chose)
lb = late.dropna(subset=["F", "L"])
for name, g in [("mesas con votos post-17", lb)]:
    print(f"{name}: Lula {g.L.sum() / (g.L.sum() + g.F.sum()) * 100:.2f}% · Flávio {g.F.sum() / (g.L.sum() + g.F.sum()) * 100:.2f}% ({len(g)} mesas, {int(g.L.sum() + g.F.sum()):,} válidos)")
heavy = lb[lb.after17 >= 10]
print(f"mesas con ≥10 votos post-17: {len(heavy)} · votos post-17 {heavy.after17.sum():,} · Lula {heavy.L.sum() / (heavy.L.sum() + heavy.F.sum()) * 100:.2f}% · Flávio {heavy.F.sum() / (heavy.L.sum() + heavy.F.sum()) * 100:.2f}%")
df.to_parquet(f"{D}/late_all.parquet")
