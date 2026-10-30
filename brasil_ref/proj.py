"""Live projection of Brazil 2026 presidential runoff from TSE partial results.

Model: Goodman ecological regression (NNLS) of round-2 votes per elector on round-1
composition per elector, fitted on counted municipalities, plus shrunken state effects.
Uncounted electorate in each municipality is filled with the prediction (blended with
the municipality's own observed rate in proportion to how much of it is counted).
"""
import json, os, sys, time, concurrent.futures as cf
import numpy as np, requests
from scipy.optimize import nnls
sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
HERE = os.path.dirname(os.path.abspath(__file__))
S = requests.Session()
S.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=64))


def get(url):
    for i in range(4):
        try:
            r = S.get(url, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(0.5 * (i + 1))
    return None


def munis():
    cfg = json.load(open(os.path.join(HERE, "mun.json")))
    return [(a["cd"], m["cd"]) for a in cfg["abr"] for m in a["mu"]]


def parse(d):
    cands = {k["nmu"]: int(k["vap"]) for a in d["carg"][0]["agr"] for p in a["par"] for k in p["cand"]}
    return dict(te=int(d["e"]["te"]), est=int(d["e"]["est"]), ts=int(d["s"]["ts"]), st=int(d["s"]["st"]),
                tv=int(d["v"]["tv"]), cands=cands)


def fetch(ele, desc):
    ms = munis()
    out = {}
    urls = {(uf, cd): f"{BASE}/{ele}/dados/{uf}/{uf}{cd}-c0001-e00{ele}-u.json" for uf, cd in ms}
    bar = tqdm(total=len(urls), desc=desc, unit="mun")
    with cf.ThreadPoolExecutor(48) as ex:
        futs = {ex.submit(get, u): k for k, u in urls.items()}
        for f in cf.as_completed(futs):
            d = f.result()
            if d:
                out[futs[f]] = parse(d)
            bar.update(1)
    bar.close()
    return out


def load_r1():
    p = os.path.join(HERE, "r1.json")
    if os.path.exists(p):
        return {tuple(k.split("|")): v for k, v in json.load(open(p)).items()}
    r1 = fetch("6257", "1º turno (una vez)")
    json.dump({"|".join(k): v for k, v in r1.items()}, open(p, "w"))
    return r1


def main():
    r1 = load_r1()
    r2 = fetch("6258", "2º turno en vivo")
    keys = [k for k in r1 if k in r2]
    n = len(keys)
    uf = np.array([k[0] for k in keys])
    E = np.array([r1[k]["te"] for k in keys], float)
    F1 = np.array([r1[k]["cands"].get("FLAVIO BOLSONARO", 0) for k in keys], float)
    L1 = np.array([r1[k]["cands"].get("LULA", 0) for k in keys], float)
    V1 = np.array([sum(r1[k]["cands"].values()) for k in keys], float)
    T1 = np.array([r1[k]["tv"] for k in keys], float)
    O1 = V1 - F1 - L1
    X = np.c_[F1, L1, O1, E - V1] / E[:, None]  # rates per elector: F, L, other valid, abst+blank+null

    E2 = np.array([r2[k]["te"] for k in keys], float)
    est = np.array([r2[k]["est"] for k in keys], float)
    F2 = np.array([r2[k]["cands"].get("FLAVIO BOLSONARO", 0) for k in keys], float)
    L2 = np.array([r2[k]["cands"].get("LULA", 0) for k in keys], float)
    c = np.where(E2 > 0, est / E2, 0)
    rem = E2 - est
    ok = est > 0
    yF = np.where(ok, F2 / np.maximum(est, 1), 0)
    yL = np.where(ok, L2 / np.maximum(est, 1), 0)

    def fit(idx):
        w = np.sqrt(est[idx])
        bF, _ = nnls(X[idx] * w[:, None], yF[idx] * w)
        bL, _ = nnls(X[idx] * w[:, None], yL[idx] * w)
        pF, pL = X @ bF, X @ bL
        # shrunken state effects (prior weight W0 electors counted)
        W0 = 2e5
        sF, sL = np.zeros(n), np.zeros(n)
        for s in np.unique(uf):
            m = (uf == s)
            mi = np.intersect1d(np.where(m)[0], idx)
            W = est[mi].sum()
            if W > 0:
                k = W / (W + W0)
                sF[m] = k * np.average(yF[mi] - pF[mi], weights=est[mi])
                sL[m] = k * np.average(yL[mi] - pL[mi], weights=est[mi])
        return bF, bL, pF + sF, pL + sL

    def project(pF, pL, shockF=0, shockL=0):
        w = c / (c + 0.25)  # trust own observed rate as counting advances
        rF = np.where(ok, w * yF + (1 - w) * pF, pF) + shockF
        rL = np.where(ok, w * yL + (1 - w) * pL, pL) + shockL
        return F2.sum() + (rem * np.clip(rF, 0, 1)).sum(), L2.sum() + (rem * np.clip(rL, 0, 1)).sum()

    idx = np.where(c >= 0.03)[0]
    bF, bL, pF, pL = fit(idx)
    F, L = project(pF, pL)

    # uncertainty: bootstrap municipalities + state-level shocks sized by state residual dispersion
    rng = np.random.default_rng(0)
    states = np.unique(uf)
    resid = (yF - yL) - (pF - pL)
    sig = np.sqrt(np.average(resid[idx] ** 2, weights=est[idx])) if len(idx) else 0.05
    sims = []
    for b in tqdm(range(300), desc="bootstrap", unit="sim"):
        bi = rng.choice(idx, len(idx), replace=True)
        _, _, qF, qL = fit(bi)
        # state shock: larger where little is counted
        cs = {s: est[uf == s].sum() / max(E2[uf == s].sum(), 1) for s in states}
        sh = {s: rng.normal(0, 0.5 * sig * (1 - cs[s])) for s in states}
        shv = np.array([sh[s] for s in uf])
        f, l = project(qF, qL, shv / 2, -shv / 2)
        sims.append(f / (f + l))
    sims = np.array(sims)

    tot_c = est.sum() / E2.sum()
    print(time.strftime("%H:%M:%S"), f"| electorado contado {tot_c*100:.1f}% | munis con datos {ok.sum()}/{n}")
    print(f"Parcial TSE:  Flávio {F2.sum()/(F2.sum()+L2.sum())*100:.2f}%  Lula {L2.sum()/(F2.sum()+L2.sum())*100:.2f}%")
    p = F / (F + L)
    print(f"PROYECCIÓN:   Flávio {p*100:.2f}%  Lula {(1-p)*100:.2f}%   (Flávio {F/1e6:.2f}M vs Lula {L/1e6:.2f}M)")
    lo, hi = np.percentile(sims, [5, 95])
    print(f"IC 90% Flávio: {lo*100:.2f}–{hi*100:.2f}%   P(Flávio gana)={np.mean(sims>0.5)*100:.0f}%")
    lab = ["Flávio1", "Lula1", "Otros1", "NoVoto1"]
    print("Transferencias (votos 2º turno por voto 1º):")
    print("  a Flávio:", dict(zip(lab, np.round(bF, 3))))
    print("  a Lula:  ", dict(zip(lab, np.round(bL, 3))))
    print("Por estado (contado% | parcial Flávio% | proyectado Flávio%):")
    for s in states:
        m = uf == s
        fc, lc = F2[m].sum(), L2[m].sum()
        fp = fc + (rem[m] * np.clip(np.where(ok[m], (c[m]/(c[m]+.25))*yF[m]+(1-c[m]/(c[m]+.25))*pF[m], pF[m]), 0, 1)).sum()
        lp = lc + (rem[m] * np.clip(np.where(ok[m], (c[m]/(c[m]+.25))*yL[m]+(1-c[m]/(c[m]+.25))*pL[m], pL[m]), 0, 1)).sum()
        print(f"  {s.upper()} {est[m].sum()/E2[m].sum()*100:5.1f}% | {fc/max(fc+lc,1)*100:5.1f} | {fp/(fp+lp)*100:5.1f}")
    json.dump(dict(t=time.time(), counted=tot_c, proj=p, lo=lo, hi=hi), open(os.path.join(HERE, "last.json"), "w"))


if __name__ == "__main__":
    main()
