"""Improved hierarchical RxC ecological inference, variational, on the Metal GPU (PyTorch MPS).

logits_irc = eta_rc + u_{state(i),r,c} + sigma_r * eps_irc
  eta ~ N(mu0, 1.5^2)   mu0 = +L on loyalty cells (F->F, L->L, BN->BN, Abst->Abst) if --loyal, else 0
  u_s ~ N(0, tau_r^2),  tau_r, sigma_r ~ HalfNormal(1)
  y_i ~ Multinomial(N_i, sum_r x_ir softmax(logits_ir))
Fitted per region with K random restarts (best final ELBO kept); stability = spread of the top restarts.
5-fold cross-validation by unit: predict held-out runoff shares from first-round composition.

Usage: python vi_ei2.py <units.npz> <out.json>
  units.npz: X (n x 8 first-round shares of electorate), Y (n x 4 runoff shares), N (electorate), uf (state codes)
"""
import json, os, sys, time
import numpy as np
import torch

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm

ROWS = ["Flávio", "Lula", "Caiado", "Cury", "Renan", "Otros", "Blanco/Nulo", "Abstención"]
COLS = ["Flávio", "Lula", "Blanco/Nulo", "Abstención"]
LOYAL = [(0, 0), (1, 1), (6, 2), (7, 3)]
REGION = {**{u: "Norte" for u in "ac am ap pa ro rr to".split()},
          **{u: "Nordeste" for u in "al ba ce ma pb pe pi rn se".split()},
          **{u: "Centro-Oeste" for u in "df go ms mt".split()},
          **{u: "Sudeste" for u in "es mg rj sp".split()},
          **{u: "Sul" for u in "pr rs sc".split()}}
DEV = torch.device("mps")
STEPS, K, LR = 3000, 8, 0.03
normal = torch.distributions.Normal


def fit(X, Y, N, st, loyal, seed):
    """Returns (final -ELBO per vote, q params) for one restart."""
    torch.manual_seed(seed)
    n, r = X.shape; c = Y.shape[1]; S = int(st.max()) + 1
    x = torch.tensor(X, dtype=torch.float32, device=DEV)
    y = torch.tensor(Y * N[:, None], dtype=torch.float32, device=DEV)
    s_idx = torch.tensor(st, dtype=torch.long, device=DEV)
    mu0 = torch.zeros(r, c, device=DEV)
    if loyal:
        for a, b in LOYAL:
            mu0[a, b] = 3.0
    P = lambda *sh, v=0.0, sd=0.0: (torch.full(sh, v, device=DEV) + sd * torch.randn(*sh, device=DEV)).requires_grad_()
    q = dict(eta_m=P(r, c, sd=1.0), eta_s=P(r, c, v=-2.0),
             u_m=P(S, r, c), u_s=P(S, r, c, v=-2.0), lt_m=P(r, v=-1.0), lt_s=P(r, v=-2.0),
             ls_m=P(r, v=-1.0), ls_s=P(r, v=-2.0), eps_m=P(n, r, c), eps_s=P(n, r, c, v=-2.0))
    opt = torch.optim.Adam(q.values(), lr=LR)
    tot = y.sum()

    def elbo(samples=1):
        val = 0
        for _ in range(samples):
            eta = q["eta_m"] + q["eta_s"].exp() * torch.randn_like(q["eta_m"])
            u = q["u_m"] + q["u_s"].exp() * torch.randn_like(q["u_m"])
            lt = q["lt_m"] + q["lt_s"].exp() * torch.randn_like(q["lt_m"])
            ls = q["ls_m"] + q["ls_s"].exp() * torch.randn_like(q["ls_m"])
            eps = q["eps_m"] + q["eps_s"].exp() * torch.randn_like(q["eps_m"])
            beta = torch.softmax(eta + u[s_idx] + ls.exp()[None, :, None] * eps, -1)
            p = (x[:, :, None] * beta).sum(1).clamp_min(1e-9)
            val = val + (y * p.log()).sum() + normal(mu0, 1.5).log_prob(eta).sum() \
                + normal(0, lt.exp()[None, :, None]).log_prob(u).sum() \
                + normal(0, 1.0).log_prob(lt.exp()).sum() + lt.sum() + normal(0, 1.0).log_prob(ls.exp()).sum() + ls.sum() \
                + normal(0, 1.0).log_prob(eps).sum()
        ent = sum(q[k].sum() for k in q if k.endswith("_s"))
        return (val / samples + ent) / tot

    for _ in range(STEPS):
        opt.zero_grad(); loss = -elbo(); loss.backward(); opt.step()
    with torch.no_grad():
        final = float(-elbo(16))
    return final, {k: v.detach() for k, v in q.items()}


def transfer(q, X, N, st, draws=300):
    """Aggregate transfer matrix draws for the fitted units."""
    x = torch.tensor(X, dtype=torch.float32, device=DEV)
    w = torch.tensor(N, dtype=torch.float32, device=DEV)[:, None] * x
    s_idx = torch.tensor(st, dtype=torch.long, device=DEV)
    out = []
    with torch.no_grad():
        for _ in range(draws):
            eta = q["eta_m"] + q["eta_s"].exp() * torch.randn_like(q["eta_m"])
            u = q["u_m"] + q["u_s"].exp() * torch.randn_like(q["u_m"])
            ls = q["ls_m"] + q["ls_s"].exp() * torch.randn_like(q["ls_m"])
            eps = q["eps_m"] + q["eps_s"].exp() * torch.randn_like(q["eps_m"])
            beta = torch.softmax(eta + u[s_idx] + ls.exp()[None, :, None] * eps, -1)
            out.append(((w[:, :, None] * beta).sum(0) / w.sum(0)[:, None].clamp_min(1e-9)).cpu().numpy())
    return np.array(out)


def predict(q, X, st, draws=100):
    """Predicted runoff shares for NEW units (eps drawn from the prior)."""
    x = torch.tensor(X, dtype=torch.float32, device=DEV)
    s_idx = torch.tensor(st, dtype=torch.long, device=DEV)
    acc = 0
    with torch.no_grad():
        for _ in range(draws):
            ls = q["ls_m"] + q["ls_s"].exp() * torch.randn_like(q["ls_m"])
            eps = torch.randn(len(X), *q["eta_m"].shape, device=DEV)
            beta = torch.softmax(q["eta_m"] + q["u_m"][s_idx] + ls.exp()[None, :, None] * eps, -1)
            acc = acc + (x[:, :, None] * beta).sum(1)
    return (acc / draws).cpu().numpy()


def best_of(X, Y, N, st, loyal, k=K, seed0=0):
    runs = [fit(X, Y, N, st, loyal, seed0 + i) for i in range(k)]
    runs.sort(key=lambda t: t[0])
    return runs


def regression_predict(Xtr, Ytr, Ntr, Xte):
    from scipy.optimize import minimize
    r, c = Xtr.shape[1], Ytr.shape[1]
    w = Ntr / Ntr.sum(); A = Xtr.T @ (w[:, None] * Xtr); C = Xtr.T @ (w[:, None] * Ytr)
    cons = [{"type": "eq", "fun": (lambda b, i=i: b.reshape(r, c)[i].sum() - 1)} for i in range(r)]
    res = minimize(lambda b: np.sum(b.reshape(r, c) * (A @ b.reshape(r, c))) - 2 * np.sum(b.reshape(r, c) * C),
                   np.full(r * c, 1 / c), jac=lambda b: (2 * (A @ b.reshape(r, c)) - 2 * C).ravel(),
                   method="SLSQP", bounds=[(0, 1)] * (r * c), constraints=cons, options={"maxiter": 1000})
    return Xte @ res.x.reshape(r, c)


def wrmse(P, Y, N):
    return float(np.sqrt(np.average(((P - Y) ** 2).sum(1), weights=N)))


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = np.load(src, allow_pickle=True)
    X, Y, N, uf = d["X"], d["Y"], d["N"].astype(float), d["uf"]
    reg = np.array([REGION[u] for u in uf])
    regions = ["Norte", "Centro-Oeste", "Sul", "Sudeste", "Nordeste"]
    jobs = [(g, v) for g in regions for v in ("fiel", "neutro")]
    res = json.load(open(dst)) if os.path.exists(dst) else {}
    bar = tqdm(jobs, desc="EI mejorado (GPU)", unit="ajuste",
               goal=f"{os.path.basename(src)}: región × previo, {K} arranques + validación cruzada")
    bar.info(dispositivo="Apple M5 Pro GPU (MPS)", unidades=int(len(N)), pasos=STEPS, arranques=K)
    rng = np.random.default_rng(0)
    for g, v in bar:
        key = f"{g}|{v}"
        if key in res:
            bar.log(f"{key}: ya estaba"); continue
        m = np.where(reg == g)[0]
        st = np.unique(uf[m], return_inverse=True)[1]
        Xg, Yg, Ng = X[m], Y[m], N[m]
        t = time.time()
        bar.status(f"{g} · previo {v} · {K} arranques sobre {len(m)} unidades")
        runs = best_of(Xg, Yg, Ng, st, v == "fiel")
        draws = transfer(runs[0][1], Xg, Ng, st)
        top = [transfer(q, Xg, Ng, st, draws=50).mean(0) for _, q in runs[:3]]
        spread = float(max(np.abs(top[0] - t2).max() for t2 in top[1:]))
        # 5-fold CV (single restart per fold to keep it cheap; best-of-2)
        bar.status(f"{g} · previo {v} · validación cruzada")
        folds = rng.permutation(len(m)) % 5
        cv_model, cv_reg = [], []
        for f in range(5):
            tr, te = folds != f, folds == f
            q = best_of(Xg[tr], Yg[tr], Ng[tr], st[tr], v == "fiel", k=2, seed0=100 + f)[0][1]
            cv_model.append(wrmse(predict(q, Xg[te], st[te]), Yg[te], Ng[te]))
            cv_reg.append(wrmse(regression_predict(Xg[tr], Yg[tr], Ng[tr], Xg[te]), Yg[te], Ng[te]))
        B = draws.mean(0)
        res[key] = dict(mean=B.tolist(), lo=np.percentile(draws, 5, 0).tolist(), hi=np.percentile(draws, 95, 0).tolist(),
                        elbos=[r_[0] for r_ in runs], top3_spread=spread,
                        cv_rmse_model=float(np.mean(cv_model)), cv_rmse_regression=float(np.mean(cv_reg)),
                        n=int(len(m)), seconds=time.time() - t)
        json.dump(res, open(dst, "w"), ensure_ascii=False)
        bar.log(f"{g} {v}: CV modelo {np.mean(cv_model)*100:.2f} vs regresión {np.mean(cv_reg)*100:.2f} pp · estabilidad {spread*100:.1f} pp")


if __name__ == "__main__":
    main()
