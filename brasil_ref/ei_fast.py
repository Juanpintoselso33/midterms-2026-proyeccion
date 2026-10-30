"""Constrained ecological regression (rows of the transition matrix in the simplex),
by region, with municipality bootstrap for 90% intervals."""
import json, os, sys
import numpy as np
from scipy.optimize import minimize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ei import build, ROWS, COLS, REGION


def fit(X, Y, N):
    r, c = X.shape[1], Y.shape[1]
    w = N / N.sum()

    def loss(b):
        B = b.reshape(r, c)
        return (w[:, None] * (X @ B - Y) ** 2).sum()

    cons = [{"type": "eq", "fun": (lambda b, i=i: b.reshape(r, c)[i].sum() - 1)} for i in range(r)]
    b0 = np.full(r * c, 1 / c)
    res = minimize(loss, b0, method="SLSQP", bounds=[(0, 1)] * (r * c), constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-12})
    return res.x.reshape(r, c)


def main():
    X, Y, N, uf = build()
    reg = np.array([REGION[u] for u in uf])
    rng = np.random.default_rng(0)
    out = {}
    for g in ["Brasil", "Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]:
        m = np.ones(len(N), bool) if g == "Brasil" else reg == g
        Xg, Yg, Ng = X[m], Y[m], N[m]
        B = fit(Xg, Yg, Ng)
        boots = []
        for _ in range(150):
            i = rng.choice(len(Ng), len(Ng), replace=True)
            boots.append(fit(Xg[i], Yg[i], Ng[i]))
        boots = np.array(boots)
        pred = (Xg * Ng[:, None]).sum(0) @ B / Ng.sum()
        obs = (Yg * Ng[:, None]).sum(0) / Ng.sum()
        out[g] = dict(mean=B.tolist(), lo=np.percentile(boots, 5, 0).tolist(), hi=np.percentile(boots, 95, 0).tolist(),
                      pred=pred.tolist(), obs=obs.tolist(), n=int(m.sum()))
        print(f"\n== {g} ({m.sum()} munis)  check 2º turno pred vs obs: " +
              " ".join(f"{c} {p*100:.1f}/{o*100:.1f}" for c, p, o in zip(COLS, pred, obs)))
        print(f"{'1º turno →':14s}" + "".join(f"{c:>20s}" for c in COLS))
        for i, rname in enumerate(ROWS):
            print(f"{rname:14s}" + "".join(f"{B[i,j]*100:7.1f} [{out[g]['lo'][i][j]*100:4.0f}-{out[g]['hi'][i][j]*100:3.0f}]" for j in range(len(COLS))))
    json.dump(dict(rows=ROWS, cols=COLS, regions=out), open(os.path.join(HERE, "ei_fast.json"), "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
