"""Proyección en vivo de las midterms 2026 (Senado, gobernaciones y Cámara).

Modelo (en logit de la proporción bipartidaria D/(D+R), o del principal no-republicano
cuando no hay demócrata):

    logit y[u,t] = logit b[u] + rho0[r] + n_nat + n_state[s] + n_race[r] + d[s,t] + e[u]

  b[u]      base histórica de la unidad (presidencial 2024 por condado o pedazo de distrito)
  rho0[r]   prior de la carrera: la calificación (solid/likely/lean/tossup) traducida a una
            proporción esperada, menos la base promedio de la carrera
  n_nat     error nacional compartido por todas las carreras (lo que aprende el este del país
            se transmite al oeste)
  n_state   error estatal compartido por las carreras del mismo estado
  n_race    error propio de la carrera
  d[s,t]    efecto del tipo de voto (anticipado, correo, día de elección, provisional) por estado
  e[u]      desvío propio de la unidad

Se estima por mínimos cuadrados ponderados penalizados (los priors entran como
pseudo-observaciones), con pesos binomiales más un piso de sobredispersión. Los votos que
faltan (esperados por AP - contados) se proyectan con el modelo, por unidad y tipo. La
incertidumbre se simula con shocks nacionales, estatales, de carrera, de tipo y de
participación escalados por la fracción no escrutada; con eso salen las probabilidades de
victoria y de control de cada cámara.

Uso:  uv run --with numpy --with scipy --with pandas model/project.py [--date 2026-11-03]
"""
import argparse, json, os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parent.parent
TYPES = ("advance", "absentee_mail", "election_day_in_person", "provisional")

# Calificación -> (mínimo, máximo de la proporción bipartidaria D, sd del prior de carrera en
# logit). La base histórica se recorta a ese rango: la calificación dice quién va adelante y
# por cuánto como máximo, no fija el resultado.
RATING = {
    "solid-dem": (0.57, 1.00, 0.20), "likely-dem": (0.53, 0.60, 0.13), "lean-dem": (0.51, 0.55, 0.10),
    "tilt-dem": (0.50, 0.53, 0.09), "tossup": (0.48, 0.52, 0.09), "tilt-rep": (0.47, 0.50, 0.09),
    "lean-rep": (0.45, 0.49, 0.10), "likely-rep": (0.40, 0.47, 0.13), "solid-rep": (0.00, 0.43, 0.20),
}
SD = dict(nat=0.08, state=0.06, type=0.15, unit=0.12, floor=0.02, bias=0.16)
# Shocks sobre los votos pendientes (logit). `untyped` cubre la diferencia entre lo contado y lo
# que falta cuando el feed no dice de qué tipo de voto es lo pendiente (correo tardío, etc.).
SHOCK = dict(nat=0.06, state=0.08, race=0.06, unit=0.10, turnout=0.08, type=0.10, untyped=0.22)
K = 2000


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


def num(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


# ---------------------------------------------------------------- carga y bases
def county_baseline(year):
    f = ROOT / f"data/base/pres2024_county/pres_{year}_county_medsl_clean.csv"
    b = pd.read_csv(f, dtype={"county_fips": str})
    b["fips"] = b["county_fips"].str.zfill(5)
    st = b.groupby("state_po")[["dem_votes", "rep_votes"]].sum()
    return (dict(zip(b["fips"], b["dem_votes"] / (b["dem_votes"] + b["rep_votes"]))),
            (st["dem_votes"] / st.sum(axis=1)).to_dict())


def district_baseline():
    f = ROOT / "data/base/cd_pres2024/pres2024_by_cd_2026maps_clean.csv"
    if not f.exists():
        return {}
    d = pd.read_csv(f)
    return dict(zip(d["district"], d["dem_share_2way_2024"]))


def load(date, units_csv=None, base_year=None):
    units_csv = units_csv or ROOT / f"data/live/{date}/units.csv"
    df = pd.read_csv(units_csv, dtype={"fips": str, "seat": str, "winner": str, "parties": str},
                     keep_default_na=False, na_values={"eevp": [""], "expected": [""]})
    df["fips"] = df["fips"].fillna("")
    cols = ["eevp", "expected", "total", "hist_dem", "hist_rep", "D", "R", "O"]
    cols += [f"{p}_{t}" for p in "DRO" for t in TYPES] + [f"exp_{t}" for t in TYPES]
    df = num(df, cols)
    base_year = base_year or (2024 if date >= "2025" else 2020)
    cmap, smap = county_baseline(base_year)
    dmap = district_baseline() if base_year == 2024 else {}

    def base(r):
        if r.hist_dem + r.hist_rep > 0:
            return r.hist_dem / (r.hist_dem + r.hist_rep)
        if r.level == "county" and r.fips in cmap:
            return cmap[r.fips]
        if r.office == "H" and r.level == "state":
            k = f"{r.state}-{int(r.seat):02d}" if str(r.seat).isdigit() else f"{r.state}-AL"
            if k in dmap:
                return dmap[k]
        return smap.get(r.state, 0.5)

    df["b"] = df.apply(base, axis=1)
    return df


def pick_units(df):
    """Un único nivel geográfico por carrera, sin solapamientos."""
    out = []
    for rid, g in df.groupby("race_id", sort=False):
        top = g[g.level == "state"]
        sub = g[~g.level.isin(["state", "national"])]
        best = None
        if len(sub):
            target = top.expected.sum() if len(top) else None
            for lvl, gl in sub.groupby("level"):
                gap = abs(gl.expected.sum() - target) if target else -len(gl)
                if best is None or gap < best[0]:
                    best = (gap, gl)
        if best is not None and (not len(top) or best[1].expected.sum() > 0.9 * top.expected.sum()):
            out.append(best[1])
        else:
            out.append(top.head(1))
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------- cuerpo del modelo
def shock_curve(f):
    """Peso del shock sobre los votos QUE FALTAN según la fracción no escrutada f.

    Sin votos (f=1) vale 0 porque la incertidumbre ya está en el prior; aparece completo con
    los primeros votos. No se multiplica por f: el shock se aplica sólo a los votos pendientes,
    así que su efecto sobre el total ya se achica solo a medida que se cuenta.
    """
    return 1 - np.exp(-(1 - f) / 0.03)


class Model:
    def __init__(self, df):
        self.u = pick_units(df).reset_index(drop=True)
        self.races = self._races(df)
        self._index()

    def _races(self, df):
        top = df[df.level == "state"].groupby("race_id").first()
        rows = []
        for rid, g in self.u.groupby("race_id", sort=False):
            t = top.loc[rid] if rid in top.index else g.iloc[0]
            parties = str(t.get("parties", "") or "")
            # lado no republicano: el que más votos tiene; sin votos, el demócrata si hay
            if g.D.sum() + g.O.sum() > 0 and "O" in parties:
                side = "D" if g.D.sum() >= g.O.sum() else "O"
            else:
                side = "D" if "D" in parties else ("O" if "O" in parties else "D")
            same = bool(parties) and len(set(parties)) == 1 and parties[0] in "DR"
            w = g.expected.where(g.expected > 0, 1)
            bbar = float(np.average(g.b, weights=w))
            lo, hi, sd = RATING.get(str(t.get("rating")), (0.0, 1.0, 0.20))
            # competitivas: manda el centro de la calificación (la base de 2024 trae el clima de
            # ese año); seguras/probables: la base histórica recortada al rango.
            rating = str(t.get("rating"))
            if rating.split("-")[0] in ("tossup", "tilt", "lean"):
                p0 = (lo + hi) / 2
            else:
                p0 = float(np.clip(bbar, lo, hi))
            rows.append(dict(
                race_id=rid, office=t.office, state=t.state, seat=t.seat, rating=t.get("rating"),
                side=side, same_party=same, parties=parties, race_type=t.get("race_type"),
                tabulation=t.get("tabulation"), call=t.get("call"), winner=str(t.get("winner") or ""),
                rho0=float(logit(p0) - logit(bbar)), sd_race=sd, bbar=bbar,
                expected=float(t.expected), counted=float(t.total), eevp=float(t.eevp),
            ))
        return pd.DataFrame(rows).set_index("race_id")

    def _index(self):
        self.ri = {r: i for i, r in enumerate(self.races.index)}
        self.states = sorted(self.races.state.dropna().unique())
        self.si = {s: i for i, s in enumerate(self.states)}
        nr, ns, nt = len(self.ri), len(self.si), len(TYPES)
        # parámetros: nat | state | race | type(state,t) | bias(state). El desvío de cada unidad
        # no es un parámetro: entra como varianza extra de su observación (efecto aleatorio
        # integrado). `bias` es el sesgo del orden de conteo de cada estado: afecta sólo a lo ya
        # contado, con peso igual a la fracción que falta contar, y no se proyecta a lo pendiente.
        self.o_state, self.o_race, self.o_type = 1, 1 + ns, 1 + ns + nr
        self.o_bias = self.o_type + ns * nt
        self.npar = self.o_bias + ns
        R = self.races
        e = R.groupby("state").expected.sum()
        c = R.groupby("state").counted.sum()
        fs = (1 - (c / e.where(e > 0, 1)).clip(0, 1)).to_dict()
        self.f_state = np.array([fs.get(s, 1.0) for s in self.states])
        tot = self.u.groupby("race_id").expected.transform("sum").where(lambda x: x > 0, 1)
        self.wu = (self.u.expected / tot).clip(0, 1).values
        self.sd_unit = np.maximum(SD["unit"] * np.sqrt(1 - self.wu), 1e-3)

    def _B(self, u, side):
        return u.D if side == "D" else u.O

    def _cells(self):
        """Celdas observadas (unidad, tipo) con votos contados para los dos lados."""
        cells = []
        for i, r in self.u.iterrows():
            race = self.races.loc[r.race_id]
            if race.same_party:
                continue
            B = self._B(r, race.side)
            typed = [(t, r[f"{race.side}_{t}"], r[f"R_{t}"]) for t in TYPES]
            if sum(b + a for _, b, a in typed) >= 0.95 * (B + r.R) > 0:
                for t, b, a in typed:
                    if a + b > 0:
                        cells.append((i, TYPES.index(t), b, a))
            elif B + r.R > 0:
                cells.append((i, -1, B, r.R))
        return cells

    def _design(self, i, t, race):
        si = self.si[race.state]
        js = [(0, 1.0), (self.o_state + si, 1.0), (self.o_race + self.ri[self.u.at[i, "race_id"]], 1.0),
              (self.o_bias + si, float(self.f_state[si]))]
        if t >= 0:
            js.append((self.o_type + si * len(TYPES) + t, 1.0))
        return js

    def fit(self):
        cells = self._cells()
        prior = np.zeros(self.npar)
        prior[0] = SD["nat"]
        prior[self.o_state:self.o_race] = SD["state"]
        prior[self.o_race:self.o_type] = self.races.sd_race.values
        prior[self.o_type:self.o_bias] = SD["type"]
        prior[self.o_bias:] = SD["bias"]
        A = np.diag(1 / prior ** 2)
        rhs = np.zeros(self.npar)
        obs = []
        for i, t, b, a in cells:
            u = self.u.loc[i]
            race = self.races.loc[u.race_id]
            n = a + b
            p = (b + 0.5) / (n + 1)
            v_bin = 1 / (n * p * (1 - p)) + SD["floor"] ** 2
            v = v_bin + self.sd_unit[i] ** 2
            yv = logit(p) - logit(u.b) - race.rho0
            js = self._design(i, t, race)
            for j, xj in js:
                rhs[j] += xj * yv / v
                for k, xk in js:
                    A[j, k] += xj * xk / v
            obs.append((i, js, yv, v_bin))
        self.cov = np.linalg.inv(A)
        self.theta = self.cov @ rhs
        # desvío propio de cada unidad que ya reportó (BLUP), para proyectar lo que le falta
        num_, den_ = np.zeros(len(self.u)), np.zeros(len(self.u))
        for i, js, yv, v_bin in obs:
            num_[i] += (yv - sum(self.theta[j] * x for j, x in js)) / v_bin
            den_[i] += 1 / v_bin
        s2 = self.sd_unit ** 2
        self.e_hat = num_ / (den_ + 1 / s2)
        self.e_sd = np.sqrt(1 / (den_ + 1 / s2))
        self.ncells = len(cells)
        return self

    # ------------------------------------------------------------ simulación
    def simulate(self, seed=2026):
        rng = np.random.default_rng(seed)
        ns, nr, nt = len(self.si), len(self.ri), len(TYPES)
        L = np.linalg.cholesky(self.cov + 1e-12 * np.eye(self.npar))
        draw = self.theta[None, :] + rng.standard_normal((K, self.npar)) @ L.T

        R = self.races
        f_race = 1 - np.clip(R.eevp.values / 100, 0, 1)
        exp_by_state = R.groupby("state").expected.sum()
        cnt_by_state = R.groupby("state").counted.sum()
        f_state = (1 - (cnt_by_state / exp_by_state.where(exp_by_state > 0, 1)).clip(0, 1)).to_dict()
        f_nat = 1 - min(R.counted.sum() / max(R.expected.sum(), 1), 1)
        g_race, g_nat = shock_curve(f_race), shock_curve(f_nat)
        g_state = np.array([shock_curve(f_state.get(s, 1)) for s in self.states])

        nat_shock = rng.standard_normal(K) * SHOCK["nat"] * g_nat
        st_shock = rng.standard_normal((K, ns)) * SHOCK["state"] * g_state
        race_shock = rng.standard_normal((K, nr)) * SHOCK["race"] * g_race
        type_shock = rng.standard_normal((K, ns * nt)) * SHOCK["type"]
        untyped_shock = rng.standard_normal((K, ns)) * SHOCK["untyped"]
        turn_st = np.exp(rng.standard_normal((K, ns)) * SHOCK["turnout"] * 0.5)

        Bsim = np.zeros((K, nr))
        Asim = np.zeros((K, nr))
        self.unit_proj = np.full(len(self.u), np.nan)
        for i, u in self.u.iterrows():
            ri, race = self.ri[u.race_id], R.loc[u.race_id]
            if race.same_party:
                continue
            si = self.si[race.state]
            B = self._B(u, race.side)
            Bsim[:, ri] += B
            Asim[:, ri] += u.R
            e_u = self.e_hat[i] + rng.standard_normal(K) * self.e_sd[i]
            base = (logit(u.b) + race.rho0 + draw[:, 0] + nat_shock
                    + draw[:, self.o_state + si] + st_shock[:, si]
                    + draw[:, self.o_race + ri] + race_shock[:, ri] + e_u)
            exp_t = np.array([u[f"exp_{t}"] for t in TYPES])
            got_t = np.array([u[f"{race.side}_{t}"] + u[f"R_{t}"] + u[f"O_{t}"] for t in TYPES])
            if exp_t.sum() > 0:
                rem = np.maximum(exp_t - got_t, 0)
                parts = [(rem[t], self.o_type + si * nt + t) for t in range(nt) if rem[t] > 0]
            else:
                parts = [(max(u.expected - u.total, 0), None)]
            other = u.total - B - u.R
            share_o = other / u.total if u.total > 0 else 0.02
            fu = 1 - min(u.eevp / 100, 1)
            unit_noise = rng.standard_normal(K) * SHOCK["unit"] * shock_curve(fu) * np.sqrt(1 - self.wu[i])
            tn = turn_st[:, si] * np.exp(rng.standard_normal(K) * SHOCK["turnout"] * 0.5)
            proj_b, proj_n = B, B + u.R
            for n, j in parts:
                if n <= 0:
                    continue
                if j is not None:
                    x = base + unit_noise + draw[:, j] + type_shock[:, j - self.o_type]
                else:
                    x = base + unit_noise + untyped_shock[:, si] * shock_curve(fu)
                p = expit(x)
                two = n * (1 - share_o) * tn
                Bsim[:, ri] += two * p
                Asim[:, ri] += two * (1 - p)
                proj_b += float(np.median(two * p)); proj_n += float(np.median(two))
            self.unit_proj[i] = proj_b / proj_n if proj_n > 0 else np.nan

        share = Bsim / np.maximum(Bsim + Asim, 1)
        win_B = share > 0.5
        for rid, race in R.iterrows():
            ri = self.ri[rid]
            if race.same_party:
                win_B[:, ri] = race.parties[0] != "R"
            elif race.winner:
                win_B[:, ri] = race.winner[0] != "R"
        self.share, self.win_B = share, win_B
        return self

    # ------------------------------------------------------------ salidas
    def summary(self, control):
        R = self.races
        q = lambda a, p: float(np.quantile(a, p))
        races = []
        for rid, race in R.iterrows():
            ri = self.ri[rid]
            g = self.u[self.u.race_id == rid]
            Bc = float(g.D.sum() if race.side == "D" else g.O.sum())
            Ac = float(g.R.sum())
            s = self.share[:, ri]
            races.append(dict(
                id=rid, office=race.office, state=race.state, seat=race.seat, rating=race.rating,
                side=race.side, same_party=race.same_party, parties=race.parties, call=race.call,
                winner=race.winner, eevp=race.eevp, counted=race.counted, expected=race.expected,
                partial_B=round(100 * Bc / (Bc + Ac), 2) if Bc + Ac else None,
                partial_R=round(100 * Ac / (Bc + Ac), 2) if Bc + Ac else None,
                proj_B=round(100 * q(s, 0.5), 2), proj_R=round(100 * (1 - q(s, 0.5)), 2),
                ci90_B=[round(100 * q(s, 0.05), 2), round(100 * q(s, 0.95), 2)],
                ci90_R=[round(100 * (1 - q(s, 0.95)), 2), round(100 * (1 - q(s, 0.05)), 2)],
                p_B_win=round(float(self.win_B[:, ri].mean()), 4),
                runoff_risk=bool(race.state == "GA" and race.office in ("S", "G")),
            ))
        out = dict(races=races, chambers={})
        for off, ctl in control.items():
            idx = [self.ri[r] for r in R.index if R.loc[r, "office"] == off]
            if not idx:
                continue
            sideD = np.array([R.iloc[i].side == "D" for i in idx])
            wins = self.win_B[:, idx]
            D = ctl["D_hold"] + (wins & sideD).sum(1)
            I = ctl.get("I_hold", 0) + (wins & ~sideD).sum(1)
            Rr = ctl["total"] - D - I
            vals, cnt = np.unique(D, return_counts=True)
            out["chambers"][off] = dict(
                total=ctl["total"], D_needs=ctl["D_needs"], R_needs=ctl["R_needs"],
                p_D=round(float((D >= ctl["D_needs"]).mean()), 4),
                p_R=round(float((Rr >= ctl["R_needs"]).mean()), 4),
                D_med=int(np.median(D)), R_med=int(np.median(Rr)), I_med=int(np.median(I)),
                D_ci90=[int(q(D, 0.05)), int(q(D, 0.95))], R_ci90=[int(q(Rr, 0.05)), int(q(Rr, 0.95))],
                dist={int(v): round(c / K, 4) for v, c in zip(vals, cnt)},
            )
        return out

    def map_units(self):
        g = self.u.assign(proj=self.unit_proj)
        out = {}
        for rid, gg in g.groupby("race_id"):
            side = self.races.loc[rid, "side"]
            m = {}
            for _, r in gg.iterrows():
                B = r.D if side == "D" else r.O
                part = B / (B + r.R) if B + r.R > 0 else None
                m[r.unit_id] = dict(
                    f=r.fips, n=r["name"], e=r.eevp,
                    p=None if part is None else round(100 * part, 1),
                    j=None if np.isnan(r.proj) else round(100 * r.proj, 1),
                    b=round(100 * r.b, 1),
                )
            out[rid] = m
        return out


def control_from_raw(date):
    """Bancas que no se votan y umbrales, desde partyControlData del NYT."""
    out = {}
    for off, fn in (("S", "results-senate"), ("H", "results-house")):
        f = ROOT / f"data/live/{date}/raw/{fn}.json"
        if not f.exists():
            continue
        o = json.loads(f.read_bytes())["partyControlData"]["results"][0]["offices"][off]
        pb = o["party_balance"]
        out[off] = dict(total=o["total"], D_hold=pb["DEM"]["no_election"], I_hold=pb["OTH"]["no_election"],
                        D_needs=o["to_win"]["DEM"], R_needs=o["to_win"]["GOP"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-03")
    ap.add_argument("--out", default=str(ROOT / "dash"))
    a = ap.parse_args()
    t0 = datetime.now()
    m = Model(load(a.date)).fit().simulate()
    s = m.summary(control_from_raw(a.date))
    s["updated"] = t0.strftime("%Y-%m-%d %H:%M:%S")
    s["cells"] = m.ncells
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, obj in (("data.json", s), ("units.json", m.map_units())):
        tmp = out / (name + ".tmp")
        tmp.write_text(json.dumps(obj, separators=(",", ":")))
        tmp.replace(out / name)
    hist = out / "history.json"
    h = json.loads(hist.read_text()) if hist.exists() else []
    h.append(dict(t=t0.strftime("%H:%M:%S"), **{k: {kk: v[kk] for kk in ("p_D", "p_R", "D_med", "R_med", "D_ci90", "R_ci90")}
                                                for k, v in s["chambers"].items()}))
    hist.write_text(json.dumps(h, separators=(",", ":")))
    for k, v in s["chambers"].items():
        print(f"{k}: P(D)={v['p_D']:.3f} P(R)={v['p_R']:.3f} D={v['D_med']} {v['D_ci90']} R={v['R_med']} I={v['I_med']}")
    print(f"{len(s['races'])} carreras · {m.ncells} celdas · {(datetime.now()-t0).total_seconds():.1f}s")


if __name__ == "__main__":
    main()
