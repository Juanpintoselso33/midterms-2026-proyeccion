"""Build section-level units: first round (TSE open data) joined with the runoff ballot-box sample."""
import json, os
import duckdb, numpy as np

D = "/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad"
V = f"{D}/secao_r1/votacao_secao_2026_BR.csv"
DET = f"{D}/secao_r1/detalhe_votacao_secao_2026_BRASIL.csv"
R1P = f"{D}/secao_r1/r1_sec.parquet"
con = duckdb.connect()
opts = "delim=';', header=true, encoding='latin-1', all_varchar=true"

if not os.path.exists(R1P):
    print(con.execute(f"""select NR_VOTAVEL, any_value(NM_VOTAVEL), sum(cast(QT_VOTOS as bigint)) v
        from read_csv('{V}', {opts}) where DS_CARGO='Presidente' group by 1 order by v desc""").fetchall())
    con.execute(f"""create table v as
      select lower(SG_UF) uf, cast(CD_MUNICIPIO as int) mu, cast(NR_ZONA as int) zo, cast(NR_SECAO as int) se,
        sum(case when NM_VOTAVEL ilike '%BOLSONARO%' then cast(QT_VOTOS as bigint) else 0 end) F,
        sum(case when NM_VOTAVEL ilike 'LUIZ IN%' then cast(QT_VOTOS as bigint) else 0 end) L,
        sum(case when NM_VOTAVEL ilike '%CAIADO%' then cast(QT_VOTOS as bigint) else 0 end) Ca,
        sum(case when NM_VOTAVEL ilike '%CURY%' then cast(QT_VOTOS as bigint) else 0 end) Cu,
        sum(case when NM_VOTAVEL ilike 'RENAN%' then cast(QT_VOTOS as bigint) else 0 end) Re,
        sum(case when cast(NR_VOTAVEL as int) not in (95, 96) then cast(QT_VOTOS as bigint) else 0 end) valid
      from read_csv('{V}', {opts}) where DS_CARGO='Presidente' group by 1,2,3,4""")
    con.execute(f"""create table d as
      select lower(SG_UF) uf, cast(CD_MUNICIPIO as int) mu, cast(NR_ZONA as int) zo, cast(NR_SECAO as int) se,
        sum(cast(QT_APTOS as bigint)) aptos, sum(cast(QT_COMPARECIMENTO as bigint)) comp
      from read_csv('{DET}', {opts}) where DS_CARGO='Presidente' group by 1,2,3,4""")
    con.execute(f"copy (select * from v join d using (uf, mu, zo, se)) to '{R1P}' (format parquet)")
    print("R1 secciones:", con.execute(f"select count(*), sum(aptos), sum(F), sum(L) from '{R1P}'").fetchone())

bu = [json.loads(l) for l in open(f"{D}/bu/bu_r2.jsonl")]
con.execute("create or replace table r2 (uf varchar, mu int, zo int, se int, aptos2 int, comp2 int, F2 int, L2 int, B2 int, N2 int)")
con.executemany("insert into r2 values (?,?,?,?,?,?,?,?,?,?)",
                [(b["uf"], int(b["mu"]), int(b["zo"]), int(b["se"]), b["aptos"], b["comp"], b["F"], b["L"], b["B"], b["N"]) for b in bu])
j = con.execute(f"select * from '{R1P}' join r2 using (uf, mu, zo, se) where aptos > 0 and aptos2 > 0").df()
# same voter roll check: drop sections whose electorate changed a lot (merged/split sections)
ratio = j.aptos2 / j.aptos
j = j[(ratio > 0.9) & (ratio < 1.1)]
print(f"R2 boletines {len(bu)} · cruzadas {len(j)}")
E1, E2 = j.aptos.values.astype(float), j.aptos2.values.astype(float)
otros = j.valid - j.F - j.L - j.Ca - j.Cu - j.Re
bn1 = j.comp - j.valid
X = np.c_[j.F, j.L, j.Ca, j.Cu, j.Re, otros, bn1, j.aptos - j.comp] / E1[:, None]
Y = np.c_[j.F2, j.L2, j.B2 + j.N2, j.aptos2 - j.comp2] / E2[:, None]
ok = (X.min(1) >= 0) & (Y.min(1) >= 0)
np.savez(f"{D}/units_sec.npz", X=X[ok], Y=Y[ok], N=E2[ok], uf=j.uf.values[ok])
print("unidades válidas:", ok.sum(), "| check R2 share Lula en muestra:",
      round(float(j.L2[ok].sum() / (j.L2[ok].sum() + j.F2[ok].sum())) * 100, 2))
