"""Ensayo: reproduce la noche de 2024 (Senado + gobernaciones, por condado) y mide el modelo.

El conteo se simula por condado: cada estado arranca según su hora de cierre, los condados
grandes reportan más tarde y más despacio, y lo contado lleva un sesgo por estado (el efecto
del orden de los tipos de voto) que se desvanece a medida que se completa el conteo, de modo
que al final coincide exactamente con el resultado real. La base es la presidencial 2020
por condado y el prior, la calificación que el NYT tenía para cada carrera en 2024.

Uso: uv run --with numpy --with scipy --with pandas --with tqdm model/rehearse.py [--bias 0.04]
"""
import argparse, os, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project as P  # noqa: E402

ROOT = P.ROOT
# Orden aproximado de cierre (horas desde las 19 ET); el resto, 1 h por defecto.
CLOSE = {"IN": 0, "KY": 0, "VT": 0, "VA": 0, "GA": 0, "SC": 0, "FL": 0.5, "OH": 0.5, "NC": 0.5,
         "WV": 0.5, "PA": 1, "ME": 1, "MD": 1, "MA": 1, "NJ": 1, "CT": 1, "DE": 1, "MS": 1, "MO": 1,
         "TN": 1, "TX": 1.5, "MI": 1.5, "AZ": 2, "WI": 2, "MN": 2, "NY": 2, "NM": 2, "NE": 2,
         "ND": 2, "WY": 2, "UT": 3, "MT": 3, "NV": 3, "CA": 4, "WA": 4, "HI": 5, "AK": 6}


def synth(df, t, rng_state, bias):
    """Units a la hora t (0..10 h desde las 19 ET). Al terminar el conteo coincide con el real."""
    tau, dur, beta, noise = rng_state
    d = df.copy()
    f = np.clip((t - tau) / dur, 0, 1)
    X, Y = d.X.values.astype(float), d.Y.values.astype(float)
    Z = np.maximum(d.total.values.astype(float) - X - Y, 0)
    two = X + Y
    y = np.divide(X, two, out=np.full_like(two, 0.5), where=two > 0)
    # sesgo que se desvanece en los extremos (0 o 100%) y al completar el conteo
    yc = y + beta * (1 - f) * 4 * y * (1 - y)
    c2 = two * f
    d["X"] = np.round(c2 * yc)
    d["Y"] = np.round(c2) - d["X"]
    d["total"] = d.X + d.Y + np.round(Z * f)
    d["expected"] = np.round(d.expected * noise)
    d["eevp"] = np.where(d.expected > 0, np.minimum(100 * d.total / d.expected, 99), 0)
    d["call"] = "too_early"
    d["winner_ids"] = ""
    for c in [c for c in d.columns if any(c.endswith("_" + x) for x in P.TYPES) and c[0] in "XYT"]:
        d[c] = 0
    return d


def rebuild_state_rows(d):
    """Reagrega la fila estatal de cada carrera con el mismo nivel que usa el modelo."""
    chosen = P.pick_units(d)
    chosen = chosen[~chosen.level.isin(["state", "resto"])]
    agg = chosen.groupby("race_id")[["X", "Y", "total", "expected"]].sum()
    st = d.level == "state"
    for c in agg.columns:
        d.loc[st, c] = d.loc[st, "race_id"].map(agg[c]).fillna(d.loc[st, c])
    d.loc[st, "eevp"] = np.where(d.loc[st, "expected"] > 0,
                                 np.minimum(100 * d.loc[st, "total"] / d.loc[st, "expected"], 99), 0)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bias", type=float, default=0.04, help="sd del sesgo estatal por orden de conteo")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--dump-hour", type=float, default=None, help="guarda data.json/units.json de esa hora")
    ap.add_argument("--dump-dir", default=str(ROOT / "dash/sample"))
    a = ap.parse_args()
    df = P.load("2024-11-05", base_year=2020)
    df = df[df.office.isin(["S", "G"])].reset_index(drop=True)
    rng = np.random.default_rng(a.seed)
    size = df.expected.rank(pct=True).values
    tau = df.state.map(CLOSE).fillna(1).values + 0.3 + 1.5 * size * rng.uniform(0.3, 1, len(df))
    dur = 0.5 + 3 * size * rng.uniform(0.5, 1.5, len(df))
    sb = {s: rng.normal(0, a.bias) for s in df.state.unique()}
    beta = df.state.map(sb).values * rng.uniform(0.5, 1.5, len(df))
    noise = np.exp(rng.normal(0, 0.03, len(df)))
    state = (tau, dur, beta, noise)

    truth = {}
    for rid, g in df[df.level == "state"].groupby("race_id"):
        r = g.iloc[0]
        if r.X + r.Y > 0 and r.y_id:
            truth[rid] = r.X / (r.X + r.Y)

    rows = []
    hours = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]
    bar = tqdm(hours, desc="Ensayo 2024", unit="corte", goal="medir error y cobertura del modelo")
    bar.info(carreras=len(truth), sesgo=a.bias, base="pres 2020")
    for t in bar:
        bar.status(f"{t} h después de las 19 ET")
        d = rebuild_state_rows(synth(df, t, state, a.bias))
        d = d.assign(b=df.b.values)
        m = P.Model(d).fit().simulate()
        s = m.summary(P.control_from_raw("2024-11-05"))
        if a.dump_hour == t:
            import json
            dd = Path(a.dump_dir); dd.mkdir(parents=True, exist_ok=True)
            s["updated"] = f"ensayo 2024 · {t} h"
            (dd / "data.json").write_text(json.dumps(s, separators=(",", ":")))
            (dd / "units.json").write_text(json.dumps(m.map_units(), separators=(",", ":")))
        res = []
        for r in s["races"]:
            if r["same_party"] or r["id"] not in truth or r["proj_B"] is None:
                continue
            y = 100 * truth[r["id"]]
            res.append(dict(
                err=r["proj_B"] - y,
                naive=(r["partial_B"] - y) if r["partial_B"] is not None else np.nan,
                cover=r["ci90_B"][0] <= y <= r["ci90_B"][1],
                brier=(r["p_B_win"] - (y > 50)) ** 2,
                wrong_sure=(r["p_B_win"] > 0.95 and y < 50) or (r["p_B_win"] < 0.05 and y > 50),
                eevp=r["eevp"], id=r["id"], y=round(y, 2), proj=r["proj_B"], ci=r["ci90_B"], pw=r["p_B_win"],
            ))
        q = pd.DataFrame(res)
        row = dict(hora=t, escrutado=round(q.eevp.mean(), 1), mae_modelo=round(q.err.abs().mean(), 2),
                   mae_parcial=round(q.naive.abs().mean(), 2), cobertura90=round(q.cover.mean(), 3),
                   brier=round(q.brier.mean(), 4), seguras_erradas=int(q.wrong_sure.sum()))
        rows.append(row)
        bad = q[~q.cover].assign(ae=lambda x: x.err.abs()).sort_values("ae", ascending=False).head(6)
        print(f"--- {t}h fuera del IC:", "; ".join(f"{b.id[:8]} y={b.y} p={b.proj} {b.ci} pw={b.pw} e={b.eevp:.0f}" for b in bad.itertuples()), flush=True)
        bar.log(f"{t}h: {row['escrutado']}% · MAE {row['mae_modelo']} vs parcial {row['mae_parcial']} · cob {row['cobertura90']}")
    bar.close()
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    out.to_csv(ROOT / f"research/ensayo_2024_bias{a.bias}.csv", index=False)


if __name__ == "__main__":
    main()
