Reading additional input from stdin...
OpenAI Codex v0.163.0
--------
workdir: /Users/juan/dev/midterms-2026-proyeccion
model: gpt-6.1-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: medium
reasoning summaries: none
session id: 01a18dad-93b0-7553-a681-e13ab4e4b736
--------
user
Review model/project.py, model/fetch_nyt.py and model/rehearse.py for correctness bugs. Context: live US midterm 2026 projection from NYT/AP JSON (see research/fuente_principal_nyt.md). Focus on: wrong party/side handling (independents, same-party races, called races), double counting of reporting units across levels, vote-type remaining-vote math, posterior/simulation errors, seat/chamber arithmetic (Senate holdovers, VP tiebreak R, House 218), and anything that would silently produce wrong numbers on election night. List concrete findings with file:line and a failure scenario; skip style.
warning: `--dangerously-bypass-hook-trust` is enabled. Enabled hooks may run without review for this invocation.
warning: `--dangerously-bypass-hook-trust` is enabled. Enabled hooks may run without review for this invocation.
hook: SessionStart
hook: SessionStart
2026-10-30T16:38:48.136111Z ERROR codex_rmcp_client::oauth::refresh_transaction: error=failed to refresh OAuth tokens for server tavily-remote: OAuth refresh token was rejected: Server returned error response: invalid_grant: refresh token does not exist
hook: SessionStart Completed
hook: SessionStart Completed
hook: UserPromptSubmit
hook: UserPromptSubmit
hook: UserPromptSubmit Completed
hook: UserPromptSubmit Completed
codex
Voy a leer la guía del proyecto y revisar los tres archivos, siguiendo cómo los datos de NYT/AP llegan a las proyecciones de votos y bancas.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "pwd && git status --short && cat CLAUDE.md && rg --files -g AGENTS.md -g 'model/project.py' -g 'model/fetch_nyt.py' -g 'model/rehearse.py' -g 'research/fuente_principal_nyt.md'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 0ms:
/Users/juan/dev/midterms-2026-proyeccion
?? research/reviews/
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
AGENTS.md
model/project.py
model/rehearse.py
model/fetch_nyt.py
research/fuente_principal_nyt.md

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc 'cat AGENTS.md && nl -ba model/project.py && nl -ba model/fetch_nyt.py && nl -ba model/rehearse.py && cat research/fuente_principal_nyt.md' in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 0ms:
# Instrucciones

Read `CLAUDE.md` first; it is the canonical operating guide.
     1	"""Proyección en vivo de las midterms 2026 (Senado, gobernaciones y Cámara).
     2	
     3	Modelo (en logit de la proporción bipartidaria D/(D+R), o del principal no-republicano
     4	cuando no hay demócrata):
     5	
     6	    logit y[u,t] = logit b[u] + rho0[r] + n_nat + n_state[s] + n_race[r] + d[s,t] + e[u]
     7	
     8	  b[u]      base histórica de la unidad (presidencial 2024 por condado o pedazo de distrito)
     9	  rho0[r]   prior de la carrera: la calificación (solid/likely/lean/tossup) traducida a una
    10	            proporción esperada, menos la base promedio de la carrera
    11	  n_nat     error nacional compartido por todas las carreras (lo que aprende el este del país
    12	            se transmite al oeste)
    13	  n_state   error estatal compartido por las carreras del mismo estado
    14	  n_race    error propio de la carrera
    15	  d[s,t]    efecto del tipo de voto (anticipado, correo, día de elección, provisional) por estado
    16	  e[u]      desvío propio de la unidad
    17	
    18	Se estima por mínimos cuadrados ponderados penalizados (los priors entran como
    19	pseudo-observaciones), con pesos binomiales más un piso de sobredispersión. Los votos que
    20	faltan (esperados por AP - contados) se proyectan con el modelo, por unidad y tipo. La
    21	incertidumbre se simula con shocks nacionales, estatales, de carrera, de tipo y de
    22	participación escalados por la fracción no escrutada; con eso salen las probabilidades de
    23	victoria y de control de cada cámara.
    24	
    25	Uso:  uv run --with numpy --with scipy --with pandas model/project.py [--date 2026-11-03]
    26	"""
    27	import argparse, json, os
    28	from datetime import datetime
    29	from pathlib import Path
    30	
    31	import numpy as np
    32	import pandas as pd
    33	from scipy import sparse
    34	from scipy.sparse.linalg import spsolve
    35	
    36	ROOT = Path(__file__).resolve().parent.parent
    37	TYPES = ("advance", "absentee_mail", "election_day_in_person", "provisional")
    38	
    39	# Calificación -> (mínimo, máximo de la proporción bipartidaria D, sd del prior de carrera en
    40	# logit). La base histórica se recorta a ese rango: la calificación dice quién va adelante y
    41	# por cuánto como máximo, no fija el resultado.
    42	RATING = {
    43	    "solid-dem": (0.57, 1.00, 0.20), "likely-dem": (0.53, 0.60, 0.13), "lean-dem": (0.51, 0.55, 0.10),
    44	    "tilt-dem": (0.50, 0.53, 0.09), "tossup": (0.48, 0.52, 0.09), "tilt-rep": (0.47, 0.50, 0.09),
    45	    "lean-rep": (0.45, 0.49, 0.10), "likely-rep": (0.40, 0.47, 0.13), "solid-rep": (0.00, 0.43, 0.20),
    46	}
    47	SD = dict(nat=0.08, state=0.06, type=0.15, unit=0.12, floor=0.02, bias=0.16)
    48	# Shocks sobre los votos pendientes (logit). `untyped` cubre la diferencia entre lo contado y lo
    49	# que falta cuando el feed no dice de qué tipo de voto es lo pendiente (correo tardío, etc.).
    50	SHOCK = dict(nat=0.06, state=0.08, race=0.06, unit=0.10, turnout=0.08, type=0.10, untyped=0.22)
    51	K = 2000
    52	
    53	
    54	def logit(p):
    55	    p = np.clip(p, 1e-4, 1 - 1e-4)
    56	    return np.log(p / (1 - p))
    57	
    58	
    59	def expit(x):
    60	    return 1 / (1 + np.exp(-x))
    61	
    62	
    63	def num(df, cols):
    64	    for c in cols:
    65	        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    66	    return df
    67	
    68	
    69	# ---------------------------------------------------------------- carga y bases
    70	def county_baseline(year):
    71	    f = ROOT / f"data/base/pres2024_county/pres_{year}_county_medsl_clean.csv"
    72	    b = pd.read_csv(f, dtype={"county_fips": str})
    73	    b["fips"] = b["county_fips"].str.zfill(5)
    74	    st = b.groupby("state_po")[["dem_votes", "rep_votes"]].sum()
    75	    return (dict(zip(b["fips"], b["dem_votes"] / (b["dem_votes"] + b["rep_votes"]))),
    76	            (st["dem_votes"] / st.sum(axis=1)).to_dict())
    77	
    78	
    79	def district_baseline():
    80	    f = ROOT / "data/base/cd_pres2024/pres2024_by_cd_2026maps_clean.csv"
    81	    if not f.exists():
    82	        return {}
    83	    d = pd.read_csv(f)
    84	    return dict(zip(d["district"], d["dem_share_2way_2024"]))
    85	
    86	
    87	def load(date, units_csv=None, base_year=None):
    88	    units_csv = units_csv or ROOT / f"data/live/{date}/units.csv"
    89	    df = pd.read_csv(units_csv, dtype={"fips": str, "seat": str, "winner": str, "parties": str},
    90	                     keep_default_na=False, na_values={"eevp": [""], "expected": [""]})
    91	    df["fips"] = df["fips"].fillna("")
    92	    cols = ["eevp", "expected", "total", "hist_dem", "hist_rep", "D", "R", "O"]
    93	    cols += [f"{p}_{t}" for p in "DRO" for t in TYPES] + [f"exp_{t}" for t in TYPES]
    94	    df = num(df, cols)
    95	    base_year = base_year or (2024 if date >= "2025" else 2020)
    96	    cmap, smap = county_baseline(base_year)
    97	    dmap = district_baseline() if base_year == 2024 else {}
    98	
    99	    def base(r):
   100	        if r.hist_dem + r.hist_rep > 0:
   101	            return r.hist_dem / (r.hist_dem + r.hist_rep)
   102	        if r.level == "county" and r.fips in cmap:
   103	            return cmap[r.fips]
   104	        if r.office == "H" and r.level == "state":
   105	            k = f"{r.state}-{int(r.seat):02d}" if str(r.seat).isdigit() else f"{r.state}-AL"
   106	            if k in dmap:
   107	                return dmap[k]
   108	        return smap.get(r.state, 0.5)
   109	
   110	    df["b"] = df.apply(base, axis=1)
   111	    return df
   112	
   113	
   114	def pick_units(df):
   115	    """Un único nivel geográfico por carrera, sin solapamientos."""
   116	    out = []
   117	    for rid, g in df.groupby("race_id", sort=False):
   118	        top = g[g.level == "state"]
   119	        sub = g[~g.level.isin(["state", "national"])]
   120	        best = None
   121	        if len(sub):
   122	            target = top.expected.sum() if len(top) else None
   123	            for lvl, gl in sub.groupby("level"):
   124	                gap = abs(gl.expected.sum() - target) if target else -len(gl)
   125	                if best is None or gap < best[0]:
   126	                    best = (gap, gl)
   127	        if best is not None and (not len(top) or best[1].expected.sum() > 0.9 * top.expected.sum()):
   128	            out.append(best[1])
   129	        else:
   130	            out.append(top.head(1))
   131	    return pd.concat(out, ignore_index=True)
   132	
   133	
   134	# ---------------------------------------------------------------- cuerpo del modelo
   135	def shock_curve(f):
   136	    """Peso del shock sobre los votos QUE FALTAN según la fracción no escrutada f.
   137	
   138	    Sin votos (f=1) vale 0 porque la incertidumbre ya está en el prior; aparece completo con
   139	    los primeros votos. No se multiplica por f: el shock se aplica sólo a los votos pendientes,
   140	    así que su efecto sobre el total ya se achica solo a medida que se cuenta.
   141	    """
   142	    return 1 - np.exp(-(1 - f) / 0.03)
   143	
   144	
   145	class Model:
   146	    def __init__(self, df):
   147	        self.u = pick_units(df).reset_index(drop=True)
   148	        self.races = self._races(df)
   149	        self._index()
   150	
   151	    def _races(self, df):
   152	        top = df[df.level == "state"].groupby("race_id").first()
   153	        rows = []
   154	        for rid, g in self.u.groupby("race_id", sort=False):
   155	            t = top.loc[rid] if rid in top.index else g.iloc[0]
   156	            parties = str(t.get("parties", "") or "")
   157	            # lado no republicano: el que más votos tiene; sin votos, el demócrata si hay
   158	            if g.D.sum() + g.O.sum() > 0 and "O" in parties:
   159	                side = "D" if g.D.sum() >= g.O.sum() else "O"
   160	            else:
   161	                side = "D" if "D" in parties else ("O" if "O" in parties else "D")
   162	            same = bool(parties) and len(set(parties)) == 1 and parties[0] in "DR"
   163	            w = g.expected.where(g.expected > 0, 1)
   164	            bbar = float(np.average(g.b, weights=w))
   165	            lo, hi, sd = RATING.get(str(t.get("rating")), (0.0, 1.0, 0.20))
   166	            # competitivas: manda el centro de la calificación (la base de 2024 trae el clima de
   167	            # ese año); seguras/probables: la base histórica recortada al rango.
   168	            rating = str(t.get("rating"))
   169	            if rating.split("-")[0] in ("tossup", "tilt", "lean"):
   170	                p0 = (lo + hi) / 2
   171	            else:
   172	                p0 = float(np.clip(bbar, lo, hi))
   173	            rows.append(dict(
   174	                race_id=rid, office=t.office, state=t.state, seat=t.seat, rating=t.get("rating"),
   175	                side=side, same_party=same, parties=parties, race_type=t.get("race_type"),
   176	                tabulation=t.get("tabulation"), call=t.get("call"), winner=str(t.get("winner") or ""),
   177	                rho0=float(logit(p0) - logit(bbar)), sd_race=sd, bbar=bbar,
   178	                expected=float(t.expected), counted=float(t.total), eevp=float(t.eevp),
   179	            ))
   180	        return pd.DataFrame(rows).set_index("race_id")
   181	
   182	    def _index(self):
   183	        self.ri = {r: i for i, r in enumerate(self.races.index)}
   184	        self.states = sorted(self.races.state.dropna().unique())
   185	        self.si = {s: i for i, s in enumerate(self.states)}
   186	        nr, ns, nt = len(self.ri), len(self.si), len(TYPES)
   187	        # parámetros: nat | state | race | type(state,t) | bias(state). El desvío de cada unidad
   188	        # no es un parámetro: entra como varianza extra de su observación (efecto aleatorio
   189	        # integrado). `bias` es el sesgo del orden de conteo de cada estado: afecta sólo a lo ya
   190	        # contado, con peso igual a la fracción que falta contar, y no se proyecta a lo pendiente.
   191	        self.o_state, self.o_race, self.o_type = 1, 1 + ns, 1 + ns + nr
   192	        self.o_bias = self.o_type + ns * nt
   193	        self.npar = self.o_bias + ns
   194	        R = self.races
   195	        e = R.groupby("state").expected.sum()
   196	        c = R.groupby("state").counted.sum()
   197	        fs = (1 - (c / e.where(e > 0, 1)).clip(0, 1)).to_dict()
   198	        self.f_state = np.array([fs.get(s, 1.0) for s in self.states])
   199	        tot = self.u.groupby("race_id").expected.transform("sum").where(lambda x: x > 0, 1)
   200	        self.wu = (self.u.expected / tot).clip(0, 1).values
   201	        self.sd_unit = np.maximum(SD["unit"] * np.sqrt(1 - self.wu), 1e-3)
   202	
   203	    def _B(self, u, side):
   204	        return u.D if side == "D" else u.O
   205	
   206	    def _cells(self):
   207	        """Celdas observadas (unidad, tipo) con votos contados para los dos lados."""
   208	        cells = []
   209	        for i, r in self.u.iterrows():
   210	            race = self.races.loc[r.race_id]
   211	            if race.same_party:
   212	                continue
   213	            B = self._B(r, race.side)
   214	            typed = [(t, r[f"{race.side}_{t}"], r[f"R_{t}"]) for t in TYPES]
   215	            if sum(b + a for _, b, a in typed) >= 0.95 * (B + r.R) > 0:
   216	                for t, b, a in typed:
   217	                    if a + b > 0:
   218	                        cells.append((i, TYPES.index(t), b, a))
   219	            elif B + r.R > 0:
   220	                cells.append((i, -1, B, r.R))
   221	        return cells
   222	
   223	    def _design(self, i, t, race):
   224	        si = self.si[race.state]
   225	        js = [(0, 1.0), (self.o_state + si, 1.0), (self.o_race + self.ri[self.u.at[i, "race_id"]], 1.0),
   226	              (self.o_bias + si, float(self.f_state[si]))]
   227	        if t >= 0:
   228	            js.append((self.o_type + si * len(TYPES) + t, 1.0))
   229	        return js
   230	
   231	    def fit(self):
   232	        cells = self._cells()
   233	        prior = np.zeros(self.npar)
   234	        prior[0] = SD["nat"]
   235	        prior[self.o_state:self.o_race] = SD["state"]
   236	        prior[self.o_race:self.o_type] = self.races.sd_race.values
   237	        prior[self.o_type:self.o_bias] = SD["type"]
   238	        prior[self.o_bias:] = SD["bias"]
   239	        A = np.diag(1 / prior ** 2)
   240	        rhs = np.zeros(self.npar)
   241	        obs = []
   242	        for i, t, b, a in cells:
   243	            u = self.u.loc[i]
   244	            race = self.races.loc[u.race_id]
   245	            n = a + b
   246	            p = (b + 0.5) / (n + 1)
   247	            v_bin = 1 / (n * p * (1 - p)) + SD["floor"] ** 2
   248	            v = v_bin + self.sd_unit[i] ** 2
   249	            yv = logit(p) - logit(u.b) - race.rho0
   250	            js = self._design(i, t, race)
   251	            for j, xj in js:
   252	                rhs[j] += xj * yv / v
   253	                for k, xk in js:
   254	                    A[j, k] += xj * xk / v
   255	            obs.append((i, js, yv, v_bin))
   256	        self.cov = np.linalg.inv(A)
   257	        self.theta = self.cov @ rhs
   258	        # desvío propio de cada unidad que ya reportó (BLUP), para proyectar lo que le falta
   259	        num_, den_ = np.zeros(len(self.u)), np.zeros(len(self.u))
   260	        for i, js, yv, v_bin in obs:
   261	            num_[i] += (yv - sum(self.theta[j] * x for j, x in js)) / v_bin
   262	            den_[i] += 1 / v_bin
   263	        s2 = self.sd_unit ** 2
   264	        self.e_hat = num_ / (den_ + 1 / s2)
   265	        self.e_sd = np.sqrt(1 / (den_ + 1 / s2))
   266	        self.ncells = len(cells)
   267	        return self
   268	
   269	    # ------------------------------------------------------------ simulación
   270	    def simulate(self, seed=2026):
   271	        rng = np.random.default_rng(seed)
   272	        ns, nr, nt = len(self.si), len(self.ri), len(TYPES)
   273	        L = np.linalg.cholesky(self.cov + 1e-12 * np.eye(self.npar))
   274	        draw = self.theta[None, :] + rng.standard_normal((K, self.npar)) @ L.T
   275	
   276	        R = self.races
   277	        f_race = 1 - np.clip(R.eevp.values / 100, 0, 1)
   278	        exp_by_state = R.groupby("state").expected.sum()
   279	        cnt_by_state = R.groupby("state").counted.sum()
   280	        f_state = (1 - (cnt_by_state / exp_by_state.where(exp_by_state > 0, 1)).clip(0, 1)).to_dict()
   281	        f_nat = 1 - min(R.counted.sum() / max(R.expected.sum(), 1), 1)
   282	        g_race, g_nat = shock_curve(f_race), shock_curve(f_nat)
   283	        g_state = np.array([shock_curve(f_state.get(s, 1)) for s in self.states])
   284	
   285	        nat_shock = rng.standard_normal(K) * SHOCK["nat"] * g_nat
   286	        st_shock = rng.standard_normal((K, ns)) * SHOCK["state"] * g_state
   287	        race_shock = rng.standard_normal((K, nr)) * SHOCK["race"] * g_race
   288	        type_shock = rng.standard_normal((K, ns * nt)) * SHOCK["type"]
   289	        untyped_shock = rng.standard_normal((K, ns)) * SHOCK["untyped"]
   290	        turn_st = np.exp(rng.standard_normal((K, ns)) * SHOCK["turnout"] * 0.5)
   291	
   292	        Bsim = np.zeros((K, nr))
   293	        Asim = np.zeros((K, nr))
   294	        self.unit_proj = np.full(len(self.u), np.nan)
   295	        for i, u in self.u.iterrows():
   296	            ri, race = self.ri[u.race_id], R.loc[u.race_id]
   297	            if race.same_party:
   298	                continue
   299	            si = self.si[race.state]
   300	            B = self._B(u, race.side)
   301	            Bsim[:, ri] += B
   302	            Asim[:, ri] += u.R
   303	            e_u = self.e_hat[i] + rng.standard_normal(K) * self.e_sd[i]
   304	            base = (logit(u.b) + race.rho0 + draw[:, 0] + nat_shock
   305	                    + draw[:, self.o_state + si] + st_shock[:, si]
   306	                    + draw[:, self.o_race + ri] + race_shock[:, ri] + e_u)
   307	            exp_t = np.array([u[f"exp_{t}"] for t in TYPES])
   308	            got_t = np.array([u[f"{race.side}_{t}"] + u[f"R_{t}"] + u[f"O_{t}"] for t in TYPES])
   309	            if exp_t.sum() > 0:
   310	                rem = np.maximum(exp_t - got_t, 0)
   311	                parts = [(rem[t], self.o_type + si * nt + t) for t in range(nt) if rem[t] > 0]
   312	            else:
   313	                parts = [(max(u.expected - u.total, 0), None)]
   314	            other = u.total - B - u.R
   315	            share_o = other / u.total if u.total > 0 else 0.02
   316	            fu = 1 - min(u.eevp / 100, 1)
   317	            unit_noise = rng.standard_normal(K) * SHOCK["unit"] * shock_curve(fu) * np.sqrt(1 - self.wu[i])
   318	            tn = turn_st[:, si] * np.exp(rng.standard_normal(K) * SHOCK["turnout"] * 0.5)
   319	            proj_b, proj_n = B, B + u.R
   320	            for n, j in parts:
   321	                if n <= 0:
   322	                    continue
   323	                if j is not None:
   324	                    x = base + unit_noise + draw[:, j] + type_shock[:, j - self.o_type]
   325	                else:
   326	                    x = base + unit_noise + untyped_shock[:, si] * shock_curve(fu)
   327	                p = expit(x)
   328	                two = n * (1 - share_o) * tn
   329	                Bsim[:, ri] += two * p
   330	                Asim[:, ri] += two * (1 - p)
   331	                proj_b += float(np.median(two * p)); proj_n += float(np.median(two))
   332	            self.unit_proj[i] = proj_b / proj_n if proj_n > 0 else np.nan
   333	
   334	        share = Bsim / np.maximum(Bsim + Asim, 1)
   335	        win_B = share > 0.5
   336	        for rid, race in R.iterrows():
   337	            ri = self.ri[rid]
   338	            if race.same_party:
   339	                win_B[:, ri] = race.parties[0] != "R"
   340	            elif race.winner:
   341	                win_B[:, ri] = race.winner[0] != "R"
   342	        self.share, self.win_B = share, win_B
   343	        return self
   344	
   345	    # ------------------------------------------------------------ salidas
   346	    def summary(self, control):
   347	        R = self.races
   348	        q = lambda a, p: float(np.quantile(a, p))
   349	        races = []
   350	        for rid, race in R.iterrows():
   351	            ri = self.ri[rid]
   352	            g = self.u[self.u.race_id == rid]
   353	            Bc = float(g.D.sum() if race.side == "D" else g.O.sum())
   354	            Ac = float(g.R.sum())
   355	            s = self.share[:, ri]
   356	            races.append(dict(
   357	                id=rid, office=race.office, state=race.state, seat=race.seat, rating=race.rating,
   358	                side=race.side, same_party=race.same_party, parties=race.parties, call=race.call,
   359	                winner=race.winner, eevp=race.eevp, counted=race.counted, expected=race.expected,
   360	                partial_B=round(100 * Bc / (Bc + Ac), 2) if Bc + Ac else None,
   361	                partial_R=round(100 * Ac / (Bc + Ac), 2) if Bc + Ac else None,
   362	                proj_B=round(100 * q(s, 0.5), 2), proj_R=round(100 * (1 - q(s, 0.5)), 2),
   363	                ci90_B=[round(100 * q(s, 0.05), 2), round(100 * q(s, 0.95), 2)],
   364	                ci90_R=[round(100 * (1 - q(s, 0.95)), 2), round(100 * (1 - q(s, 0.05)), 2)],
   365	                p_B_win=round(float(self.win_B[:, ri].mean()), 4),
   366	                runoff_risk=bool(race.state == "GA" and race.office in ("S", "G")),
   367	            ))
   368	        out = dict(races=races, chambers={})
   369	        for off, ctl in control.items():
   370	            idx = [self.ri[r] for r in R.index if R.loc[r, "office"] == off]
   371	            if not idx:
   372	                continue
   373	            sideD = np.array([R.iloc[i].side == "D" for i in idx])
   374	            wins = self.win_B[:, idx]
   375	            D = ctl["D_hold"] + (wins & sideD).sum(1)
   376	            I = ctl.get("I_hold", 0) + (wins & ~sideD).sum(1)
   377	            Rr = ctl["total"] - D - I
   378	            vals, cnt = np.unique(D, return_counts=True)
   379	            out["chambers"][off] = dict(
   380	                total=ctl["total"], D_needs=ctl["D_needs"], R_needs=ctl["R_needs"],
   381	                p_D=round(float((D >= ctl["D_needs"]).mean()), 4),
   382	                p_R=round(float((Rr >= ctl["R_needs"]).mean()), 4),
   383	                D_med=int(np.median(D)), R_med=int(np.median(Rr)), I_med=int(np.median(I)),
   384	                D_ci90=[int(q(D, 0.05)), int(q(D, 0.95))], R_ci90=[int(q(Rr, 0.05)), int(q(Rr, 0.95))],
   385	                dist={int(v): round(c / K, 4) for v, c in zip(vals, cnt)},
   386	            )
   387	        return out
   388	
   389	    def map_units(self):
   390	        g = self.u.assign(proj=self.unit_proj)
   391	        out = {}
   392	        for rid, gg in g.groupby("race_id"):
   393	            side = self.races.loc[rid, "side"]
   394	            m = {}
   395	            for _, r in gg.iterrows():
   396	                B = r.D if side == "D" else r.O
   397	                part = B / (B + r.R) if B + r.R > 0 else None
   398	                m[r.unit_id] = dict(
   399	                    f=r.fips, n=r["name"], e=r.eevp,
   400	                    p=None if part is None else round(100 * part, 1),
   401	                    j=None if np.isnan(r.proj) else round(100 * r.proj, 1),
   402	                    b=round(100 * r.b, 1),
   403	                )
   404	            out[rid] = m
   405	        return out
   406	
   407	
   408	def control_from_raw(date):
   409	    """Bancas que no se votan y umbrales, desde partyControlData del NYT."""
   410	    out = {}
   411	    for off, fn in (("S", "results-senate"), ("H", "results-house")):
   412	        f = ROOT / f"data/live/{date}/raw/{fn}.json"
   413	        if not f.exists():
   414	            continue
   415	        o = json.loads(f.read_bytes())["partyControlData"]["results"][0]["offices"][off]
   416	        pb = o["party_balance"]
   417	        out[off] = dict(total=o["total"], D_hold=pb["DEM"]["no_election"], I_hold=pb["OTH"]["no_election"],
   418	                        D_needs=o["to_win"]["DEM"], R_needs=o["to_win"]["GOP"])
   419	    return out
   420	
   421	
   422	def main():
   423	    ap = argparse.ArgumentParser()
   424	    ap.add_argument("--date", default="2026-11-03")
   425	    ap.add_argument("--out", default=str(ROOT / "dash"))
   426	    a = ap.parse_args()
   427	    t0 = datetime.now()
   428	    m = Model(load(a.date)).fit().simulate()
   429	    s = m.summary(control_from_raw(a.date))
   430	    s["updated"] = t0.strftime("%Y-%m-%d %H:%M:%S")
   431	    s["cells"] = m.ncells
   432	    out = Path(a.out)
   433	    out.mkdir(parents=True, exist_ok=True)
   434	    for name, obj in (("data.json", s), ("units.json", m.map_units())):
   435	        tmp = out / (name + ".tmp")
   436	        tmp.write_text(json.dumps(obj, separators=(",", ":")))
   437	        tmp.replace(out / name)
   438	    hist = out / "history.json"
   439	    h = json.loads(hist.read_text()) if hist.exists() else []
   440	    h.append(dict(t=t0.strftime("%H:%M:%S"), **{k: {kk: v[kk] for kk in ("p_D", "p_R", "D_med", "R_med", "D_ci90", "R_ci90")}
   441	                                                for k, v in s["chambers"].items()}))
   442	    hist.write_text(json.dumps(h, separators=(",", ":")))
   443	    for k, v in s["chambers"].items():
   444	        print(f"{k}: P(D)={v['p_D']:.3f} P(R)={v['p_R']:.3f} D={v['D_med']} {v['D_ci90']} R={v['R_med']} I={v['I_med']}")
   445	    print(f"{len(s['races'])} carreras · {m.ncells} celdas · {(datetime.now()-t0).total_seconds():.1f}s")
   446	
   447	
   448	if __name__ == "__main__":
   449	    main()
     1	"""Lector de los JSON públicos del NYT (datos AP) para la noche del 3-nov-2026.
     2	
     3	Baja los tres archivos generales (senate, governor, house) y las páginas por estado de
     4	Senado y gobernación (que traen el detalle por condado). Guarda la última versión de cada
     5	uno y un snapshot comprimido sólo cuando cambia. Después aplana todo en units.csv.
     6	
     7	Uso:
     8	  uv run --with requests --with tqdm model/fetch_nyt.py --once
     9	  uv run --with requests --with tqdm model/fetch_nyt.py --every 90
    10	  uv run --with requests --with tqdm model/fetch_nyt.py --date 2024-11-05 --once   # ensayo
    11	"""
    12	import argparse, csv, gzip, json, os, sys, time
    13	from concurrent.futures import ThreadPoolExecutor
    14	from datetime import datetime, timezone
    15	from pathlib import Path
    16	
    17	import requests
    18	
    19	sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
    20	from claude_tqdm import tqdm  # noqa: E402
    21	
    22	ROOT = Path(__file__).resolve().parent.parent
    23	BASE = "https://static01.nyt.com/elections-assets/pages/data/{date}/{slug}.json"
    24	UA = {"User-Agent": "Mozilla/5.0 (proyeccion personal midterms 2026)"}
    25	TYPES = ("advance", "absentee_mail", "election_day_in_person", "provisional")
    26	THREADS = 4
    27	
    28	session = requests.Session()
    29	session.headers.update(UA)
    30	etags = {}
    31	
    32	
    33	def get(date, slug, tries=6):
    34	    """GET condicional con backoff. Devuelve (status, bytes|None)."""
    35	    url = BASE.format(date=date, slug=slug)
    36	    h = {"If-None-Match": etags[slug]} if slug in etags else {}
    37	    for i in range(tries):
    38	        try:
    39	            r = session.get(url, headers=h, timeout=30)
    40	        except requests.RequestException:
    41	            time.sleep(2 ** i)
    42	            continue
    43	        if r.status_code in (429, 500, 502, 503, 504):
    44	            time.sleep(float(r.headers.get("Retry-After", 2 ** i)))
    45	            continue
    46	        if r.status_code == 200 and r.headers.get("ETag"):
    47	            etags[slug] = r.headers["ETag"]
    48	        return r.status_code, (r.content if r.status_code == 200 else None)
    49	    return 0, None
    50	
    51	
    52	def state_slugs(overview):
    53	    """'https://.../results-alabama-us-senate.html' -> 'results-alabama-us-senate'."""
    54	    out = []
    55	    for r in overview.get("races", []):
    56	        u = r.get("url")
    57	        if u:
    58	            out.append(u.rsplit("/", 1)[1].removesuffix(".html"))
    59	    return out
    60	
    61	
    62	def save(outdir, slug, content, stamp):
    63	    (outdir / "raw").mkdir(parents=True, exist_ok=True)
    64	    latest = outdir / "raw" / f"{slug}.json"
    65	    if latest.exists() and latest.read_bytes() == content:
    66	        return False
    67	    tmp = latest.with_suffix(".tmp")
    68	    tmp.write_bytes(content)
    69	    tmp.replace(latest)
    70	    snap = outdir / "snap" / slug
    71	    snap.mkdir(parents=True, exist_ok=True)
    72	    with gzip.open(snap / f"{stamp}.json.gz", "wb") as f:
    73	        f.write(content)
    74	    return True
    75	
    76	
    77	def party_of(meta):
    78	    p = (meta or {}).get("party") or {} if isinstance(meta, dict) else {}
    79	    return {"DEM": "D", "GOP": "R"}.get(p.get("nyt_id"), "O")
    80	
    81	
    82	def flatten(outdir):
    83	    """Una fila por (carrera, unidad de reporte) con votos D/R/otros y votos esperados."""
    84	    rows, seen = [], set()
    85	    files = sorted((outdir / "raw").glob("*.json"))
    86	    # Las páginas por estado primero: tienen condados; las generales sólo completan lo que falte.
    87	    files.sort(key=lambda p: p.stem in ("results-senate", "results-governor", "results-house"))
    88	    for f in files:
    89	        try:
    90	            d = json.loads(f.read_bytes())
    91	        except json.JSONDecodeError:
    92	            continue
    93	        for r in d.get("races", []):
    94	            meta = r.get("candidate_metadata") or {}
    95	            won = (r.get("outcome") or {}).get("won") or []
    96	            parties = "".join(sorted(party_of(m) for m in meta.values()))
    97	            for u in r.get("reporting_units", []):
    98	                key = (r["nyt_id"], u["nyt_id"])
    99	                if key in seen:
   100	                    continue
   101	                seen.add(key)
   102	                v = {p: {"total": 0, **{t: 0 for t in TYPES}} for p in "DRO"}
   103	                for c in u.get("candidates", []):
   104	                    p = party_of(meta.get(c["nyt_id"]))
   105	                    for k, n in (c.get("votes") or {}).items():
   106	                        if k in v[p]:
   107	                            v[p][k] += n or 0
   108	                ev = u.get("expected_vote_by_vote_type") or {}
   109	                ee = u.get("eevp_by_vote_type") or {}
   110	                hist = next(iter((u.get("historical_comparison_race_data") or {}).values()), {}) or {}
   111	                row = {
   112	                    "race_id": r["nyt_id"], "office": r.get("office_id"), "state": u.get("state_postal"),
   113	                    "seat": r.get("seat_number"), "rating": r.get("rating"),
   114	                    "call": r.get("race_call_status"), "winner": ",".join(party_of(meta.get(w)) for w in won),
   115	                    "uncontested": r.get("uncontested"), "tabulation": r.get("tabulation_method"),
   116	                    "parties": parties, "race_type": r.get("race_type_id"),
   117	                    "unit_id": u["nyt_id"], "level": u.get("level"), "name": u.get("name"),
   118	                    "fips": (u.get("fips_state") or "") + (u.get("fips_county") or ""),
   119	                    "eevp": u.get("eevp"), "expected": u.get("total_expected_vote"),
   120	                    "total": u.get("total_votes"),
   121	                    "prec_rep": u.get("precincts_reporting"), "prec_tot": u.get("precincts_total"),
   122	                    "hist_dem": hist.get("pct_dem"), "hist_rep": hist.get("pct_rep"),
   123	                }
   124	                for p in "DRO":
   125	                    row[p] = v[p]["total"]
   126	                    for t in TYPES:
   127	                        row[f"{p}_{t}"] = v[p][t]
   128	                for t in TYPES:
   129	                    row[f"exp_{t}"] = ev.get(t)
   130	                    row[f"eevp_{t}"] = ee.get(t)
   131	                rows.append(row)
   132	    if rows:
   133	        tmp = outdir / "units.tmp"
   134	        with open(tmp, "w", newline="") as fh:
   135	            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
   136	            w.writeheader()
   137	            w.writerows(rows)
   138	        tmp.replace(outdir / "units.csv")
   139	    return len(rows)
   140	
   141	
   142	def cycle(date, outdir, bar):
   143	    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
   144	    overviews = ["results-senate", "results-governor", "results-house"]
   145	    changed, missing = 0, 0
   146	    slugs = list(overviews)
   147	    for s in overviews:
   148	        st, body = get(date, s)
   149	        if body:
   150	            changed += save(outdir, s, body, stamp)
   151	            slugs += state_slugs(json.loads(body))
   152	        elif (outdir / "raw" / f"{s}.json").exists():  # 304: usar el último para la lista
   153	            slugs += state_slugs(json.loads((outdir / "raw" / f"{s}.json").read_bytes()))
   154	    per_state = [s for s in dict.fromkeys(slugs) if s not in overviews and "-us-house-" not in s]
   155	    bar.reset(total=len(per_state))
   156	    bar.status(f"{len(per_state)} páginas por estado")
   157	
   158	    def one(s):
   159	        return s, *get(date, s)
   160	
   161	    with ThreadPoolExecutor(THREADS) as ex:
   162	        for s, st, body in ex.map(one, per_state):
   163	            if body:
   164	                changed += save(outdir, s, body, stamp)
   165	            elif st == 404:
   166	                missing += 1
   167	            bar.update(1)
   168	    n = flatten(outdir)
   169	    bar.log(f"{stamp}: {changed} archivos nuevos · {missing} páginas aún sin publicar · {n} filas")
   170	    return changed
   171	
   172	
   173	def main():
   174	    ap = argparse.ArgumentParser()
   175	    ap.add_argument("--date", default="2026-11-03")
   176	    ap.add_argument("--every", type=int, default=0, help="segundos entre ciclos (0 = una vez)")
   177	    ap.add_argument("--once", action="store_true")
   178	    a = ap.parse_args()
   179	    outdir = ROOT / "data" / "live" / a.date
   180	    bar = tqdm(total=1, desc=f"NYT {a.date}", unit="página", goal="bajar resultados en vivo")
   181	    bar.info(fuente="NYT / AP", hilos=THREADS, intervalo=f"{a.every}s" if a.every else "una vez")
   182	    while True:
   183	        cycle(a.date, outdir, bar)
   184	        if a.once or not a.every:
   185	            break
   186	        time.sleep(a.every)
   187	    bar.close()
   188	
   189	
   190	if __name__ == "__main__":
   191	    main()
     1	"""Ensayo: reproduce la noche de 2024 (Senado + gobernaciones, por condado) y mide el modelo.
     2	
     3	El conteo se simula por condado: cada estado arranca según su hora de cierre, los condados
     4	grandes reportan más tarde y más despacio, y lo contado lleva un sesgo por estado (el efecto
     5	del orden de los tipos de voto) que se desvanece a medida que se completa el conteo, de modo
     6	que al final coincide exactamente con el resultado real. La base es la presidencial 2020
     7	por condado y el prior, la calificación que el NYT tenía para cada carrera en 2024.
     8	
     9	Uso: uv run --with numpy --with scipy --with pandas --with tqdm model/rehearse.py [--bias 0.04]
    10	"""
    11	import argparse, os, sys
    12	from pathlib import Path
    13	
    14	import numpy as np
    15	import pandas as pd
    16	
    17	sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
    18	from claude_tqdm import tqdm  # noqa: E402
    19	
    20	sys.path.insert(0, str(Path(__file__).resolve().parent))
    21	import project as P  # noqa: E402
    22	
    23	ROOT = P.ROOT
    24	# Orden aproximado de cierre (horas desde las 19 ET); el resto, 1 h por defecto.
    25	CLOSE = {"IN": 0, "KY": 0, "VT": 0, "VA": 0, "GA": 0, "SC": 0, "FL": 0.5, "OH": 0.5, "NC": 0.5,
    26	         "WV": 0.5, "PA": 1, "ME": 1, "MD": 1, "MA": 1, "NJ": 1, "CT": 1, "DE": 1, "MS": 1, "MO": 1,
    27	         "TN": 1, "TX": 1.5, "MI": 1.5, "AZ": 2, "WI": 2, "MN": 2, "NY": 2, "NM": 2, "NE": 2,
    28	         "ND": 2, "WY": 2, "UT": 3, "MT": 3, "NV": 3, "CA": 4, "WA": 4, "HI": 5, "AK": 6}
    29	
    30	
    31	def synth(df, t, rng_state, bias):
    32	    """Units a la hora t (0..10 h desde las 19 ET)."""
    33	    tau, dur, beta, noise = rng_state
    34	    d = df.copy()
    35	    f = np.clip((t - tau) / dur, 0, 1)
    36	    final_B = d.D.values.astype(float)
    37	    final_R = d.R.values.astype(float)
    38	    final_O = d.O.values.astype(float)
    39	    tot2 = final_B + final_R
    40	    y = np.divide(final_B, tot2, out=np.full_like(tot2, 0.5), where=tot2 > 0)
    41	    yc = np.clip(y + beta * (1 - f), 0.01, 0.99)
    42	    c2 = tot2 * f
    43	    d["D"] = np.round(c2 * yc)
    44	    d["R"] = np.round(c2 * (1 - yc))
    45	    d["O"] = np.round(final_O * f)
    46	    d["total"] = d.D + d.R + d.O
    47	    d["expected"] = np.round(d.expected * noise)
    48	    d["eevp"] = np.where(d.expected > 0, np.minimum(100 * d.total / d.expected, 99), 0)
    49	    d["call"] = "too_early"
    50	    d["winner"] = ""
    51	    for c in [c for c in d.columns if any(c.endswith(x) for x in P.TYPES)]:
    52	        d[c] = 0
    53	    return d
    54	
    55	
    56	def rebuild_state_rows(d):
    57	    """Reagrega la fila estatal de cada carrera a partir de sus unidades."""
    58	    sub = d[~d.level.isin(["state", "national"])]
    59	    agg = sub.groupby("race_id")[["D", "R", "O", "total", "expected"]].sum()
    60	    st = d.level == "state"
    61	    for c in agg.columns:
    62	        d.loc[st, c] = d.loc[st, "race_id"].map(agg[c]).fillna(d.loc[st, c])
    63	    d.loc[st, "eevp"] = np.where(d.loc[st, "expected"] > 0,
    64	                                 np.minimum(100 * d.loc[st, "total"] / d.loc[st, "expected"], 99), 0)
    65	    return d
    66	
    67	
    68	def main():
    69	    ap = argparse.ArgumentParser()
    70	    ap.add_argument("--bias", type=float, default=0.04, help="sd del sesgo estatal por orden de conteo")
    71	    ap.add_argument("--seed", type=int, default=7)
    72	    ap.add_argument("--dump-hour", type=float, default=None, help="guarda data.json/units.json de esa hora")
    73	    ap.add_argument("--dump-dir", default=str(ROOT / "dash/sample"))
    74	    a = ap.parse_args()
    75	    df = P.load("2024-11-05", base_year=2020)
    76	    df = df[df.office.isin(["S", "G"])].reset_index(drop=True)
    77	    rng = np.random.default_rng(a.seed)
    78	    size = df.expected.rank(pct=True).values
    79	    tau = df.state.map(CLOSE).fillna(1).values + 0.3 + 1.5 * size * rng.uniform(0.3, 1, len(df))
    80	    dur = 0.5 + 3 * size * rng.uniform(0.5, 1.5, len(df))
    81	    sb = {s: rng.normal(0, a.bias) for s in df.state.unique()}
    82	    beta = df.state.map(sb).values * rng.uniform(0.5, 1.5, len(df))
    83	    noise = np.exp(rng.normal(0, 0.03, len(df)))
    84	    state = (tau, dur, beta, noise)
    85	
    86	    truth = {}
    87	    for rid, g in df[df.level == "state"].groupby("race_id"):
    88	        r = g.iloc[0]
    89	        B = max(r.D, r.O) if "O" in str(r.parties) else r.D
    90	        truth[rid] = B / (B + r.R)
    91	
    92	    rows = []
    93	    hours = [0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]
    94	    bar = tqdm(hours, desc="Ensayo 2024", unit="corte", goal="medir error y cobertura del modelo")
    95	    bar.info(carreras=len(truth), sesgo=a.bias, base="pres 2020")
    96	    for t in bar:
    97	        bar.status(f"{t} h después de las 19 ET")
    98	        d = rebuild_state_rows(synth(df, t, state, a.bias))
    99	        d = d.assign(b=df.b.values)
   100	        m = P.Model(d).fit().simulate()
   101	        s = m.summary(P.control_from_raw("2024-11-05"))
   102	        if a.dump_hour == t:
   103	            import json
   104	            dd = Path(a.dump_dir); dd.mkdir(parents=True, exist_ok=True)
   105	            s["updated"] = f"ensayo 2024 · {t} h"
   106	            (dd / "data.json").write_text(json.dumps(s, separators=(",", ":")))
   107	            (dd / "units.json").write_text(json.dumps(m.map_units(), separators=(",", ":")))
   108	        res = []
   109	        for r in s["races"]:
   110	            if r["same_party"] or r["id"] not in truth:
   111	                continue
   112	            y = 100 * truth[r["id"]]
   113	            res.append(dict(
   114	                err=r["proj_B"] - y,
   115	                naive=(r["partial_B"] - y) if r["partial_B"] is not None else np.nan,
   116	                cover=r["ci90_B"][0] <= y <= r["ci90_B"][1],
   117	                brier=(r["p_B_win"] - (y > 50)) ** 2,
   118	                wrong_sure=(r["p_B_win"] > 0.95 and y < 50) or (r["p_B_win"] < 0.05 and y > 50),
   119	                eevp=r["eevp"], id=r["id"], y=round(y, 2), proj=r["proj_B"], ci=r["ci90_B"], pw=r["p_B_win"],
   120	            ))
   121	        q = pd.DataFrame(res)
   122	        row = dict(hora=t, escrutado=round(q.eevp.mean(), 1), mae_modelo=round(q.err.abs().mean(), 2),
   123	                   mae_parcial=round(q.naive.abs().mean(), 2), cobertura90=round(q.cover.mean(), 3),
   124	                   brier=round(q.brier.mean(), 4), seguras_erradas=int(q.wrong_sure.sum()))
   125	        rows.append(row)
   126	        bad = q[~q.cover].assign(ae=lambda x: x.err.abs()).sort_values("ae", ascending=False).head(6)
   127	        print(f"--- {t}h fuera del IC:", "; ".join(f"{b.id[:8]} y={b.y} p={b.proj} {b.ci} pw={b.pw} e={b.eevp:.0f}" for b in bad.itertuples()), flush=True)
   128	        bar.log(f"{t}h: {row['escrutado']}% · MAE {row['mae_modelo']} vs parcial {row['mae_parcial']} · cob {row['cobertura90']}")
   129	    bar.close()
   130	    out = pd.DataFrame(rows)
   131	    print(out.to_string(index=False))
   132	    out.to_csv(ROOT / f"research/ensayo_2024_bias{a.bias}.csv", index=False)
   133	
   134	
   135	if __name__ == "__main__":
   136	    main()
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

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "sed -n '345,470p' model/project.py | nl -ba -v345; rg --files model data/live | head -65; ls -d .venv*; rg -n 'holdover|not_up|control|tiebreak|218' model research/fuente*" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 0ms:
   345	    # ------------------------------------------------------------ salidas
   346	    def summary(self, control):
   347	        R = self.races
   348	        q = lambda a, p: float(np.quantile(a, p))
   349	        races = []
   350	        for rid, race in R.iterrows():
   351	            ri = self.ri[rid]
   352	            g = self.u[self.u.race_id == rid]
   353	            Bc = float(g.D.sum() if race.side == "D" else g.O.sum())
   354	            Ac = float(g.R.sum())
   355	            s = self.share[:, ri]
   356	            races.append(dict(
   357	                id=rid, office=race.office, state=race.state, seat=race.seat, rating=race.rating,
   358	                side=race.side, same_party=race.same_party, parties=race.parties, call=race.call,
   359	                winner=race.winner, eevp=race.eevp, counted=race.counted, expected=race.expected,
   360	                partial_B=round(100 * Bc / (Bc + Ac), 2) if Bc + Ac else None,
   361	                partial_R=round(100 * Ac / (Bc + Ac), 2) if Bc + Ac else None,
   362	                proj_B=round(100 * q(s, 0.5), 2), proj_R=round(100 * (1 - q(s, 0.5)), 2),
   363	                ci90_B=[round(100 * q(s, 0.05), 2), round(100 * q(s, 0.95), 2)],
   364	                ci90_R=[round(100 * (1 - q(s, 0.95)), 2), round(100 * (1 - q(s, 0.05)), 2)],
   365	                p_B_win=round(float(self.win_B[:, ri].mean()), 4),
   366	                runoff_risk=bool(race.state == "GA" and race.office in ("S", "G")),
   367	            ))
   368	        out = dict(races=races, chambers={})
   369	        for off, ctl in control.items():
   370	            idx = [self.ri[r] for r in R.index if R.loc[r, "office"] == off]
   371	            if not idx:
   372	                continue
   373	            sideD = np.array([R.iloc[i].side == "D" for i in idx])
   374	            wins = self.win_B[:, idx]
   375	            D = ctl["D_hold"] + (wins & sideD).sum(1)
   376	            I = ctl.get("I_hold", 0) + (wins & ~sideD).sum(1)
   377	            Rr = ctl["total"] - D - I
   378	            vals, cnt = np.unique(D, return_counts=True)
   379	            out["chambers"][off] = dict(
   380	                total=ctl["total"], D_needs=ctl["D_needs"], R_needs=ctl["R_needs"],
   381	                p_D=round(float((D >= ctl["D_needs"]).mean()), 4),
   382	                p_R=round(float((Rr >= ctl["R_needs"]).mean()), 4),
   383	                D_med=int(np.median(D)), R_med=int(np.median(Rr)), I_med=int(np.median(I)),
   384	                D_ci90=[int(q(D, 0.05)), int(q(D, 0.95))], R_ci90=[int(q(Rr, 0.05)), int(q(Rr, 0.95))],
   385	                dist={int(v): round(c / K, 4) for v, c in zip(vals, cnt)},
   386	            )
   387	        return out
   388	
   389	    def map_units(self):
   390	        g = self.u.assign(proj=self.unit_proj)
   391	        out = {}
   392	        for rid, gg in g.groupby("race_id"):
   393	            side = self.races.loc[rid, "side"]
   394	            m = {}
   395	            for _, r in gg.iterrows():
   396	                B = r.D if side == "D" else r.O
   397	                part = B / (B + r.R) if B + r.R > 0 else None
   398	                m[r.unit_id] = dict(
   399	                    f=r.fips, n=r["name"], e=r.eevp,
   400	                    p=None if part is None else round(100 * part, 1),
   401	                    j=None if np.isnan(r.proj) else round(100 * r.proj, 1),
   402	                    b=round(100 * r.b, 1),
   403	                )
   404	            out[rid] = m
   405	        return out
   406	
   407	
   408	def control_from_raw(date):
   409	    """Bancas que no se votan y umbrales, desde partyControlData del NYT."""
   410	    out = {}
   411	    for off, fn in (("S", "results-senate"), ("H", "results-house")):
   412	        f = ROOT / f"data/live/{date}/raw/{fn}.json"
   413	        if not f.exists():
   414	            continue
   415	        o = json.loads(f.read_bytes())["partyControlData"]["results"][0]["offices"][off]
   416	        pb = o["party_balance"]
   417	        out[off] = dict(total=o["total"], D_hold=pb["DEM"]["no_election"], I_hold=pb["OTH"]["no_election"],
   418	                        D_needs=o["to_win"]["DEM"], R_needs=o["to_win"]["GOP"])
   419	    return out
   420	
   421	
   422	def main():
   423	    ap = argparse.ArgumentParser()
   424	    ap.add_argument("--date", default="2026-11-03")
   425	    ap.add_argument("--out", default=str(ROOT / "dash"))
   426	    a = ap.parse_args()
   427	    t0 = datetime.now()
   428	    m = Model(load(a.date)).fit().simulate()
   429	    s = m.summary(control_from_raw(a.date))
   430	    s["updated"] = t0.strftime("%Y-%m-%d %H:%M:%S")
   431	    s["cells"] = m.ncells
   432	    out = Path(a.out)
   433	    out.mkdir(parents=True, exist_ok=True)
   434	    for name, obj in (("data.json", s), ("units.json", m.map_units())):
   435	        tmp = out / (name + ".tmp")
   436	        tmp.write_text(json.dumps(obj, separators=(",", ":")))
   437	        tmp.replace(out / name)
   438	    hist = out / "history.json"
   439	    h = json.loads(hist.read_text()) if hist.exists() else []
   440	    h.append(dict(t=t0.strftime("%H:%M:%S"), **{k: {kk: v[kk] for kk in ("p_D", "p_R", "D_med", "R_med", "D_ci90", "R_ci90")}
   441	                                                for k, v in s["chambers"].items()}))
   442	    hist.write_text(json.dumps(h, separators=(",", ":")))
   443	    for k, v in s["chambers"].items():
   444	        print(f"{k}: P(D)={v['p_D']:.3f} P(R)={v['p_R']:.3f} D={v['D_med']} {v['D_ci90']} R={v['R_med']} I={v['I_med']}")
   445	    print(f"{len(s['races'])} carreras · {m.ncells} celdas · {(datetime.now()-t0).total_seconds():.1f}s")
   446	
   447	
   448	if __name__ == "__main__":
   449	    main()
model/project.py
model/live.py
model/rehearse.py
model/fetch_nyt.py
data/live/2026-11-03/raw/results-house.json
data/live/2026-11-03/raw/results-governor.json
data/live/2026-11-03/raw/results-senate.json
data/live/2024-11-05/raw/results-massachusetts-us-senate.json
data/live/2024-11-05/raw/results-west-virginia-governor.json
data/live/2024-11-05/raw/results-indiana-governor.json
data/live/2024-11-05/raw/results-north-dakota-governor.json
data/live/2024-11-05/raw/results-minnesota-us-senate.json
data/live/2024-11-05/raw/results-utah-us-senate.json
data/live/2024-11-05/raw/results-north-dakota-us-senate.json
data/live/2024-11-05/raw/results-washington-us-senate.json
data/live/2024-11-05/raw/results-wyoming-us-senate.json
data/live/2024-11-05/raw/results-montana-us-senate.json
data/live/2024-11-05/raw/results-house.json
data/live/2024-11-05/raw/results-pennsylvania-us-senate.json
data/live/2024-11-05/raw/results-wisconsin-us-senate.json
data/live/2024-11-05/raw/results-new-jersey-us-senate.json
data/live/2024-11-05/raw/results-north-carolina-governor.json
data/live/2024-11-05/raw/results-west-virginia-us-senate.json
data/live/2024-11-05/raw/results-texas-us-senate.json
data/live/2024-11-05/raw/results-new-mexico-us-senate.json
data/live/2024-11-05/raw/results-rhode-island-us-senate.json
data/live/2024-11-05/raw/results-governor.json
data/live/2024-11-05/raw/results-new-hampshire-governor.json
data/live/2024-11-05/raw/results-michigan-us-senate.json
data/live/2024-11-05/raw/results-ohio-us-senate.json
data/live/2024-11-05/raw/results-arizona-us-senate.json
data/live/2024-11-05/raw/results-maine-us-senate.json
data/live/2024-11-05/raw/results-connecticut-us-senate.json
data/live/2024-11-05/raw/results-maryland-us-senate.json
data/live/2024-11-05/raw/results-delaware-us-senate.json
data/live/2024-11-05/raw/results-florida-us-senate.json
data/live/2024-11-05/raw/results-vermont-governor.json
data/live/2024-11-05/raw/results-utah-governor.json
data/live/2024-11-05/raw/results-tennessee-us-senate.json
data/live/2024-11-05/raw/results-vermont-us-senate.json
data/live/2024-11-05/raw/results-nevada-us-senate.json
data/live/2024-11-05/raw/results-washington-governor.json
data/live/2024-11-05/raw/results-senate.json
data/live/2024-11-05/raw/results-virginia-us-senate.json
data/live/2024-11-05/raw/results-hawaii-us-senate.json
data/live/2024-11-05/raw/results-mississippi-us-senate.json
data/live/2024-11-05/raw/results-delaware-governor.json
data/live/2024-11-05/raw/results-missouri-governor.json
data/live/2024-11-05/raw/results-montana-governor.json
data/live/2024-11-05/raw/results-nebraska-us-senate-special.json
data/live/2024-11-05/raw/results-new-york-us-senate.json
data/live/2024-11-05/raw/results-california-us-senate.json
data/live/2024-11-05/raw/results-indiana-us-senate.json
data/live/2024-11-05/raw/results-missouri-us-senate.json
data/live/2024-11-05/raw/results-nebraska-us-senate.json
data/live/2026-11-03/snap/results-senate/20261030T162614Z.json.gz
data/live/2026-11-03/snap/results-governor/20261030T162614Z.json.gz
data/live/2026-11-03/snap/results-house/20261030T162614Z.json.gz
data/live/2026-11-03/units.csv
data/live/2024-11-05/units.csv
data/live/2024-11-05/snap/results-connecticut-us-senate/20261030T162619Z.json.gz
data/live/2024-11-05/snap/results-wisconsin-us-senate/20261030T162619Z.json.gz
data/live/2024-11-05/snap/results-nebraska-us-senate/20261030T162619Z.json.gz
data/live/2024-11-05/snap/results-hawaii-us-senate/20261030T162619Z.json.gz
data/live/2024-11-05/snap/results-west-virginia-governor/20261030T162619Z.json.gz
zsh:1: no matches found: .venv*
research/fuente_principal_nyt.md:31:pocos hilos. Los feeds oficiales verificados (`feeds_*.md`) quedan como control cruzado.
model/project.py:23:victoria y de control de cada cámara.
model/project.py:346:    def summary(self, control):
model/project.py:369:        for off, ctl in control.items():
model/project.py:408:def control_from_raw(date):
model/project.py:429:    s = m.summary(control_from_raw(a.date))
model/rehearse.py:101:        s = m.summary(P.control_from_raw("2024-11-05"))

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "python3 -c 'import json,collections,importlib.util
for x in (\"numpy\",\"pandas\",\"scipy\"): print(x,bool(importlib.util.find_spec(x)))
for year in (\"2024-11-05\",\"2026-11-03\"):
 for off in (\"senate\",\"house\"):
  d=json.load(open(f\"data/live/{year}/raw/results-{off}.json\"))
  print(year,off,\"control\",json.dumps(d[\"partyControlData\"])[:6000])
  print(\"races\",len(d[\"races\"]),collections.Counter((r.get(\"race_type_id\"),r.get(\"office_id\")) for r in d[\"races\"]))
  for r in d[\"races\"]:
   if off==\"senate\" and any(s in r.get(\"url\",\"\") for s in (\"nebraska\",\"maine\",\"vermont\")):
    print(\"example\",r[\"nyt_id\"],r.get(\"url\"),r.get(\"outcome\"),r.get(\"candidate_metadata\"))
 print(\"unit\",json.dumps(d[\"races\"][0][\"reporting_units\"][0])[:5000])'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 0ms:
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-2RWAQ7uB' (errno=Operation not permitted)
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-5KlURTHQ' (errno=Operation not permitted)
numpy False
pandas False
scipy False
2024-11-05 senate control {"count": 1, "results": [{"state": "United States", "offices": {"S": {"total": 100, "office": "U.S. Senate", "to_win": {"DEM": 51, "GOP": 51, "OTH": 51}, "office_id": "S", "open_seats": 34, "lg_party_id": null, "is_reporting": true, "party_balance": {"DEM": {"party": "Democrat", "seats": 47, "winner": false, "party_id": "DEM", "flip_count": 0, "no_election": 28, "controlled_at": null, "candidate_metadata": null, "party_abbreviation": "Dem."}, "GOP": {"party": "Republican", "seats": 53, "winner": true, "party_id": "GOP", "flip_count": 4, "no_election": 38, "controlled_at": "2024-11-06T05:06:56.208171+00:00", "candidate_metadata": null, "party_abbreviation": "Rep."}, "OTH": {"party": "Independent", "seats": 0, "winner": false, "party_id": "OTH", "flip_count": 0, "no_election": 0, "controlled_at": null, "candidate_metadata": null, "party_abbreviation": "Ind."}}, "model_settings": {"end_time": null, "start_time": null, "model_status": null}, "current_control": {"DEM": 48, "GOP": 49, "OTH": 4}, "num_races_called": 34, "no_election_seats": 66, "nyt_model_estimates": null}}, "state_postal": "US"}]}
races 34 Counter({('G', 'S'): 33, ('W', 'S'): 1})
example ME-G-S-2024-11-05 https://www.nytimes.com/interactive/2024/11/05/us/elections/results-maine-us-senate.html {'won': ['king-a'], 'gained': False, 'called_by': ['ap'], 'electoral_votes': None, 'advanced_to_runoff': [], 'runoff_accepted_at': [], 'winner_accepted_at': ['2024-11-07T15:15:09.597501+00:00']} {'king-a': {'order': 1, 'party': {'name': 'Independent', 'nyt_id': 'IND', 'abbreviation': 'Ind.'}, 'nyt_id': 'king-a', 'suffix': 'Jr.', 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/ME-G-S-2024-11-05-king-a-83147.png', 'incumbent': True, 'last_name': 'King', 'first_name': 'Angus', 'middle_name': 'S.', 'ballot_order': 3, 'party_caucus': {'name': 'Democrat', 'nyt_id': 'DEM', 'abbreviation': 'Dem.'}, 'nyt_candidate_id': 83147, 'nyt_candidate_race_id': 102044639}, 'cherry-j': {'order': 4, 'party': {'name': 'Independent', 'nyt_id': 'IND', 'abbreviation': 'Ind.'}, 'nyt_id': 'cherry-j', 'suffix': None, 'img_url': None, 'incumbent': False, 'last_name': 'Cherry', 'first_name': 'Jason', 'middle_name': 'S.', 'ballot_order': 1, 'party_caucus': None, 'nyt_candidate_id': 83146, 'nyt_candidate_race_id': 102044638}, 'costello-d': {'order': 2, 'party': {'name': 'Democrat', 'nyt_id': 'DEM', 'abbreviation': 'Dem.'}, 'nyt_id': 'costello-d', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/ME-D-S-1-2024-06-11-costello-d-71594.png', 'incumbent': False, 'last_name': 'Costello', 'first_name': 'David', 'middle_name': 'Allen', 'ballot_order': 2, 'party_caucus': None, 'nyt_candidate_id': 83144, 'nyt_candidate_race_id': 102044636}, 'kouzounas-d': {'order': 3, 'party': {'name': 'Republican', 'nyt_id': 'GOP', 'abbreviation': 'Rep.'}, 'nyt_id': 'kouzounas-d', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/ME-R-S-1-2024-06-11-kouzounas-d-71599.png', 'incumbent': False, 'last_name': 'Kouzounas', 'first_name': 'Demi', 'middle_name': None, 'ballot_order': 4, 'party_caucus': None, 'nyt_candidate_id': 83145, 'nyt_candidate_race_id': 102044637}, 'total_writeins': {'order': 5, 'party': {'name': '', 'nyt_id': 'OTH', 'abbreviation': ''}, 'nyt_id': 'total_writeins', 'suffix': None, 'img_url': None, 'incumbent': False, 'last_name': 'Total Write-ins', 'first_name': None, 'middle_name': None, 'ballot_order': 5, 'party_caucus': None, 'nyt_candidate_id': 92753, 'nyt_candidate_race_id': 102054545}}
example NE-G-S-2024-11-05 https://www.nytimes.com/interactive/2024/11/05/us/elections/results-nebraska-us-senate.html {'won': ['fischer-d'], 'gained': False, 'called_by': ['ap'], 'electoral_votes': None, 'advanced_to_runoff': [], 'runoff_accepted_at': [], 'winner_accepted_at': ['2024-11-06T05:06:56.208171+00:00']} {'osborn-d': {'order': 2, 'party': {'name': 'Nonpartisan', 'nyt_id': 'NP', 'abbreviation': 'Nonpartisan'}, 'nyt_id': 'osborn-d', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/NE-G-S-2024-11-05-osborn-d-89633.png', 'incumbent': False, 'last_name': 'Osborn', 'first_name': 'Dan', 'middle_name': None, 'ballot_order': 2, 'party_caucus': None, 'nyt_candidate_id': 89633, 'nyt_candidate_race_id': 102051279}, 'fischer-d': {'order': 1, 'party': {'name': 'Republican', 'nyt_id': 'GOP', 'abbreviation': 'Rep.'}, 'nyt_id': 'fischer-d', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/NE-R-S-1-2024-05-14-fischer-d-68500.png', 'incumbent': True, 'last_name': 'Fischer', 'first_name': 'Deb', 'middle_name': None, 'ballot_order': 1, 'party_caucus': None, 'nyt_candidate_id': 85299, 'nyt_candidate_race_id': 102046822}}
example NE-S_W-S-2024-11-05 https://www.nytimes.com/interactive/2024/11/05/us/elections/results-nebraska-us-senate-special.html {'won': ['ricketts-p'], 'gained': None, 'called_by': ['ap'], 'electoral_votes': None, 'advanced_to_runoff': [], 'runoff_accepted_at': [], 'winner_accepted_at': ['2024-11-06T02:01:11.41923+00:00']} {'love-p': {'order': 2, 'party': {'name': 'Democrat', 'nyt_id': 'DEM', 'abbreviation': 'Dem.'}, 'nyt_id': 'love-p', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/NE-S_J-S-2024-05-14-love-p-68502.png', 'incumbent': False, 'last_name': 'Love', 'first_name': 'Preston', 'middle_name': None, 'ballot_order': 2, 'party_caucus': None, 'nyt_candidate_id': 85301, 'nyt_candidate_race_id': 102046833}, 'ricketts-p': {'order': 1, 'party': {'name': 'Republican', 'nyt_id': 'GOP', 'abbreviation': 'Rep.'}, 'nyt_id': 'ricketts-p', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/NE-S_K-S-2024-05-14-ricketts-p-68504.png', 'incumbent': True, 'last_name': 'Ricketts', 'first_name': 'Pete', 'middle_name': None, 'ballot_order': 1, 'party_caucus': None, 'nyt_candidate_id': 85302, 'nyt_candidate_race_id': 102046834}}
example VT-G-S-2024-11-05 https://www.nytimes.com/interactive/2024/11/05/us/elections/results-vermont-us-senate.html {'won': ['sanders-b'], 'gained': False, 'called_by': ['ap'], 'electoral_votes': None, 'advanced_to_runoff': [], 'runoff_accepted_at': [], 'winner_accepted_at': ['2024-11-06T00:00:54.559315+00:00']} {'hill-m': {'order': 5, 'party': {'name': 'Libertarian', 'nyt_id': 'LIB', 'abbreviation': 'Lib.'}, 'nyt_id': 'hill-m', 'suffix': None, 'img_url': None, 'incumbent': False, 'last_name': 'Hill', 'first_name': 'Matt', 'middle_name': None, 'ballot_order': 3, 'party_caucus': None, 'nyt_candidate_id': 88477, 'nyt_candidate_race_id': 102050073}, 'berry-s': {'order': 3, 'party': {'name': 'Independent', 'nyt_id': 'IND', 'abbreviation': 'Ind.'}, 'nyt_id': 'berry-s', 'suffix': None, 'img_url': None, 'incumbent': False, 'last_name': 'Berry', 'first_name': 'Steve', 'middle_name': None, 'ballot_order': 1, 'party_caucus': None, 'nyt_candidate_id': 88479, 'nyt_candidate_race_id': 102050075}, 'malloy-g': {'order': 2, 'party': {'name': 'Republican', 'nyt_id': 'GOP', 'abbreviation': 'Rep.'}, 'nyt_id': 'malloy-g', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/VT-R-S-2024-08-13-malloy-g-76721.png', 'incumbent': False, 'last_name': 'Malloy', 'first_name': 'Gerald', 'middle_name': None, 'ballot_order': 4, 'party_caucus': None, 'nyt_candidate_id': 88480, 'nyt_candidate_race_id': 102050076}, 'sanders-b': {'order': 1, 'party': {'name': 'Independent', 'nyt_id': 'IND', 'abbreviation': 'Ind.'}, 'nyt_id': 'sanders-b', 'suffix': None, 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/VT-D-S-2024-08-13-sanders-b-76720.png', 'incumbent': True, 'last_name': 'Sanders', 'first_name': 'Bernie', 'middle_name': None, 'ballot_order': 5, 'party_caucus': {'name': 'Democrat', 'nyt_id': 'DEM', 'abbreviation': 'Dem.'}, 'nyt_candidate_id': 88475, 'nyt_candidate_race_id': 102050071}, 'schoville-j': {'order': 6, 'party': {'name': 'Other', 'nyt_id': 'PJP', 'abbreviation': 'Other'}, 'nyt_id': 'schoville-j', 'suffix': None, 'img_url': None, 'incumbent': False, 'last_name': 'Schoville', 'first_name': 'Justin', 'middle_name': None, 'ballot_order': 6, 'party_caucus': None, 'nyt_candidate_id': 88478, 'nyt_candidate_race_id': 102050074}, 'greenstein-m': {'order': 4, 'party': {'name': 'Independent', 'nyt_id': 'OTH', 'abbreviation': 'Ind.'}, 'nyt_id': 'greenstein-m', 'suffix': None, 'img_url': None, 'incumbent': False, 'last_name': 'Greenstein', 'first_name': 'Mark Stewart', 'middle_name': None, 'ballot_order': 2, 'party_caucus': None, 'nyt_candidate_id': 88476, 'nyt_candidate_race_id': 102050072}}
2024-11-05 house control {"count": 1, "results": [{"state": "United States", "offices": {"H": {"total": 435, "office": "U.S. House", "to_win": {"DEM": 218, "GOP": 218, "OTH": 218}, "office_id": "H", "open_seats": 435, "lg_party_id": null, "is_reporting": true, "party_balance": {"DEM": {"party": "Democrat", "seats": 215, "winner": false, "party_id": "DEM", "flip_count": 4, "no_election": 0, "controlled_at": null, "candidate_metadata": null, "party_abbreviation": "Dem."}, "GOP": {"party": "Republican", "seats": 220, "winner": true, "party_id": "GOP", "flip_count": 5, "no_election": 0, "controlled_at": "2024-11-14T03:28:15.758163+00:00", "candidate_metadata": null, "party_abbreviation": "Rep."}, "OTH": {"party": "Independent", "seats": 0, "winner": false, "party_id": "OTH", "flip_count": 0, "no_election": 0, "controlled_at": null, "candidate_metadata": null, "party_abbreviation": "Ind."}}, "model_settings": {"end_time": null, "start_time": null, "model_status": null}, "current_control": {"DEM": 214, "GOP": 220, "OTH": 0}, "num_races_called": 435, "no_election_seats": 0, "nyt_model_estimates": null}}, "state_postal": "US"}]}
races 435 Counter({('G', 'H'): 429, ('L', 'H'): 6})
unit {"eevp": 100, "name": "Alabama", "level": "state", "nyt_id": "AL-state", "eevp_max": 100, "state_abb": "Ala.", "candidates": [{"votes": {"total": 258619}, "leader": true, "nyt_id": "moore-b", "nyt_model_estimates": null, "nyt_candidate_race_id": 102041140}, {"votes": {"total": 70929}, "leader": false, "nyt_id": "holmes-t", "nyt_model_estimates": null, "nyt_candidate_race_id": 102041139}], "fips_state": "01", "fips_county": null, "fips_suffix": null, "total_votes": 329548, "state_postal": "AL", "precincts_total": 258, "nyt_model_estimates": null, "precincts_reporting": 258, "total_expected_vote": 329548}
2026-11-03 senate control {"count": 1, "results": [{"state_postal": "US", "state": "United States", "offices": {"S": {"office_id": "S", "office": "U.S. Senate", "lg_party_id": "GOP", "total": 100, "open_seats": 35, "no_election_seats": 65, "num_races_called": 0, "to_win": {"DEM": 51, "GOP": 50, "OTH": 51}, "party_balance": {"DEM": {"party_id": "DEM", "party": "Democrat", "party_abbreviation": "Dem.", "flip_count": 0, "seats": 34, "no_election": 34, "winner": false, "candidate_metadata": null, "controlled_at": null}, "GOP": {"party_id": "GOP", "party": "Republican", "party_abbreviation": "Rep.", "flip_count": 0, "seats": 31, "no_election": 31, "winner": false, "candidate_metadata": null, "controlled_at": null}, "OTH": {"party_id": "OTH", "party": "Independent", "party_abbreviation": "Ind.", "flip_count": 0, "seats": 0, "no_election": 0, "winner": false, "candidate_metadata": null, "controlled_at": null}}, "current_control": {"DEM": 45, "GOP": 57, "OTH": 2}, "nyt_model_estimates": null, "nyt_model_chamber": null, "model_settings": {"model_status": null, "model_inactive_reason": null, "start_time": null, "end_time": null}, "is_reporting": false}}}]}
races 35 Counter({('G', 'S'): 33, ('W', 'S'): 2})
example ME-G-S-2026-11-03 https://www.nytimes.com/interactive/2026/11/03/us/elections/results-maine-us-senate.html {'won': [], 'advanced_to_runoff': [], 'called_by': [], 'runoff_accepted_at': [], 'winner_accepted_at': [], 'gained': None, 'electoral_votes': None} {'collins-s': {'nyt_id': 'collins-s', 'nyt_candidate_id': 115100, 'nyt_candidate_race_id': 102076896, 'first_name': 'Susan', 'middle_name': 'M.', 'last_name': 'Collins', 'suffix': None, 'pronoun': 'she', 'img_url': 'https://static01.nyt.com/elections-assets/2026/headshots/ME-G-S-2026-11-03-collins-s-115100.png', 'incumbent': True, 'ballot_order': 1, 'order': 1, 'party': {'nyt_id': 'GOP', 'name': 'Republican', 'abbreviation': 'Rep.'}, 'party_caucus': None, 'groups': None, 'color_number': 1}, 'jackson-t': {'nyt_id': 'jackson-t', 'nyt_candidate_id': 115101, 'nyt_candidate_race_id': 102076897, 'first_name': 'Troy', 'middle_name': 'D.', 'last_name': 'Jackson', 'suffix': None, 'pronoun': 'he', 'img_url': 'https://static01.nyt.com/elections-assets/2026/headshots/ME-G-S-2026-11-03-jackson-t-115101.png', 'incumbent': False, 'ballot_order': 2, 'order': 2, 'party': {'nyt_id': 'DEM', 'name': 'Democrat', 'abbreviation': 'Dem.'}, 'party_caucus': None, 'groups': None, 'color_number': 1}, 'olson_writein-s': {'nyt_id': 'olson_writein-s', 'nyt_candidate_id': 126914, 'nyt_candidate_race_id': 102088710, 'first_name': 'Sigrid', 'middle_name': 'Ann', 'last_name': 'Olson (write-in)', 'suffix': None, 'pronoun': None, 'img_url': None, 'incumbent': False, 'ballot_order': 4, 'order': 3, 'party': {'nyt_id': 'DEM', 'name': 'Democrat', 'abbreviation': 'Dem.'}, 'party_caucus': None, 'groups': None, 'color_number': 2}, 'webb_writein-a': {'nyt_id': 'webb_writein-a', 'nyt_candidate_id': 126926, 'nyt_candidate_race_id': 102088722, 'first_name': 'Ashley', 'middle_name': 'J.', 'last_name': 'Webb (write-in)', 'suffix': None, 'pronoun': 'she', 'img_url': None, 'incumbent': False, 'ballot_order': 8, 'order': 4, 'party': {'nyt_id': 'DEM', 'name': 'Democrat', 'abbreviation': 'Dem.'}, 'party_caucus': None, 'groups': None, 'color_number': 3}, 'andrews_writein-b': {'nyt_id': 'andrews_writein-b', 'nyt_candidate_id': 126913, 'nyt_candidate_race_id': 102088709, 'first_name': 'Brent', 'middle_name': None, 'last_name': 'Andrews (write-in)', 'suffix': None, 'pronoun': None, 'img_url': None, 'incumbent': False, 'ballot_order': 3, 'order': 5, 'party': {'nyt_id': 'UNA', 'name': 'Independent', 'abbreviation': 'Ind.'}, 'party_caucus': None, 'groups': None, 'color_number': 1}, 'oswald_writein-g': {'nyt_id': 'oswald_writein-g', 'nyt_candidate_id': 126915, 'nyt_candidate_race_id': 102088711, 'first_name': 'Gina', 'middle_name': None, 'last_name': 'Oswald (write-in)', 'suffix': None, 'pronoun': None, 'img_url': None, 'incumbent': False, 'ballot_order': 5, 'order': 6, 'party': {'nyt_id': 'IND', 'name': 'Independent', 'abbreviation': 'Ind.'}, 'party_caucus': None, 'groups': None, 'color_number': 2}, 'steinberger_writein-j': {'nyt_id': 'steinberger_writein-j', 'nyt_candidate_id': 126925, 'nyt_candidate_race_id': 102088721, 'first_name': 'Joseph', 'middle_name': None, 'last_name': 'Steinberger (write-in)', 'suffix': None, 'pronoun': None, 'img_url': None, 'incumbent': False, 'ballot_order': 6, 'order': 7, 'party': {'nyt_id': 'OTH', 'name': 'Independent', 'abbreviation': 'Ind.'}, 'party_caucus': None, 'groups': None, 'color_number': 3}, 'turcotte_writein-m': {'nyt_id': 'turcotte_writein-m', 'nyt_candidate_id': 126924, 'nyt_candidate_race_id': 102088720, 'first_name': 'Michael', 'middle_name': None, 'last_name': 'Turcotte (write-in)', 'suffix': None, 'pronoun': None, 'img_url': None, 'incumbent': False, 'ballot_order': 7, 'order': 8, 'party': {'nyt_id': 'UNR', 'name': 'Unenrolled', 'abbreviation': 'Other'}, 'party_caucus': None, 'groups': None, 'color_number': 4}}
example NE-G-S-2026-11-03 https://www.nytimes.com/interactive/2026/11/03/us/elections/results-nebraska-us-senate.html {'won': [], 'advanced_to_runoff': [], 'called_by': [], 'runoff_accepted_at': [], 'winner_accepted_at': [], 'gained': None, 'electoral_votes': None} {'ricketts-p': {'nyt_id': 'ricketts-p', 'nyt_candidate_id': 116236, 'nyt_candidate_race_id': 102078032, 'first_name': 'Pete', 'middle_name': None, 'last_name': 'Ricketts', 'suffix': None, 'pronoun': 'he', 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/NE-S_K-S-2024-05-14-ricketts-p-68504.png', 'incumbent': True, 'ballot_order': 1, 'order': 1, 'party': {'nyt_id': 'GOP', 'name': 'Republican', 'abbreviation': 'Rep.'}, 'party_caucus': None, 'groups': None}, 'marvin-m': {'nyt_id': 'marvin-m', 'nyt_candidate_id': 116235, 'nyt_candidate_race_id': 102078031, 'first_name': 'Mike', 'middle_name': None, 'last_name': 'Marvin', 'suffix': None, 'pronoun': 'he', 'img_url': None, 'incumbent': False, 'ballot_order': 2, 'order': 2, 'party': {'nyt_id': 'IND', 'name': 'Independent', 'abbreviation': 'Ind.'}, 'party_caucus': None, 'groups': None}, 'richards-r': {'nyt_id': 'richards-r', 'nyt_candidate_id': 127760, 'nyt_candidate_race_id': 102089556, 'first_name': 'Robin', 'middle_name': None, 'last_name': 'Richards', 'suffix': None, 'pronoun': None, 'img_url': None, 'incumbent': False, 'ballot_order': 3, 'order': 3, 'party': {'nyt_id': 'NWK', 'name': 'Other', 'abbreviation': 'Other'}, 'party_caucus': None, 'groups': None}, 'conboy-c': {'nyt_id': 'conboy-c', 'nyt_candidate_id': 127761, 'nyt_candidate_race_id': 102089557, 'first_name': 'Chuck', 'middle_name': None, 'last_name': 'Conboy', 'suffix': None, 'pronoun': None, 'img_url': None, 'incumbent': False, 'ballot_order': 4, 'order': 4, 'party': {'nyt_id': 'AFI', 'name': 'Other', 'abbreviation': 'Other'}, 'party_caucus': None, 'groups': None}, 'osborn-d': {'nyt_id': 'osborn-d', 'nyt_candidate_id': 116234, 'nyt_candidate_race_id': 102078030, 'first_name': 'Dan', 'middle_name': None, 'last_name': 'Osborn', 'suffix': None, 'pronoun': 'he', 'img_url': 'https://static01.nyt.com/elections-assets/2024/headshots/NE-G-S-2024-11-05-osborn-d-89633.png', 'incumbent': False, 'ballot_order': 5, 'order': 5, 'party': {'nyt_id': 'IND', 'name': 'Independent', 'abbreviation': 'Ind.'}, 'party_caucus': None, 'groups': None}}
2026-11-03 house control {"count": 1, "results": [{"state_postal": "US", "state": "United States", "offices": {"H": {"office_id": "H", "office": "U.S. House", "lg_party_id": null, "total": 435, "open_seats": 435, "no_election_seats": 0, "num_races_called": 0, "to_win": {"DEM": 218, "GOP": 218, "OTH": 218}, "party_balance": {"DEM": {"party_id": "DEM", "party": "Democrat", "party_abbreviation": "Dem.", "flip_count": 0, "seats": 0, "no_election": 0, "winner": false, "candidate_metadata": null, "controlled_at": null, "votes": 0}, "GOP": {"party_id": "GOP", "party": "Republican", "party_abbreviation": "Rep.", "flip_count": 0, "seats": 0, "no_election": 0, "winner": false, "candidate_metadata": null, "controlled_at": null, "votes": 0}, "OTH": {"party_id": "OTH", "party": "Independent", "party_abbreviation": "Ind.", "flip_count": 0, "seats": 0, "no_election": 0, "winner": false, "candidate_metadata": null, "controlled_at": null, "votes": 0}}, "current_control": {"DEM": 214, "GOP": 218, "OTH": 1}, "nyt_model_estimates": null, "nyt_model_chamber": null, "model_settings": {"model_status": null, "model_inactive_reason": null, "start_time": null, "end_time": null}, "is_reporting": false, "votes": 0}}}]}
races 436 Counter({('G', 'H'): 430, ('L', 'H'): 6})
unit {"nyt_id": "US-national", "name": "United States", "fips_state": null, "fips_county": null, "fips_suffix": null, "level": "national", "state_postal": "US", "state_abb": null, "eevp": 0, "eevp_by_vote_type": {"total": 0}, "eevp_max": 99, "expected_vote_by_vote_type": {"total": 120711369}, "total_votes": 0, "total_expected_vote": 120711369, "precincts_reporting": 0, "precincts_total": 172484, "nyt_model_estimates": null, "candidates": [{"votes": {"total": 0}, "leader": false, "nyt_id": "democrat", "nyt_model_estimates": null, "nyt_candidate_race_id": 102088698}, {"votes": {"total": 0}, "leader": false, "nyt_id": "republican", "nyt_model_estimates": null, "nyt_candidate_race_id": 102088699}, {"votes": {"total": 0}, "leader": false, "nyt_id": "other", "nyt_model_estimates": null, "nyt_candidate_race_id": 102090391}], "demographic_categories": []}

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "command -v -a python python3 uv; ls /Users/juan/.cache/uv/archive-v0 | head; python3 -c 'import json,collections
from pathlib import Path
for year in (\"2024-11-05\",\"2026-11-03\"):
 print(\"YEAR\",year)
 d=json.load(open(f\"data/live/{year}/raw/results-house.json\"))
 print(\"non district\",[(r[\"nyt_id\"],[(u[\"level\"],u.get(\"state_postal\")) for u in r[\"reporting_units\"]]) for r in d[\"races\"] if not any(u[\"level\"]==\"state\" for u in r[\"reporting_units\"])])
 for f in Path(f\"data/live/{year}/raw\").glob(\"*.json\"):
  if f.stem in (\"results-senate\",\"results-governor\"): continue
  for r in json.load(open(f)).get(\"races\",[]):
   us=r.get(\"reporting_units\",[]); levels=collections.Counter(u[\"level\"] for u in us)
   if len(levels)>2: print(\"mixed\",f.stem,r[\"nyt_id\"],levels,[(l,sum(u.get(\"total_votes\") or 0 for u in us if u[\"level\"]==l),sum(u.get(\"total_expected_vote\") or 0 for u in us if u[\"level\"]==l)) for l in levels])
'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 57ms:
zsh:1: command not found: -v
-0JmkGXFLFrQwzmd
-7lE-KpErHkc-7wF
-JDbBzRap8EbzHY4
-QWywi3bHq9m3-1n
-UWOaM8UBMSE5T-S
-XKNbZvYKzAbr2nK
-ivGKxRBdC_iScvc
-jOedsSgenqPSYjU
-rKAsWzz7L6_pT73
-vHs5m1NO8hwSBQ2
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-5Ye3Xu4K' (errno=Operation not permitted)
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-9pwkmkPh' (errno=Operation not permitted)
YEAR 2024-11-05
non district []
YEAR 2026-11-03
non district [('US-G-H-2026-11-03', [('national', 'US')])]
mixed results-house AK-G-H-1-2026-11-03 Counter({'state_house_district': 40, 'state': 1, 'other': 1}) [('state', 0, 290928), ('other', 0, 148), ('state_house_district', 0, 290780)]
mixed results-house CT-G-H-1-2026-11-03 Counter({'other': 24, 'county': 4, 'state': 1}) [('state', 0, 299823), ('county', 0, 299823), ('other', 0, 45907)]
mixed results-house CT-G-H-3-2026-11-03 Counter({'county': 4, 'other': 4, 'state': 1}) [('state', 0, 278546), ('county', 0, 278546), ('other', 0, 7340)]
mixed results-house CT-G-H-4-2026-11-03 Counter({'other': 48, 'county': 3, 'state': 1}) [('state', 0, 310011), ('county', 0, 310011), ('other', 0, 107557)]
mixed results-house CT-G-H-5-2026-11-03 Counter({'other': 19, 'county': 5, 'state': 1}) [('state', 0, 276194), ('county', 0, 276194), ('other', 0, 33548)]
mixed results-house IL-G-H-1-2026-11-03 Counter({'county': 3, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 246723), ('county', 0, 246723), ('city', 0, 120958), ('other', 0, 35392)]
mixed results-house IL-G-H-2-2026-11-03 Counter({'county': 8, 'city': 2, 'other': 2, 'state': 1}) [('state', 0, 238107), ('county', 0, 238107), ('city', 0, 45003), ('other', 0, 121414)]
mixed results-house IL-G-H-3-2026-11-03 Counter({'county': 2, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 228734), ('county', 0, 228734), ('city', 0, 134197), ('other', 0, 26599)]
mixed results-house IL-G-H-4-2026-11-03 Counter({'county': 2, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 170783), ('county', 0, 170783), ('city', 0, 70405), ('other', 0, 84357)]
mixed results-house IL-G-H-5-2026-11-03 Counter({'county': 2, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 228803), ('county', 0, 228803), ('city', 0, 134943), ('other', 0, 78207)]
mixed results-house IL-G-H-6-2026-11-03 Counter({'county': 2, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 260867), ('county', 0, 260867), ('city', 0, 21417), ('other', 0, 116141)]
mixed results-house IL-G-H-7-2026-11-03 Counter({'state': 1, 'county': 1, 'city': 1, 'other': 1}) [('state', 0, 207488), ('county', 0, 207488), ('city', 0, 154439), ('other', 0, 53049)]
mixed results-house IL-G-H-8-2026-11-03 Counter({'county': 3, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 229775), ('county', 0, 229775), ('city', 0, 1860), ('other', 0, 95989)]
mixed results-house IL-G-H-9-2026-11-03 Counter({'county': 3, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 233799), ('county', 0, 233799), ('city', 0, 67445), ('other', 0, 115700)]
mixed results-house IL-G-H-10-2026-11-03 Counter({'county': 3, 'state': 1, 'other': 1}) [('state', 0, 244729), ('county', 0, 244729), ('other', 0, 33967)]
mixed results-house IL-G-H-11-2026-11-03 Counter({'county': 8, 'state': 1, 'other': 1}) [('state', 0, 271686), ('county', 0, 271686), ('other', 0, 3601)]
mixed results-house IL-G-H-12-2026-11-03 Counter({'county': 34, 'state': 1, 'other': 1}) [('state', 0, 300804), ('county', 0, 300804), ('other', 0, 32668)]
mixed results-house IL-G-H-13-2026-11-03 Counter({'county': 7, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 274321), ('county', 0, 274321), ('city', 0, 5663), ('other', 0, 51089)]
mixed results-house IL-G-H-15-2026-11-03 Counter({'county': 35, 'state': 1, 'other': 1}) [('state', 0, 305985), ('county', 0, 305985), ('other', 0, 3149)]
mixed results-house IL-G-H-16-2026-11-03 Counter({'county': 21, 'city': 2, 'other': 2, 'state': 1}) [('state', 0, 285566), ('county', 0, 285566), ('city', 0, 26996), ('other', 0, 42144)]
mixed results-house IL-G-H-17-2026-11-03 Counter({'county': 14, 'city': 3, 'other': 3, 'state': 1}) [('state', 0, 251508), ('county', 0, 251508), ('city', 0, 60029), ('other', 0, 25639)]
mixed results-house ME-G-H-1-2026-11-03 Counter({'county': 6, 'state': 1, 'other': 1}) [('state', 0, 393991), ('county', 0, 393091), ('other', 0, 900)]
mixed results-house ME-G-H-2-2026-11-03 Counter({'county': 11, 'state': 1, 'other': 1}) [('state', 0, 341579), ('county', 0, 340679), ('other', 0, 900)]
mixed results-house MI-G-H-6-2026-11-03 Counter({'city': 9, 'county': 4, 'state': 1}) [('state', 0, 332768), ('county', 0, 332768), ('city', 0, 32308)]
mixed results-house MI-G-H-12-2026-11-03 Counter({'city': 7, 'county': 2, 'state': 1}) [('state', 0, 321731), ('county', 0, 321731), ('city', 0, 249747)]
mixed results-house MI-G-H-13-2026-11-03 Counter({'city': 20, 'state': 1, 'county': 1}) [('state', 0, 303358), ('county', 0, 303358), ('city', 0, 303358)]
mixed results-house MO-G-H-4-2026-11-03 Counter({'county': 24, 'state': 1, 'other': 1}) [('state', 0, 309846), ('county', 0, 309846), ('other', 0, 32780)]
mixed results-house MO-G-H-5-2026-11-03 Counter({'county': 2, 'state': 1, 'city': 1, 'other': 1}) [('state', 0, 278963), ('county', 0, 278963), ('city', 0, 103483), ('other', 0, 118318)]
mixed results-house MO-G-H-6-2026-11-03 Counter({'county': 39, 'state': 1, 'other': 1}) [('state', 0, 314294), ('county', 0, 314294), ('other', 0, 5312)]
mixed results-house RI-G-H-1-2026-11-03 Counter({'county': 3, 'state': 1, 'other': 1}) [('state', 0, 172132), ('county', 0, 172036), ('other', 0, 96)]
mixed results-house RI-G-H-2-2026-11-03 Counter({'county': 3, 'state': 1, 'other': 1}) [('state', 0, 221522), ('county', 0, 221425), ('other', 0, 97)]

hook: PostToolUse
hook: PostToolUse Completed
codex
Ya aparecen problemas concretos con los votos tipificados y la asignación de bancas cuando gana un independiente. Estoy contrastándolos con los JSON locales de 2024 y 2026 y revisando casos mínimos para precisar el efecto numérico.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "rg --files /Users/juan/.cache/uv/archive-v0 -g 'numpy/__init__.py' -g 'pandas/__init__.py' -g 'scipy/__init__.py' | head; which -a python3 uv; python3 -c 'import json,collections
from pathlib import Path
for year in (\"2024-11-05\",\"2026-11-03\"):
 stats=collections.Counter(); ex={}
 for f in Path(f\"data/live/{year}/raw\").glob(\"*.json\"):
  for r in json.load(open(f)).get(\"races\",[]):
   for u in r.get(\"reporting_units\",[]):
    ev=u.get(\"expected_vote_by_vote_type\") or {}; vt={k:v for k,v in ev.items() if k"'!="total" and v}
    if vt:
     stats[tuple(sorted(vt))]+=1; ex.setdefault(tuple(sorted(vt)),(f.stem,r["nyt_id"],u))
 print(year,stats)
 for k,v in ex.items(): print(k,json.dumps(v)[:3400])
print("same D plus O races")
d=json.load(open("data/live/2026-11-03/raw/results-house.json"))
for r in d["races"]:
 ps=[(c["nyt_id"],c.get("party",{}).get("nyt_id")) for c in r["candidate_metadata"].values()]
 if not any(p=="GOP" for c,p in ps): print(r["nyt_id"],ps)
'"'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 2322ms:
/usr/bin/python3
/opt/homebrew/bin/uv
/opt/homebrew/bin/uv
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-B1QfbltN' (errno=Operation not permitted)
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-BF6vbXCG' (errno=Operation not permitted)
2024-11-05 Counter()
2026-11-03 Counter()
same D plus O races
CA-G-H-4-2026-11-03 [('thompson-m', 'DEM'), ('jones-e', 'DEM')]
CA-G-H-6-2026-11-03 [('kiley-k', 'NPP'), ('pan-r', 'DEM')]
CA-G-H-7-2026-11-03 [('matsui-d', 'DEM'), ('vang-m', 'DEM')]
CA-G-H-11-2026-11-03 [('chan-c', 'DEM'), ('wiener-s', 'DEM')]
CA-G-H-12-2026-11-03 [('simon-l', 'DEM'), ('joyce-j', 'DEM')]
CA-G-H-14-2026-11-03 [('wahab-a', 'DEM'), ('hernandez-m', 'DEM')]
CA-G-H-29-2026-11-03 [('rivas-l', 'DEM'), ('dueas-a', 'DEM')]
CA-G-H-34-2026-11-03 [('gomez-j', 'DEM'), ('gonzalestorres-a', 'DEM')]
CA-G-H-37-2026-11-03 [('kamlagerdove-s', 'DEM'), ('mota-s', 'DEM')]
FL-G-H-10-2026-11-03 [('frost-m', 'DEM')]
MA-G-H-1-2026-11-03 [('neal-r', 'DEM'), ('milleron-n', 'IND')]
MA-G-H-2-2026-11-03 [('mcgovern-j', 'DEM')]
MA-G-H-5-2026-11-03 [('clark-k', 'DEM')]
MA-G-H-7-2026-11-03 [('pressley-a', 'DEM')]
NJ-G-H-8-2026-11-03 [('menendez-r', 'DEM'), ('eliopoulos-a', 'OTH'), ('honts-c', 'OTH'), ('hughey-d', 'OTH')]
PA-G-H-3-2026-11-03 [('rabb-c', 'DEM'), ('mahoney-d', 'IND')]
WI-G-H-2-2026-11-03 [('pocan-m', 'DEM')]

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "ls /Users/juan/.local/share/uv/python; rg --files /Users/juan/.cache/uv/archive-v0 | rg '/(numpy|pandas|scipy)/__init__.py"'$'"' | head -12; python3 -c 'import csv,collections,json
for yr in (\"2024-11-05\",\"2026-11-03\"):
 rows=list(csv.DictReader(open(f\"data/live/{yr}/units.csv\")))
 print(yr,\"levels\",collections.Counter(r[\"level\"] for r in rows))
 for rid in (\"CA-G-H-6-2026-11-03\",\"NE-G-S-2024-11-05\",\"ME-G-S-2024-11-05\",\"VT-G-S-2024-11-05\"):
  rs=[r for r in rows if r[\"race_id\"]==rid]
  if rs: print(\"selected rows\",rid,[(r[\"level\"],r[\"name\"],r[\"D\"],r[\"R\"],r[\"O\"],r[\"expected\"],r[\"total\"],r[\"parties\"],r[\"winner\"]) for r in rs[:2]])
'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 1581ms:
cpython-3.10-macos-aarch64-none
cpython-3.10.20-macos-aarch64-none
cpython-3.11-macos-aarch64-none
cpython-3.11.15-macos-aarch64-none
cpython-3.12-macos-aarch64-none
cpython-3.12.11-macos-aarch64-none
cpython-3.12.13-macos-aarch64-none
cpython-3.13-macos-aarch64-none
cpython-3.13.15-macos-aarch64-none
/Users/juan/.cache/uv/archive-v0/UuYgK9KYab2DhrNk/lib/python3.13/site-packages/pandas/__init__.py
/Users/juan/.cache/uv/archive-v0/aqxE6Nds1JloxK5n/lib/python3.13/site-packages/pandas/__init__.py
/Users/juan/.cache/uv/archive-v0/nA9yI81h3pSb24Z2/lib/python3.13/site-packages/pandas/__init__.py
/Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/lib/python3.13/site-packages/pandas/__init__.py
/Users/juan/.cache/uv/archive-v0/JVavIP1BteLp95d3/lib/python3.13/site-packages/pandas/__init__.py
/Users/juan/.cache/uv/archive-v0/UuYgK9KYab2DhrNk/lib/python3.13/site-packages/pandas/compat/numpy/__init__.py
/Users/juan/.cache/uv/archive-v0/aqxE6Nds1JloxK5n/lib/python3.13/site-packages/pandas/compat/numpy/__init__.py
/Users/juan/.cache/uv/archive-v0/nA9yI81h3pSb24Z2/lib/python3.13/site-packages/pandas/compat/numpy/__init__.py
/Users/juan/.cache/uv/archive-v0/UuYgK9KYab2DhrNk/lib/python3.13/site-packages/numpy/__init__.py
/Users/juan/.cache/uv/archive-v0/6ZUDYyQr832Hhbub/lib/python3.13/site-packages/pandas/__init__.py
/Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/lib/python3.13/site-packages/pandas/compat/numpy/__init__.py
/Users/juan/.cache/uv/archive-v0/JVavIP1BteLp95d3/lib/python3.13/site-packages/pandas/compat/numpy/__init__.py
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-NvQktq2Y' (errno=Operation not permitted)
python3: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
python3: error: couldn't create cache file '/tmp/xcrun_db-6qnVCPN9' (errno=Operation not permitted)
2024-11-05 levels Counter({'county': 2455, 'township': 1789, 'state': 480})
selected rows NE-G-S-2024-11-05 [('state', 'Nebraska', '0', '499124', '436493', '935617', '935617', 'OR', 'R'), ('county', 'Douglas', '0', '111211', '157317', '268528', '268528', 'OR', 'R')]
selected rows ME-G-S-2024-11-05 [('state', 'Maine', '88875', '284434', '447763', '821072', '821072', 'DOOOR', 'O'), ('township', 'Portland', '10737', '5543', '29016', '45296', '45296', 'DOOOR', 'O')]
selected rows VT-G-S-2024-11-05 [('state', 'Vermont', '0', '116512', '246343', '362855', '362855', 'OOOOOR', 'O'), ('township', 'Burlington', '0', '2118', '18021', '20139', '20139', 'OOOOOR', 'O')]
2026-11-03 levels Counter({'county': 3737, 'state': 506, 'other': 123, 'city': 53, 'state_house_district': 40, 'national': 1})
selected rows CA-G-H-6-2026-11-03 [('state', 'California', '0', '0', '0', '248247', '0', 'DO', ''), ('county', 'Placer', '0', '0', '0', '92733', '0', 'DO', '')]

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "ls /Users/juan/.cache/uv/archive-v0/UuYgK9KYab2DhrNk/bin; ls /Users/juan/.cache/uv/archive-v0/UuYgK9KYab2DhrNk/lib/python3.13/site-packages | head -25; rg --files /Users/juan/.cache/uv/archive-v0 | rg '/scipy/__init__.py"'$'"' | head -4" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 2065ms:
activate
activate.bat
activate.fish
activate.nu
activate.ps1
activate.xsh
activate_this.py
deactivate.bat
f2py
numpy-config
pydoc.bat
python
python3
python3.13
__pycache__
_virtualenv.pth
_virtualenv.py
dateutil
numpy
numpy-2.5.4.dist-info
pandas
pandas-3.1.0.dist-info
pyarrow
pyarrow-26.0.0.dist-info
python_dateutil-3.0.0.dist-info
six-1.17.0.dist-info
six.py
tzdata
tzdata-2026.5.dist-info
/Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/lib/python3.13/site-packages/scipy/__init__.py
/Users/juan/.cache/uv/archive-v0/kh_57iP-Yyyuflmz/lib/python3.13/site-packages/scipy/__init__.py
/Users/juan/.cache/uv/archive-v0/aqxE6Nds1JloxK5n/lib/python3.13/site-packages/scipy/__init__.py
/Users/juan/.cache/uv/archive-v0/Yj7LIN14c4yz505h/lib/python3.13/site-packages/scipy/__init__.py

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 /Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/bin/python -c 'import numpy,pandas,scipy; print(numpy.__version__,pandas.__version__,scipy.__version__)'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 487ms:
2.5.4 3.1.0 1.18.1

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "OPENBLAS_NUM_THREADS=6 PYTHONDONTWRITEBYTECODE=1 /Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/bin/python -c 'import sys, numpy as np, pandas as pd
sys.path.insert(0,\"model\"); import project as P
base=P.load(\"2026-11-03\")
def unit(rid=\"demo\",parties=\"DR\",D=300,R=200,O=0,expected=1000,level=\"state\"):
 d=base[(base.office==\"S\") & (base.level==\"state\")].iloc[[0]].copy(); d.loc[:,\"race_id\"]=rid; d.loc[:,\"unit_id\"]=rid+level; d.loc[:,\"parties\"]=parties; d.loc[:,\"D\"]=D; d.loc[:,\"R\"]=R; d.loc[:,\"O\"]=O; d.loc[:,\"total\"]=D+R+O; d.loc[:,\"expected\"]=expected; d.loc[:,\"eevp\"]=100*(D+R+O)/expected; d.loc[:,\"b\"]=.5; d.loc[:,\"level\"]=level; d.loc[:,\"rating\"]=\"tossup\"; d.loc[:,\"winner\"]=\"\"; return d
ctl={\"S\":dict(total=100,D_hold=34,I_hold=0,D_needs=51,R_needs=50)}
for label,d in [(\"no GOP opponent\",unit(parties=\"DO\",D=250,R=0,O=250)),(\"O winner but D side\",unit(parties=\"DOR\",D=300,R=200,O=10).assign(winner=\"O\")),(\"same D\",unit(parties=\"DD\"))]:
 m=P.Model(d).fit().simulate(); s=m.summary(ctl); print(label, {k:s[\"races\"][0][k] for k in (\"side\",\"proj_B\",\"proj_R\",\"p_B_win\")}, s[\"chambers\"])
# O side with fully typed counts: correct remaining = 500
for side in (\"DR\",\"OR\"):
 d=unit(parties=side,D=300 if side==\"DR\" else 0,R=200,O=0 if side==\"DR\" else 300)
 d.loc[:,\"exp_advance\"]=1000; d.loc[:,\"D_advance\"]=d.D; d.loc[:,\"R_advance\"]=d.R; d.loc[:,\"O_advance\"]=d.O
 m=P.Model(d); u=m.u.iloc[0]; race=m.races.iloc[0]; got=sum(u[f\"{race.side}_advance\"]+u[\"R_advance\"]+u[\"O_advance\"] for _ in [0]); print(\"typed\",side,\"counted\",u.total,\"got\",got,\"remaining\",max(u.exp_advance-got,0))
# Missing typed category causes all untyped remainder to vanish
u=unit(); u.loc[:,\"exp_advance\"]=200; u.loc[:,\"D_advance\"]=120; u.loc[:,\"R_advance\"]=80
m=P.Model(u); print(\"partial exp types: actual remaining\",1000-500,\"modeled remaining\",max(200-200,0))
# Incomplete sublevel accepted
st=unit(); co=unit(D=270,R=180,expected=950,level=\"county\"); co.loc[:,\"unit_id\"]=\"county\"; mm=P.Model(pd.concat([st,co])); print(\"omitted county votes\",mm.u[[\"D\",\"R\",\"expected\"]].to_dict(\"records\"), \"race\",mm.races[[\"counted\",\"expected\"]].to_dict(\"records\"))
# Inspect existing 2024 partition coverage
old=P.load(\"2024-11-05\"); selected=P.pick_units(old)
for rid,g in selected.groupby(\"race_id\"):
 st=old[(old.race_id==rid)&(old.level==\"state\")]
 if len(st) and abs(g.total.sum()-st.total.iloc[0])>max(100,st.total.iloc[0]*.001): print(\"2024 coverage mismatch\",rid,g.level.iloc[0],\"chosen\",g.total.sum(),\"state\",st.total.iloc[0])
print(\"control2026\",P.control_from_raw(\"2026-11-03\"))
'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 876ms:
no GOP opponent {'side': 'D', 'proj_B': 75.71, 'proj_R': 24.29, 'p_B_win': 1.0} {'S': {'total': 100, 'D_needs': 51, 'R_needs': 50, 'p_D': 0.0, 'p_R': 1.0, 'D_med': 35, 'R_med': 65, 'I_med': 0, 'D_ci90': [35, 35], 'R_ci90': [65, 65], 'dist': {35: np.float64(1.0)}}}
O winner but D side {'side': 'D', 'proj_B': 57.78, 'proj_R': 42.22, 'p_B_win': 1.0} {'S': {'total': 100, 'D_needs': 51, 'R_needs': 50, 'p_D': 0.0, 'p_R': 1.0, 'D_med': 35, 'R_med': 65, 'I_med': 0, 'D_ci90': [35, 35], 'R_ci90': [65, 65], 'dist': {35: np.float64(1.0)}}}
same D {'side': 'D', 'proj_B': 0.0, 'proj_R': 100.0, 'p_B_win': 1.0} {'S': {'total': 100, 'D_needs': 51, 'R_needs': 50, 'p_D': 0.0, 'p_R': 1.0, 'D_med': 35, 'R_med': 65, 'I_med': 0, 'D_ci90': [35, 35], 'R_ci90': [65, 65], 'dist': {35: np.float64(1.0)}}}
typed DR counted 500 got 500 remaining 500.0
typed OR counted 500 got 800 remaining 200.0
partial exp types: actual remaining 500 modeled remaining 0
omitted county votes [{'D': 270, 'R': 180, 'expected': 950.0}] race [{'counted': 500.0, 'expected': 1000.0}]
control2026 {'S': {'total': 100, 'D_hold': 34, 'I_hold': 0, 'D_needs': 51, 'R_needs': 50}, 'H': {'total': 435, 'D_hold': 0, 'I_hold': 0, 'D_needs': 218, 'R_needs': 218}}

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "OPENBLAS_NUM_THREADS=6 PYTHONDONTWRITEBYTECODE=1 /Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/bin/python -c 'import sys,numpy as np,pandas as pd
sys.path.insert(0,\"model\"); import project as P; import rehearse as Q
d=P.load(\"2024-11-05\"); d=d[d.race_id==\"NE-G-S-2024-11-05\"].reset_index(drop=True)
n=len(d); state=(np.zeros(n),np.ones(n),np.zeros(n),np.ones(n)); z=Q.rebuild_state_rows(Q.synth(d,10,state,.04))
print(\"NE final true\",d[d.level==\"state\"][[\"D\",\"R\",\"O\"]].to_dict(\"records\")); print(\"NE synthetic final\",z[z.level==\"state\"][[\"D\",\"R\",\"O\"]].to_dict(\"records\")); print(\"NE truth metric\",max(d.iloc[0].D,d.iloc[0].O)/(max(d.iloc[0].D,d.iloc[0].O)+d.iloc[0].R))
m=P.Model(z).fit().simulate(); print(\"NE end simulation\",m.summary({})[\"races\"][0])
# Rebuild on existing mixed-level House input
h=P.load(\"2026-11-03\"); h=h[h.race_id==\"IL-G-H-7-2026-11-03\"].copy(); s=h[h.level==\"state\"].expected.iloc[0]; Q.rebuild_state_rows(h); print(\"IL7 original expected\",s,\"rebuilt\",h[h.level==\"state\"].expected.iloc[0])
'" in /Users/juan/dev/midterms-2026-proyeccion
 exited 1 in 160ms:
Traceback (most recent call last):
  File "<string>", line 2, in <module>
    sys.path.insert(0,"model"); import project as P; import rehearse as Q
                                                     ^^^^^^^^^^^^^^^^^^^^
  File "/Users/juan/dev/midterms-2026-proyeccion/model/rehearse.py", line 18, in <module>
    from claude_tqdm import tqdm  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/juan/.claude/tools/claude_tqdm.py", line 23, in <module>
    from tqdm import tqdm as _tqdm
ModuleNotFoundError: No module named 'tqdm'

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "rg --files /Users/juan/.cache/uv/archive-v0 | rg '/tqdm/__init__.py"'$'"' | head -4; nl -ba model/live.py" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 2108ms:
/Users/juan/.cache/uv/archive-v0/bZpT0vvm7eKoJIB5/lib/python3.13/site-packages/tqdm/__init__.py
/Users/juan/.cache/uv/archive-v0/kh_57iP-Yyyuflmz/lib/python3.13/site-packages/tqdm/__init__.py
/Users/juan/.cache/uv/archive-v0/r01Cb6yvOw5PQ7zA/lib/python3.13/site-packages/tqdm/__init__.py
/Users/juan/.cache/uv/archive-v0/nA9yI81h3pSb24Z2/lib/python3.13/site-packages/tqdm/__init__.py
     1	"""Circuito de la noche: bajar → proyectar → publicar.
     2	
     3	Cada --every segundos baja los JSON del NYT y corre el modelo sobre dash/. Cada --push
     4	segundos copia el tablero a la rama gh-pages (worktree en ../midterms-2026-pages) y pushea.
     5	GitHub Pages admite ~10 publicaciones por hora: no bajar --push de 480.
     6	
     7	Uso: uv run --with requests --with tqdm --with numpy --with scipy --with pandas model/live.py
     8	"""
     9	import argparse, os, shutil, subprocess, sys, time
    10	from pathlib import Path
    11	
    12	sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
    13	from claude_tqdm import tqdm  # noqa: E402
    14	
    15	sys.path.insert(0, str(Path(__file__).resolve().parent))
    16	import fetch_nyt as F  # noqa: E402
    17	import project as P  # noqa: E402
    18	
    19	ROOT = P.ROOT
    20	PAGES = ROOT.parent / "midterms-2026-pages"
    21	PUBLISH = ["index.html", "app.js", "style.css", "data.json", "units.json", "history.json", "lib", "geo"]
    22	
    23	
    24	def publish(stamp):
    25	    for name in PUBLISH:
    26	        src = ROOT / "dash" / name
    27	        if not src.exists():
    28	            continue
    29	        dst = PAGES / name
    30	        if src.is_dir():
    31	            shutil.copytree(src, dst, dirs_exist_ok=True)
    32	        else:
    33	            shutil.copy2(src, dst)
    34	    run = lambda *a: subprocess.run(["git", "-C", str(PAGES), *a], capture_output=True, text=True)
    35	    run("add", "-A")
    36	    if run("diff", "--cached", "--quiet").returncode == 0:
    37	        return "sin cambios"
    38	    run("commit", "-qm", f"Datos {stamp}")
    39	    r = run("push", "-q", "origin", "gh-pages")
    40	    return "publicado" if r.returncode == 0 else f"push falló: {r.stderr.strip()[:120]}"
    41	
    42	
    43	def main():
    44	    ap = argparse.ArgumentParser()
    45	    ap.add_argument("--date", default="2026-11-03")
    46	    ap.add_argument("--every", type=int, default=60)
    47	    ap.add_argument("--push", type=int, default=480)
    48	    ap.add_argument("--no-push", action="store_true")
    49	    a = ap.parse_args()
    50	    outdir = ROOT / "data" / "live" / a.date
    51	    bar = tqdm(total=1, desc="Noche electoral", unit="página", goal="bajar, proyectar y publicar en vivo")
    52	    bar.info(fuente="NYT / AP", ciclo=f"{a.every}s", publica="no" if a.no_push else f"cada {a.push}s")
    53	    last_push = 0.0
    54	    while True:
    55	        t0 = time.time()
    56	        try:
    57	            F.cycle(a.date, outdir, bar)
    58	            bar.status("proyectando")
    59	            sys.argv = ["project.py", "--date", a.date, "--out", str(ROOT / "dash")]
    60	            P.main()
    61	            stamp = time.strftime("%H:%M")
    62	            if not a.no_push and time.time() - last_push >= a.push:
    63	                bar.status("publicando")
    64	                bar.log(f"{stamp} {publish(stamp)}")
    65	                last_push = time.time()
    66	        except Exception as e:  # una caída de red o un JSON a medio escribir no corta la noche
    67	            bar.log(f"error: {type(e).__name__}: {str(e)[:120]}")
    68	        bar.status("esperando el próximo ciclo")
    69	        time.sleep(max(5, a.every - (time.time() - t0)))
    70	
    71	
    72	if __name__ == "__main__":
    73	    main()

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "OPENBLAS_NUM_THREADS=6 PYTHONDONTWRITEBYTECODE=1 /Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/bin/python -c 'import sys,numpy as np,pandas as pd
sys.path.append(\"/Users/juan/.cache/uv/archive-v0/bZpT0vvm7eKoJIB5/lib/python3.13/site-packages\"); sys.path.insert(0,\"model\"); import project as P; import rehearse as Q
d=P.load(\"2024-11-05\"); d=d[d.race_id==\"NE-G-S-2024-11-05\"].reset_index(drop=True)
n=len(d); state=(np.zeros(n),np.ones(n),np.zeros(n),np.ones(n)); z=Q.rebuild_state_rows(Q.synth(d,10,state,.04))
print(\"NE final true\",d[d.level==\"state\"][[\"D\",\"R\",\"O\"]].to_dict(\"records\")); print(\"NE synthetic final\",z[z.level==\"state\"][[\"D\",\"R\",\"O\"]].to_dict(\"records\")); print(\"NE truth metric\",max(d.iloc[0].D,d.iloc[0].O)/(max(d.iloc[0].D,d.iloc[0].O)+d.iloc[0].R))
m=P.Model(z).fit().simulate(); print(\"NE end simulation\",m.summary({})[\"races\"][0])
h=P.load(\"2026-11-03\"); h=h[h.race_id==\"IL-G-H-7-2026-11-03\"].copy(); s=h[h.level==\"state\"].expected.iloc[0]; Q.rebuild_state_rows(h); print(\"IL7 original expected\",s,\"rebuilt\",h[h.level==\"state\"].expected.iloc[0])
'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 313ms:
NE final true [{'D': 0, 'R': 499124, 'O': 436493}]
NE synthetic final [{'D': 4988.0, 'R': 494136.0, 'O': 436493.0}]
NE truth metric 0.46652957353275964
NE end simulation {'id': 'NE-G-S-2024-11-05', 'office': 'S', 'state': 'NE', 'seat': '1', 'rating': 'lean-rep', 'side': 'O', 'same_party': False, 'parties': 'OR', 'call': 'too_early', 'winner': '', 'eevp': 99.0, 'counted': 935617.0, 'expected': 935617.0, 'partial_B': 46.9, 'partial_R': 53.1, 'proj_B': 46.9, 'proj_R': 53.1, 'ci90_B': [46.9, 46.9], 'ci90_R': [53.1, 53.1], 'p_B_win': 0.0, 'runoff_risk': False}
IL7 original expected 207488.0 rebuilt 414976.0

hook: PostToolUse
hook: PostToolUse Completed
codex
Confirmé dos errores numéricos: cuando el lado elegido es `O`, el modelo resta sus votos dos veces del remanente tipificado; y las carreras entre demócratas salen con proyección D=0%, R=100%. Los umbrales actuales sí se leen correctamente del feed: Senado D=51/R=50 y Cámara=218. También encontré un doble conteo entre niveles en la función de reconstrucción del ensayo.
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "OPENBLAS_NUM_THREADS=6 PYTHONDONTWRITEBYTECODE=1 /Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/bin/python -c 'import sys,numpy as np,pandas as pd
sys.path.insert(0,\"model\"); import project as P
z=P.load(\"2026-11-03\"); z=z[(z.office==\"S\")&(z.level==\"state\")].iloc[[0]].copy(); z.loc[:,\"race_id\"]=\"test\"; z.loc[:,\"parties\"]=\"DR\"; z.loc[:,\"rating\"]=\"tossup\"; z.loc[:,\"b\"]=.5; z.loc[:,\"winner\"]=\"\"; z.loc[:,\"D\"]=250000; z.loc[:,\"R\"]=250000; z.loc[:,\"O\"]=0; z.loc[:,\"total\"]=500000; z.loc[:,\"expected\"]=1000000; z.loc[:,\"eevp\"]=50
co=pd.concat([z.assign(level=\"county\",unit_id=\"a\"),z.assign(level=\"county\",unit_id=\"b\")],ignore_index=True); top=z.assign(total=1000000,expected=2000000); m=P.Model(pd.concat([top,co],ignore_index=True)).fit(); i=0; race=m.races.iloc[0]; x=np.zeros(m.npar)
for j,v in m._design(i,-1,race):
 if j<m.o_bias:x[j]=v
vbin=1/(500000*.25)+P.SD[\"floor\"]**2; lam=m.sd_unit[0]**2/(vbin+m.sd_unit[0]**2)
print(\"unit posterior\",dict(shrinkage=lam,implemented_sd=float(np.sqrt(x@m.cov@x+m.e_sd[0]**2)),correct_conditional_sd=float(np.sqrt((1-lam)**2*(x@m.cov@x)+m.e_sd[0]**2))))
# Exact complete-model posterior with a shared unit intercept and 4 observed vote types vs implemented covariance
for t in P.TYPES:
 co.loc[:,f\"D_{t}\"]=62500; co.loc[:,f\"R_{t}\"]=62500
mm=P.Model(pd.concat([top,co],ignore_index=True)).fit(); n=mm.npar; A=np.zeros((n+2,n+2)); sd=np.zeros(n); sd[0]=P.SD[\"nat\"]; sd[mm.o_state:mm.o_race]=P.SD[\"state\"]; sd[mm.o_race:mm.o_type]=mm.races.sd_race.values; sd[mm.o_type:mm.o_bias]=P.SD[\"type\"]; sd[mm.o_bias:]=P.SD[\"bias\"]; A[:n,:n]=np.diag(1/sd**2)
for i in range(2):
 A[n+i,n+i]=1/mm.sd_unit[i]**2
 for ti in range(4):
  xx=np.zeros(n+2)
  for j,v in mm._design(i,ti,mm.races.iloc[0]):xx[j]=v
  xx[n+i]=1; A+=np.outer(xx,xx)/(1/(125000*.25)+P.SD[\"floor\"]**2)
true=np.linalg.inv(A); print(\"typed national posterior sd: implemented\",float(np.sqrt(mm.cov[0,0])),\"exact\",float(np.sqrt(true[0,0])))
'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 179ms:
unit posterior {'shrinkage': np.float64(0.9463722397476341), 'implemented_sd': 0.08313501539024183, 'correct_conditional_sd': 0.02012178557545384}
typed national posterior sd: implemented 0.07128862656563886 exact 0.07202369261278792

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "OPENBLAS_NUM_THREADS=6 PYTHONDONTWRITEBYTECODE=1 /Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/bin/python -c 'import sys,numpy as np,pandas as pd
sys.path.insert(0,\"model\"); import project as P
z=P.load(\"2026-11-03\"); z=z[(z.office==\"S\")&(z.level==\"state\")].iloc[[0]].copy().assign(race_id=\"test\",parties=\"DR\",rating=\"tossup\",b=.5,winner=\"\",D=250000,R=250000,O=0,total=500000,expected=1000000,eevp=50)
co=pd.concat([z.assign(level=\"county\",unit_id=\"a\"),z.assign(level=\"county\",unit_id=\"b\")],ignore_index=True); m=P.Model(pd.concat([z.assign(total=1000000,expected=2000000),co],ignore_index=True)).fit(); obs=np.zeros(m.npar)
for j,v in m._design(0,-1,m.races.iloc[0]):obs[j]=v
pred=obs.copy(); pred[m.o_bias:]=0
vbin=1/(500000*.25)+P.SD[\"floor\"]**2; lam=m.sd_unit[0]**2/(vbin+m.sd_unit[0]**2); adjusted=pred-lam*obs
print(\"implemented\",float(np.sqrt(pred@m.cov@pred+m.e_sd[0]**2)),\"correct\",float(np.sqrt(adjusted@m.cov@adjusted+m.e_sd[0]**2)))
'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 204ms:
implemented 0.08313501539024183 correct 0.07249957809039306

hook: PostToolUse
hook: PostToolUse Completed
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse
hook: PreToolUse Completed
hook: PreToolUse Completed
hook: PreToolUse Completed
exec
/bin/zsh -lc "OPENBLAS_NUM_THREADS=6 PYTHONDONTWRITEBYTECODE=1 /Users/juan/.cache/uv/archive-v0/U1fTPxkk7o3jmpSp/bin/python -c 'import sys,numpy as np
sys.path.insert(0,\"model\"); import project as P
z=P.load(\"2024-11-05\"); z=z[(z.office==\"S\")&(z.level==\"state\")]; m=P.Model(z); m.share=np.zeros((P.K,len(m.races))); m.win_B=np.tile((m.races.winner.str[0]"'!="R").values,(P.K,1)); print(m.summary(P.control_from_raw("2024-11-05"))["chambers"]["S"])
'"'" in /Users/juan/dev/midterms-2026-proyeccion
 succeeded in 244ms:
{'total': 100, 'D_needs': 51, 'R_needs': 51, 'p_D': 0.0, 'p_R': 1.0, 'D_med': 45, 'R_med': 53, 'I_med': 2, 'D_ci90': [45, 45], 'R_ci90': [53, 53], 'dist': {45: np.float64(1.0)}}

hook: PostToolUse
hook: PostToolUse Completed
codex
Found the following correctness bugs. References point to the current files; several scenarios were reproduced with in-memory inputs and the checked-in feeds.

1. **[P1] Candidate aggregation changes who can win.** [fetch_nyt.py:102](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:102), [project.py:158](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:158). All independents and minor candidates become one `O` candidate, and only the larger of aggregate D/O competes against R. Two independents receiving 26% each therefore beat a Republican receiving 48%. In an actual D-versus-independent race such as 2026 CA-06, the model instead invents a Republican opponent and ignores the other real candidate.

2. **[P1] Called winners can be credited to the wrong party.** [project.py:340](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:340), [project.py:373](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:373). A call sets only “non-R won”; chamber allocation still uses the side selected from current votes. If `side=D` when an independent is called, the independent’s seat becomes Democratic. The reverse misclassifies a called Democrat as independent.

3. **[P1] Independent caucuses are discarded in chamber control.** [fetch_nyt.py:77](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:77), [project.py:375](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:375). The feed supplies `party_caucus`, but flattening drops it and `p_D` excludes every independent win. The 2024 Senate fixture consequently produces D=45/I=2/R=53 versus the feed’s Democratic caucus total of 47. A 49-D-plus-two-D-caucusing-independent outcome incorrectly fails the 51-seat control test.

4. **[P1] Independent votes are subtracted twice from typed remaining votes.** [project.py:308](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:308). When `side=O`, `got_t` becomes `O_t + R_t + O_t`, omitting D. Reproduced: expected=1,000, O=300, R=200 gives only **200 remaining**, rather than 500. Independent races can prematurely run out of projected votes.

5. **[P1] Partial vote-type expectations discard the rest of the outstanding vote.** [project.py:309](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:309). Any positive typed expectation completely replaces the aggregate remainder. With aggregate expected=1,000/counted=500 and only an advance category expected=counted=200, the model projects **zero remaining**, although 500 votes remain. Conversely, inconsistent typed totals can project more than the aggregate remainder.

6. **[P1] Stale state pages override fresh overview results indefinitely.** [fetch_nyt.py:87](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:87), [fetch_nyt.py:98](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:98). State pages always win deduplication, without a freshness comparison. If a state-page request fails while the overview receives new totals or a call, the old local page suppresses those updates. The projection can silently remain uncalled and behind the count.

7. **[P1] Unit selection silently drops uncovered geography.** [project.py:127](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:127). A sublevel covering just over 90% of expected votes replaces the complete state row without retaining a residual. Reproduced: selected counties contain 450 counted/950 expected versus the state’s 500/1,000; all projections omit the missing geography, while the displayed race totals still come from the state. This also drops smaller residual units in the current feed, such as Maine House “other” units.

8. **[P1] Majority/runoff and ranked tabulations are treated as ordinary two-side wins.** [project.py:334](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:334), [project.py:366](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:366). `tabulation` is loaded but unused; `runoff_risk` is only a label. A 48-D/47-R/5-other result becomes a Democratic win because D/(D+R)>50%, even where that result requires a runoff. Chamber simulations immediately award the seat.

9. **[P2] Same-party Democratic races report a 100% Republican vote projection.** [project.py:297](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:297), [project.py:334](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:334). Simulation skips these races, leaving both vote arrays zero; normalization produces `share=0`. Reproduced for `parties=DD`: `proj_B=0`, `proj_R=100`, but `p_B_win=1`. Current California D/D contests trigger this.

10. **[P2] Typed observations incorrectly treat the shared unit effect as independent noise.** [project.py:248](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:248). Each vote-type cell receives a separate `sd_unit²` variance, although all cells in that unit share the same `e[u]`. Their covariance is missing. Four large typed batches from one county can contribute roughly four times the information warranted by the shared county deviation, distorting posterior learning and confidence intervals.

11. **[P2] Simulated unit effects lose their posterior dependence on model coefficients.** [project.py:264](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:264), [project.py:303](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:303). `e_hat` is computed using mean coefficients and then sampled independently of coefficient draws. Its conditional mean should change with each draw. The resulting remaining-vote draws do not follow the fitted posterior; a two-county reproduction gave a projected-logit SD of 0.083 versus 0.072 with the conditional dependence retained, before additional shocks.

12. **[P2] The rehearsal changes the final result it claims to reproduce.** [rehearse.py:41](/Users/juan/dev/midterms-2026-proyeccion/model/rehearse.py:41). Even at `f=1`, clipping D’s share to `[.01,.99]` transfers votes between D and R. Reproduced for Nebraska Senate 2024: the true D=0/R=499,124 becomes synthetic D=4,988/R=494,136, while O remains 436,493. Final projected independent share is 46.90% against the rehearsal truth of 46.65%, contaminating error and coverage metrics.

13. **[P2, latent] Rebuilding state rows double-counts overlapping reporting levels.** [rehearse.py:58](/Users/juan/dev/midterms-2026-proyeccion/model/rehearse.py:58). It sums every non-state/non-national row, unlike `pick_units`. Applied to current IL-07, county plus city/other rows turn expected votes from **207,488 into 414,976**. The current S/G-only 2024 rehearsal avoids this input, but the helper is incorrect for mixed-level feeds.

The checked-in 2026 feed’s holdovers and thresholds are read correctly: Senate D holdovers=34, Republican threshold=50, Democratic threshold=51; House threshold=218. The chamber errors above arise from winner/caucus classification, rather than those constants.
hook: Stop
hook: Stop
hook: Stop Completed
hook: Stop Completed
tokens used
69.235
Found the following correctness bugs. References point to the current files; several scenarios were reproduced with in-memory inputs and the checked-in feeds.

1. **[P1] Candidate aggregation changes who can win.** [fetch_nyt.py:102](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:102), [project.py:158](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:158). All independents and minor candidates become one `O` candidate, and only the larger of aggregate D/O competes against R. Two independents receiving 26% each therefore beat a Republican receiving 48%. In an actual D-versus-independent race such as 2026 CA-06, the model instead invents a Republican opponent and ignores the other real candidate.

2. **[P1] Called winners can be credited to the wrong party.** [project.py:340](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:340), [project.py:373](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:373). A call sets only “non-R won”; chamber allocation still uses the side selected from current votes. If `side=D` when an independent is called, the independent’s seat becomes Democratic. The reverse misclassifies a called Democrat as independent.

3. **[P1] Independent caucuses are discarded in chamber control.** [fetch_nyt.py:77](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:77), [project.py:375](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:375). The feed supplies `party_caucus`, but flattening drops it and `p_D` excludes every independent win. The 2024 Senate fixture consequently produces D=45/I=2/R=53 versus the feed’s Democratic caucus total of 47. A 49-D-plus-two-D-caucusing-independent outcome incorrectly fails the 51-seat control test.

4. **[P1] Independent votes are subtracted twice from typed remaining votes.** [project.py:308](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:308). When `side=O`, `got_t` becomes `O_t + R_t + O_t`, omitting D. Reproduced: expected=1,000, O=300, R=200 gives only **200 remaining**, rather than 500. Independent races can prematurely run out of projected votes.

5. **[P1] Partial vote-type expectations discard the rest of the outstanding vote.** [project.py:309](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:309). Any positive typed expectation completely replaces the aggregate remainder. With aggregate expected=1,000/counted=500 and only an advance category expected=counted=200, the model projects **zero remaining**, although 500 votes remain. Conversely, inconsistent typed totals can project more than the aggregate remainder.

6. **[P1] Stale state pages override fresh overview results indefinitely.** [fetch_nyt.py:87](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:87), [fetch_nyt.py:98](/Users/juan/dev/midterms-2026-proyeccion/model/fetch_nyt.py:98). State pages always win deduplication, without a freshness comparison. If a state-page request fails while the overview receives new totals or a call, the old local page suppresses those updates. The projection can silently remain uncalled and behind the count.

7. **[P1] Unit selection silently drops uncovered geography.** [project.py:127](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:127). A sublevel covering just over 90% of expected votes replaces the complete state row without retaining a residual. Reproduced: selected counties contain 450 counted/950 expected versus the state’s 500/1,000; all projections omit the missing geography, while the displayed race totals still come from the state. This also drops smaller residual units in the current feed, such as Maine House “other” units.

8. **[P1] Majority/runoff and ranked tabulations are treated as ordinary two-side wins.** [project.py:334](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:334), [project.py:366](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:366). `tabulation` is loaded but unused; `runoff_risk` is only a label. A 48-D/47-R/5-other result becomes a Democratic win because D/(D+R)>50%, even where that result requires a runoff. Chamber simulations immediately award the seat.

9. **[P2] Same-party Democratic races report a 100% Republican vote projection.** [project.py:297](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:297), [project.py:334](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:334). Simulation skips these races, leaving both vote arrays zero; normalization produces `share=0`. Reproduced for `parties=DD`: `proj_B=0`, `proj_R=100`, but `p_B_win=1`. Current California D/D contests trigger this.

10. **[P2] Typed observations incorrectly treat the shared unit effect as independent noise.** [project.py:248](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:248). Each vote-type cell receives a separate `sd_unit²` variance, although all cells in that unit share the same `e[u]`. Their covariance is missing. Four large typed batches from one county can contribute roughly four times the information warranted by the shared county deviation, distorting posterior learning and confidence intervals.

11. **[P2] Simulated unit effects lose their posterior dependence on model coefficients.** [project.py:264](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:264), [project.py:303](/Users/juan/dev/midterms-2026-proyeccion/model/project.py:303). `e_hat` is computed using mean coefficients and then sampled independently of coefficient draws. Its conditional mean should change with each draw. The resulting remaining-vote draws do not follow the fitted posterior; a two-county reproduction gave a projected-logit SD of 0.083 versus 0.072 with the conditional dependence retained, before additional shocks.

12. **[P2] The rehearsal changes the final result it claims to reproduce.** [rehearse.py:41](/Users/juan/dev/midterms-2026-proyeccion/model/rehearse.py:41). Even at `f=1`, clipping D’s share to `[.01,.99]` transfers votes between D and R. Reproduced for Nebraska Senate 2024: the true D=0/R=499,124 becomes synthetic D=4,988/R=494,136, while O remains 436,493. Final projected independent share is 46.90% against the rehearsal truth of 46.65%, contaminating error and coverage metrics.

13. **[P2, latent] Rebuilding state rows double-counts overlapping reporting levels.** [rehearse.py:58](/Users/juan/dev/midterms-2026-proyeccion/model/rehearse.py:58). It sums every non-state/non-national row, unlike `pick_units`. Applied to current IL-07, county plus city/other rows turn expected votes from **207,488 into 414,976**. The current S/G-only 2024 rehearsal avoids this input, but the helper is incorrect for mixed-level feeds.

The checked-in 2026 feed’s holdovers and thresholds are read correctly: Senate D holdovers=34, Republican threshold=50, Democratic threshold=51; House threshold=218. The chamber errors above arise from winner/caucus classification, rather than those constants.
