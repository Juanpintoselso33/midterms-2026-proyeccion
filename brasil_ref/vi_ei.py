"""Hierarchical RxC ecological inference fitted by variational inference on the Metal GPU (PyTorch MPS).

Model, per region, municipality i, first-round group r, runoff option c:
  beta_irc = softmax_c(eta_rc + sigma_r * eps_irc),  eps ~ N(0,1),  eta ~ N(0, 2^2),  sigma ~ HalfNormal(1)
  y_i ~ Multinomial(N_i, p_i),  p_ic = sum_r x_ir beta_irc            (Rosen et al. 2001 style)
Mean-field Gaussian q over (eta, log sigma, eps); all 5.5k municipalities, no subsampling.
Region transfer matrix: B_rc = sum_i N_i x_ir beta_irc / sum_i N_i x_ir, from draws of q.
Stability check: two independent fits (different seeds) must agree.
"""
import json, os, sys, time
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm
from ei import build, ROWS, COLS, REGION

DEV = torch.device("mps")
STEPS = 4000


def fit(X, Y, N, seed, bar=None, label=""):
    torch.manual_seed(seed)
    n, r = X.shape; c = Y.shape[1]
    x = torch.tensor(X, dtype=torch.float32, device=DEV)
    y = torch.tensor(Y * N[:, None], dtype=torch.float32, device=DEV)  # runoff counts
    P = lambda *s, v=0.0: torch.full(s, v, device=DEV, requires_grad=True)
    q = dict(eta_m=P(r, c), eta_s=P(r, c, v=-2.0), ls_m=P(r, v=-1.0), ls_s=P(r, v=-2.0),
             eps_m=P(n, r, c), eps_s=P(n, r, c, v=-2.0))
    opt = torch.optim.Adam(q.values(), lr=0.03)
    normal = torch.distributions.Normal
    hist = []
    for step in range(STEPS):
        opt.zero_grad()
        eta = q["eta_m"] + q["eta_s"].exp() * torch.randn(r, c, device=DEV)
        ls = q["ls_m"] + q["ls_s"].exp() * torch.randn(r, device=DEV)
        eps = q["eps_m"] + q["eps_s"].exp() * torch.randn(n, r, c, device=DEV)
        beta = torch.softmax(eta + ls.exp()[None, :, None] * eps, -1)
        p = (x[:, :, None] * beta).sum(1).clamp_min(1e-9)
        loglik = (y * p.log()).sum()
        logprior = (normal(0, 2.0).log_prob(eta).sum() + normal(0, 1.0).log_prob(ls.exp()).sum() + ls.sum()
                    + normal(0, 1.0).log_prob(eps).sum())
        entropy = q["eta_s"].sum() + q["ls_s"].sum() + q["eps_s"].sum()
        loss = -(loglik + logprior + entropy) / y.sum()
        loss.backward(); opt.step()
        if step % 200 == 0:
            hist.append(float(loss))
            if bar is not None:
                bar.status(f"{label} paso {step}/{STEPS} · -ELBO/voto {float(loss):.5f}")
    with torch.no_grad():
        draws = []
        w = torch.tensor(N, dtype=torch.float32, device=DEV)[:, None] * x  # n x r electors per group
        for _ in range(400):
            eta = q["eta_m"] + q["eta_s"].exp() * torch.randn(r, c, device=DEV)
            ls = q["ls_m"] + q["ls_s"].exp() * torch.randn(r, device=DEV)
            eps = q["eps_m"] + q["eps_s"].exp() * torch.randn(n, r, c, device=DEV)
            beta = torch.softmax(eta + ls.exp()[None, :, None] * eps, -1)
            draws.append(((w[:, :, None] * beta).sum(0) / w.sum(0)[:, None]).cpu().numpy())
    return np.array(draws), hist


def main():
    X, Y, N, uf = build()
    reg = np.array([REGION[u] for u in uf])
    groups = ["Norte", "Centro-Oeste", "Sul", "Sudeste", "Nordeste"]
    bar = tqdm(groups, desc="EI variacional (GPU)", unit="región", goal="transferencias 1º→2º turno, 8×4, todos los municipios")
    bar.info(dispositivo="Apple M5 Pro GPU (MPS)", pasos=STEPS, semillas=2, municipios=int(len(N)))
    out = {}
    for g in bar:
        m = reg == g
        t = time.time()
        d1, h1 = fit(X[m], Y[m], N[m], 1, bar, f"{g} semilla 1")
        d2, h2 = fit(X[m], Y[m], N[m], 2, bar, f"{g} semilla 2")
        B = d1.mean(0)
        pred = (X[m] * N[m][:, None]).sum(0) @ B / N[m].sum()
        obs = (Y[m] * N[m][:, None]).sum(0) / N[m].sum()
        out[g] = dict(mean=B.tolist(), lo=np.percentile(d1, 5, 0).tolist(), hi=np.percentile(d1, 95, 0).tolist(),
                      seed2=d2.mean(0).tolist(), max_seed_diff=float(np.abs(d1.mean(0) - d2.mean(0)).max()),
                      elbo1=h1, elbo2=h2, pred=pred.tolist(), obs=obs.tolist(), n=int(m.sum()), seconds=time.time() - t)
        json.dump(dict(rows=ROWS, cols=COLS, regions=out), open(os.path.join(HERE, "vi_ei.json"), "w"), ensure_ascii=False)
        bar.log(f"{g}: dif. entre semillas {out[g]['max_seed_diff']*100:.1f} pp · Caiado→Flávio {B[2,0]*100:.0f}% · BN→Lula {B[6,1]*100:.0f}%")


if __name__ == "__main__":
    main()
