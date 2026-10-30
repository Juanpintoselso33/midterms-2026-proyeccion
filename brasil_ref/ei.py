"""Ecological inference (RxC, multinomial-Dirichlet; Rosen et al. 2001 via PyEI) of
vote transitions from the 2026 first round to the runoff, at municipality level.

Usage: python ei.py pilot   -> timing run on a random sample
       python ei.py         -> national-by-region fits, saved per region
"""
import json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm
import proj

ROWS = ["Flávio", "Lula", "Caiado", "Cury", "Renan", "Otros", "Blanco/Nulo", "Abstención"]
COLS = ["Flávio", "Lula", "Blanco/Nulo", "Abstención"]
REGION = {**{u: "Norte" for u in "ac am ap pa ro rr to".split()},
          **{u: "Nordeste" for u in "al ba ce ma pb pe pi rn se".split()},
          **{u: "Centro-Oeste" for u in "df go ms mt".split()},
          **{u: "Sudeste" for u in "es mg rj sp".split()},
          **{u: "Sul" for u in "pr rs sc".split()}}
OUT = os.path.join(HERE, "ei_results")
os.makedirs(OUT, exist_ok=True)


def load_r2():
    p = os.path.join(HERE, "r2_final.json")
    if os.path.exists(p):
        return {tuple(k.split("|")): v for k, v in json.load(open(p)).items()}
    r2 = proj.fetch("6258", "2º turno final")
    json.dump({"|".join(k): v for k, v in r2.items()}, open(p, "w"))
    return r2


def build():
    r1, r2 = proj.load_r1(), load_r2()
    keys = [k for k in r1 if k in r2 and k[0] != "zz" and r2[k]["est"] == r2[k]["te"] and r2[k]["te"] > 0]
    X, Y, N, uf = [], [], [], []
    for k in keys:
        a, b = r1[k], r2[k]
        c = a["cands"]
        F, L = c.get("FLAVIO BOLSONARO", 0), c.get("LULA", 0)
        Ca, Cu, Re = c.get("RONALDO CAIADO", 0), c.get("ESCRITOR AUGUSTO CURY", 0), c.get("RENAN SANTOS", 0)
        valid = sum(c.values())
        row = [F, L, Ca, Cu, Re, valid - F - L - Ca - Cu - Re, a["tv"] - valid, a["te"] - a["tv"]]
        F2, L2 = b["cands"].get("FLAVIO BOLSONARO", 0), b["cands"].get("LULA", 0)
        col = [F2, L2, b["tv"] - F2 - L2, b["te"] - b["tv"]]
        X.append(np.array(row, float) / a["te"]); Y.append(np.array(col, float) / b["te"])
        N.append(b["te"]); uf.append(k[0])
    return np.array(X), np.array(Y), np.array(N), np.array(uf)


def fit(X, Y, N, draws, tune, chains=4):
    from pyei.r_by_c import RowByColumnEI
    ei = RowByColumnEI(model_name="multinomial-dirichlet-modified", pareto_scale=8, pareto_shape=2)
    X = np.clip(X, 1e-6, None); X = X / X.sum(1, keepdims=True)
    Y = np.clip(Y, 1e-6, None); Y = Y / Y.sum(1, keepdims=True)
    ei.fit(X.T, Y.T, N.astype(int), ROWS, COLS, draws=draws, tune=tune, chains=chains,
           cores=chains, nuts_sampler="nutpie", progressbar=False)
    s = np.asarray(ei.sampled_voting_prefs)  # (samples, r, c)
    import arviz as az
    summ = az.summary(ei.sim_trace, var_names=["kappa"] if "kappa" in ei.sim_trace.posterior else None)
    return dict(mean=s.mean(0).tolist(), lo=np.percentile(s, 5, 0).tolist(), hi=np.percentile(s, 95, 0).tolist(),
                rhat_max=float(summ["r_hat"].max()), ess_min=float(summ["ess_bulk"].min()),
                n_units=int(len(N)), electorate=int(N.sum()),
                check_pred=(X * N[:, None]).sum(0) @ s.mean(0) / N.sum(), check_obs=(Y * N[:, None]).sum(0) / N.sum())


def main():
    pilot = len(sys.argv) > 1 and sys.argv[1] == "pilot"
    X, Y, N, uf = build()
    print(f"municipios completos: {len(N)}  electorado {N.sum():,}")
    if pilot:
        rng = np.random.default_rng(1); i = rng.choice(len(N), 400, replace=False)
        t = time.time(); r = fit(X[i], Y[i], N[i], draws=200, tune=200, chains=2)
        print(f"PILOTO 400 munis, 400 iter x 2 cadenas: {time.time()-t:.0f}s  rhat_max {r['rhat_max']:.2f}")
        return
    reg = np.array([REGION[u] for u in uf])
    jobs = ["Norte", "Centro-Oeste", "Sul", "Sudeste", "Nordeste"]
    bar = tqdm(jobs, desc="Inferencia ecológica RxC", unit="región",
               goal="transferencias 1º→2º turno por región (8×4)")
    bar.info(modelo="multinomial-Dirichlet (Rosen)", sampler="nutpie CPU", cadenas=4, muestras=1000)
    for g in bar:
        p = os.path.join(OUT, f"{g}.json")
        if os.path.exists(p):
            bar.log(f"{g}: ya estaba"); continue
        m = reg == g
        bar.status(f"{g}: {m.sum()} municipios, {N[m].sum()/1e6:.1f}M electores")
        t = time.time()
        r = fit(X[m], Y[m], N[m], draws=1000, tune=1000)
        r["seconds"] = time.time() - t
        r["check_pred"] = list(map(float, r["check_pred"])); r["check_obs"] = list(map(float, r["check_obs"]))
        json.dump(r, open(p, "w"), ensure_ascii=False)
        mean = np.array(r["mean"])
        bar.log(f"{g}: R-hat {r['rhat_max']:.2f} · otros→Lula {mean[5,1]*100:.0f}% · Caiado→Flávio {mean[2,0]*100:.0f}%")


if __name__ == "__main__":
    main()
