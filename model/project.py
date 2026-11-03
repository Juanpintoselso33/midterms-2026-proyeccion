"""Proyección en vivo de las midterms 2026 (Senado, gobernaciones y Cámara).

Cada carrera se modela entre sus dos candidatos principales: X (el principal no republicano:
demócrata, o un independiente cuando es el que compite) e Y (el republicano principal; si no
hay, el siguiente más votado). Se modela la proporción y = X / (X + Y) en logit:

    logit y[u,t] = logit b[u] + rho0[r] + n_nat + n_state[s] + n_race[r] + d[s,t]
                   + f[s]·bias[s] + e[u]

  b[u]      base histórica de la unidad (presidencial 2024 por condado o pedazo de distrito)
  rho0[r]   prior de la carrera según su calificación (solid/likely/lean/tossup)
  n_nat     error nacional compartido por todas las carreras (lo que aprende el este se
            transmite al oeste)
  n_state   error estatal compartido por las carreras del mismo estado
  n_race    error propio de la carrera
  d[s,t]    efecto del tipo de voto (anticipado, correo, día de elección, provisional)
  bias[s]   sesgo del orden de conteo del estado: sólo afecta a lo ya contado, con peso f[s] =
            fracción que falta contar; no se proyecta a los votos pendientes
  e[u]      desvío propio de la unidad, integrado como varianza extra de sus observaciones

Se estima por mínimos cuadrados ponderados penalizados (los priors entran como
pseudo-observaciones) y se simula con la covarianza posterior completa más shocks sobre los
votos pendientes. Con eso salen las probabilidades de victoria, de balotaje (umbral del 50%)
y de control de cada cámara, contando las bancas por bancada (King y Sanders con los
demócratas).

Uso:  uv run --with numpy --with scipy --with pandas model/project.py [--date 2026-11-03]
"""
import argparse, json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TYPES = ("advance", "absentee_mail", "election_day_in_person", "provisional")

# Calificación -> (mínimo, máximo de la proporción bipartidaria D, sd del prior de carrera en
# logit). En las competitivas manda el centro del rango; en las seguras/probables, la base
# histórica recortada al rango.
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
# Voto presidencial 2024, proporción bipartidaria D (Harris 48,3 – Trump 49,8): referencia para
# trasladar la encuesta nacional al resultado presidencial de cada distrito.
PRES24_D = 48.3 / (48.3 + 49.8)
POLL_SD = ((10, 0.09), (3, 0.11), (0, 0.14))  # cantidad de encuestas -> sd del prior (logit)


def load_polls(path=None):
    """Prior desde encuestas (research/previa_encuestas.json): por carrera de Senado/gobernación
    la proporción bipartidaria del candidato no republicano, y el desvío nacional en logit.
    En cada estado manda el promedio con más encuestas; una encuesta suelta, sólo si no hay otro."""
    path = Path(path or ROOT / "research" / "previa_encuestas.json")
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    races = {}
    for r in d.get("races", []):
        ind = r.get("other") is not None and (r.get("D") is None or r["other"] > r["D"])
        x, name = (r["other"], r.get("other_name")) if ind else (r.get("D"), r.get("D_name"))
        if x is None or not r.get("R"):
            continue
        k, n = (r["state"], r["office"]), r.get("n_polls") or 5
        if k in races and races[k]["n"] >= n:
            continue
        races[k] = dict(p=x / (x + r["R"]), n=n, name=str(name or "").lower(), sd=next(sd for lim, sd in POLL_SD if n >= lim))
    gb = [g["D"] / (g["D"] + g["R"]) for g in d.get("generic_ballot", []) if g.get("D") and g.get("R")]
    swing = float(logit(np.mean(gb)) - logit(PRES24_D)) if gb else 0.0
    return dict(races=races, swing=swing)


POLLS = None  # se carga en main() sólo para la elección de 2026; el ensayo de 2024 no lo usa


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


def shock_curve(f):
    """Peso del shock sobre los votos QUE FALTAN según la fracción no escrutada f.

    Sin votos (f=1) vale 0 porque la incertidumbre ya está en el prior; aparece completo con
    los primeros votos. No se multiplica por f: el shock se aplica sólo a los votos pendientes,
    así que su efecto sobre el total ya se achica solo a medida que se cuenta.
    """
    return 1 - np.exp(-(1 - f) / 0.03)


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


NUMERIC = (["eevp", "expected", "total", "hist_dem", "hist_rep", "X", "Y", "win_threshold"]
           + [f"{p}_{t}" for p in "XYT" for t in TYPES] + [f"exp_{t}" for t in TYPES])


def load(date, units_csv=None, base_year=None):
    units_csv = units_csv or ROOT / f"data/live/{date}/units.csv"
    df = pd.read_csv(units_csv, dtype=str, keep_default_na=False)
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
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


VOTE_COLS = ["X", "Y", "total", "expected"] + [f"{p}_{t}" for p in "XYT" for t in TYPES] + [f"exp_{t}" for t in TYPES]


def pick_units(df):
    """Un único nivel geográfico por carrera, sin solapamientos, más una unidad residual con
    lo que la fila estatal tenga y el nivel elegido no cubra (no se pierde geografía)."""
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
        if best is None or not len(top) or best[1].expected.sum() < 0.5 * top.expected.sum():
            out.append(top.head(1) if len(top) else g.head(1))
            continue
        chosen = best[1]
        out.append(chosen)
        t = top.iloc[0]
        resid = {c: max(t[c] - chosen[c].sum(), 0) for c in VOTE_COLS}
        if resid["expected"] > 0.005 * t.expected or resid["total"] > 0.005 * max(t.total, 1):
            r = t.copy()
            for c, v in resid.items():
                r[c] = v
            r["unit_id"], r["level"], r["name"], r["fips"] = f"{t.unit_id}-resto", "resto", "Resto", ""
            r["eevp"] = min(100 * r.total / r.expected, 100) if r.expected > 0 else 0
            out.append(r.to_frame().T)
    u = pd.concat(out, ignore_index=True)
    for c in NUMERIC + ["b"]:
        u[c] = pd.to_numeric(u[c], errors="coerce").fillna(0)
    return u


# ---------------------------------------------------------------- cuerpo del modelo
class Model:
    def __init__(self, df):
        # 'US-G-H-...' es el voto popular nacional de la Cámara, no una banca
        df = df[~df.race_id.str.startswith("US-")]
        self.u = pick_units(df).reset_index(drop=True)
        self.races = self._races(df)
        self._index()

    def _races(self, df):
        top = df[df.level == "state"].groupby("race_id").first()
        rows = []
        for rid, g in self.u.groupby("race_id", sort=False):
            t = top.loc[rid] if rid in top.index else g.iloc[0]
            xp, yp = t.x_party, t.y_party
            # sin rival, o los dos del mismo partido: la banca ya tiene dueño
            fixed = (not t.y_id) or (xp == yp and xp in ("D", "R"))
            w = g.expected.where(g.expected > 0, 1)
            bbar = float(np.average(g.b, weights=w))
            rating = str(t.rating)
            lo, hi, sd = RATING.get(rating, (0.0, 1.0, 0.20))
            poll = POLLS["races"].get((t.state, t.office)) if POLLS and t.office in ("S", "G") else None
            if poll and xp != "R" and str(t.x_name).lower() in poll["name"]:
                p0, sd = poll["p"], poll["sd"]
            elif POLLS:
                p0 = float(np.clip(expit(logit(bbar) + POLLS["swing"]), lo, hi))
            elif rating.split("-")[0] in ("tossup", "tilt", "lean"):
                p0 = (lo + hi) / 2
            else:
                p0 = float(np.clip(bbar, lo, hi))
            won = [w_ for w_ in str(t.winner_ids).split(",") if w_]
            called = "X" if t.x_id in won else ("Y" if t.y_id in won else ("?" if won else ""))
            rows.append(dict(
                race_id=rid, office=t.office, state=t.state, seat=t.seat, rating=t.rating,
                x_id=t.x_id, y_id=t.y_id, x_name=t.x_name, y_name=t.y_name, x_party=xp, y_party=yp,
                x_caucus=t.x_caucus or xp, y_caucus=t.y_caucus or yp, fixed=bool(fixed),
                tabulation=t.tabulation, threshold=float(t.win_threshold or 0), race_type=t.race_type,
                call=t.call, called=called, rho0=float(logit(p0) - logit(bbar)), sd_race=sd, bbar=bbar,
                expected=float(t.expected), counted=float(t.total), eevp=float(t.eevp),
                X=float(t.X), Y=float(t.Y),
            ))
        return pd.DataFrame(rows).set_index("race_id")

    def _index(self):
        self.ri = {r: i for i, r in enumerate(self.races.index)}
        self.states = sorted(self.races.state.dropna().unique())
        self.si = {s: i for i, s in enumerate(self.states)}
        nr, ns, nt = len(self.ri), len(self.si), len(TYPES)
        # parámetros: nat | state | race | type(state,t) | bias(state)
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

    def _cells(self):
        """Celdas observadas (unidad, tipo) con votos contados para X o Y."""
        cells = []
        for i, r in self.u.iterrows():
            if self.races.at[r.race_id, "fixed"]:
                continue
            typed = [(TYPES.index(t), r[f"X_{t}"], r[f"Y_{t}"]) for t in TYPES]
            typed = [c for c in typed if c[1] + c[2] > 0]
            if typed and sum(b + a for _, b, a in typed) >= 0.95 * (r.X + r.Y):
                cells += [(i, t, b, a, len(typed)) for t, b, a in typed]
            elif r.X + r.Y > 0:
                cells.append((i, -1, r.X, r.Y, 1))
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
        for i, t, b, a, m in cells:
            u = self.u.loc[i]
            race = self.races.loc[u.race_id]
            n = a + b
            p = (b + 0.5) / (n + 1)
            v_bin = 1 / (n * p * (1 - p)) + SD["floor"] ** 2
            # el desvío de la unidad es uno solo para todas sus celdas por tipo: repartido en m
            # celdas, cada una lleva m veces su varianza (así no se cuenta m veces la misma info)
            v = v_bin + m * self.sd_unit[i] ** 2
            yv = logit(p) - logit(u.b) - race.rho0
            js = self._design(i, t, race)
            for j, xj in js:
                rhs[j] += xj * yv / v
                for k, xk in js:
                    A[j, k] += xj * xk / v
            obs.append((i, js, yv, v_bin))
        self.cov = np.linalg.inv(A)
        self.theta = self.cov @ rhs
        # desvío de cada unidad que ya reportó (BLUP), lineal en los coeficientes: e(θ) =
        # e_hat - g_u·(θ - θ̂). Se guarda g_u para que cada simulación use su propio θ.
        n_u = len(self.u)
        num_, den_ = np.zeros(n_u), np.zeros(n_u)
        self.g = [dict() for _ in range(n_u)]
        for i, js, yv, v_bin in obs:
            num_[i] += (yv - sum(self.theta[j] * x for j, x in js)) / v_bin
            den_[i] += 1 / v_bin
            for j, x in js:
                self.g[i][j] = self.g[i].get(j, 0) + x / v_bin
        s2 = self.sd_unit ** 2
        tot = den_ + 1 / s2
        self.e_hat = num_ / tot
        self.e_sd = np.sqrt(1 / tot)
        self.g = [{j: v / tot[i] for j, v in gi.items()} for i, gi in enumerate(self.g)]
        self.ncells = len(cells)
        return self

    # ------------------------------------------------------------ simulación
    def simulate(self, seed=2026):
        rng = np.random.default_rng(seed)
        ns, nr, nt = len(self.si), len(self.ri), len(TYPES)
        L = np.linalg.cholesky(self.cov + 1e-12 * np.eye(self.npar))
        dev = rng.standard_normal((K, self.npar)) @ L.T  # θ_draw - θ̂
        draw = self.theta[None, :] + dev

        R = self.races
        f_race = 1 - np.clip(R.eevp.values / 100, 0, 1)
        f_nat = 1 - min(R.counted.sum() / max(R.expected.sum(), 1), 1)
        g_race, g_nat = shock_curve(f_race), shock_curve(f_nat)
        g_state = shock_curve(self.f_state)

        nat_shock = rng.standard_normal(K) * SHOCK["nat"] * g_nat
        st_shock = rng.standard_normal((K, ns)) * SHOCK["state"] * g_state
        race_shock = rng.standard_normal((K, nr)) * SHOCK["race"] * g_race
        type_shock = rng.standard_normal((K, ns * nt)) * SHOCK["type"]
        untyped_shock = rng.standard_normal((K, ns)) * SHOCK["untyped"]
        turn_st = np.exp(rng.standard_normal((K, ns)) * SHOCK["turnout"] * 0.5)

        Xs, Ys, Os = np.zeros((K, nr)), np.zeros((K, nr)), np.zeros((K, nr))
        self.unit_proj = np.full(len(self.u), np.nan)
        for i, u in self.u.iterrows():
            ri, race = self.ri[u.race_id], R.loc[u.race_id]
            if race.fixed:
                continue
            si = self.si[race.state]
            other = max(u.total - u.X - u.Y, 0)
            Xs[:, ri] += u.X
            Ys[:, ri] += u.Y
            Os[:, ri] += other
            e_u = self.e_hat[i] + rng.standard_normal(K) * self.e_sd[i]
            if self.g[i]:
                js = list(self.g[i])
                e_u = e_u - dev[:, js] @ np.array([self.g[i][j] for j in js])
            base = (logit(u.b) + race.rho0 + draw[:, 0] + nat_shock
                    + draw[:, self.o_state + si] + st_shock[:, si]
                    + draw[:, self.o_race + ri] + race_shock[:, ri] + e_u)
            # votos que faltan: el total esperado manda; el desglose por tipo sólo reparte
            rem_total = max(u.expected - u.total, 0)
            rem_t = np.array([max(u[f"exp_{t}"] - u[f"T_{t}"], 0) for t in TYPES])
            if rem_t.sum() > 0 and rem_total > 0:
                rem_t = rem_t * rem_total / rem_t.sum()
                parts = [(rem_t[t], self.o_type + si * nt + t) for t in range(nt) if rem_t[t] > 0]
            else:
                parts = [(rem_total, None)]
            share_o = other / u.total if u.total > 0 else 0.02
            fu = 1 - min(u.eevp / 100, 1)
            unit_noise = rng.standard_normal(K) * SHOCK["unit"] * shock_curve(fu) * np.sqrt(1 - self.wu[i])
            tn = turn_st[:, si] * np.exp(rng.standard_normal(K) * SHOCK["turnout"] * 0.5)
            proj_x, proj_n = u.X, u.X + u.Y
            for n, j in parts:
                if n <= 0:
                    continue
                if j is not None:
                    x = base + unit_noise + draw[:, j] + type_shock[:, j - self.o_type]
                else:
                    x = base + unit_noise + untyped_shock[:, si] * shock_curve(fu)
                p = expit(x)
                two = n * (1 - share_o) * tn
                Xs[:, ri] += two * p
                Ys[:, ri] += two * (1 - p)
                Os[:, ri] += n * share_o * tn
                proj_x += float(np.median(two * p)); proj_n += float(np.median(two))
            self.unit_proj[i] = proj_x / proj_n if proj_n > 0 else np.nan

        share = Xs / np.maximum(Xs + Ys, 1)
        win_X = share > 0.5
        # umbral de mayoría (GA, VT gob., LA): si nadie llega al 50% del total hay balotaje.
        # El voto preferencial (AK, ME) ya se decide entre los dos finalistas: sin balotaje.
        tot = np.maximum(Xs + Ys + Os, 1)
        runoff = np.zeros((K, nr), dtype=bool)
        for rid, race in R.iterrows():
            ri = self.ri[rid]
            if race.fixed:
                win_X[:, ri] = True
                share[:, ri] = np.nan
            elif race.called:
                win_X[:, ri] = race.called == "X"
            elif race.threshold and race.tabulation != "ranked-choice":
                lead = np.maximum(Xs[:, ri], Ys[:, ri]) / tot[:, ri]
                runoff[:, ri] = lead * 100 < race.threshold
        self.share, self.win_X, self.runoff = share, win_X, runoff
        return self

    # ------------------------------------------------------------ salidas
    def _caucus_wins(self, idx):
        R = self.races.iloc[idx]
        w = self.win_X[:, idx]
        xc, yc = R.x_caucus.values, R.y_caucus.values
        seat = np.where(w, xc[None, :], yc[None, :])
        return seat

    def summary(self, control):
        R = self.races
        q = lambda a, p: float(np.nanquantile(a, p))
        races = []
        for rid, race in R.iterrows():
            ri = self.ri[rid]
            X, Y = race.X, race.Y
            s = self.share[:, ri]
            proj = not race.fixed
            races.append(dict(
                id=rid, office=race.office, state=race.state, seat=race.seat, rating=race.rating,
                x_name=race.x_name, y_name=race.y_name, x_party=race.x_party, y_party=race.y_party,
                x_caucus=race.x_caucus, y_caucus=race.y_caucus,
                side="D" if race.x_party == "D" else "O", same_party=bool(race.fixed),
                call=race.call, winner=race.called, eevp=race.eevp, counted=race.counted,
                expected=race.expected, tabulation=race.tabulation,
                partial_B=round(100 * X / (X + Y), 2) if X + Y else None,
                partial_R=round(100 * Y / (X + Y), 2) if X + Y else None,
                proj_B=round(100 * q(s, 0.5), 2) if proj else None,
                proj_R=round(100 * (1 - q(s, 0.5)), 2) if proj else None,
                ci90_B=[round(100 * q(s, 0.05), 2), round(100 * q(s, 0.95), 2)] if proj else None,
                ci90_R=[round(100 * (1 - q(s, 0.95)), 2), round(100 * (1 - q(s, 0.05)), 2)] if proj else None,
                p_B_win=round(float(self.win_X[:, ri].mean()), 4),
                p_runoff=round(float(self.runoff[:, ri].mean()), 4),
                runoff_risk=bool(race.threshold and race.tabulation != "ranked-choice"),
            ))
        out = dict(races=races, chambers={})
        for off, ctl in control.items():
            idx = [self.ri[r] for r in R.index if R.loc[r, "office"] == off]
            if not idx:
                continue
            seat = self._caucus_wins(idx)
            D = ctl["D_hold"] + (seat == "D").sum(1)
            I = ctl.get("I_hold", 0) + (seat == "I").sum(1)
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
            m = {}
            for _, r in gg.iterrows():
                part = r.X / (r.X + r.Y) if r.X + r.Y > 0 else None
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
    global POLLS
    POLLS = load_polls() if a.date.startswith("2026") else None
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
