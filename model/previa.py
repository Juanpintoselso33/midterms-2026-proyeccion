"""Datos de la pestaña "Previa": voto anticipado, encuestas y pronósticos antes del conteo.

Junta tres fuentes en dash/previa.json:
- Voto anticipado por estado (UF Election Lab, Michael McDonald; CC BY-NC-ND 4.0).
- Encuestas y pronósticos públicos (research/previa_encuestas.json, relevado a mano con fuente y fecha).
- La proyección propia de dash/data.json, para comparar.

Uso: uv run --with requests model/previa.py
"""
import csv, io, json, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dash"
UF = "https://election.lab.ufl.edu/data-downloads/earlyvote/2026/US.csv"
UA = {"User-Agent": "Mozilla/5.0 (proyeccion personal midterms 2026)"}


def num(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def early():
    r = requests.get(UF, headers=UA, timeout=60)
    r.raise_for_status()
    (ROOT / "data" / "base" / "early_vote" / "hoy").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "base" / "early_vote" / "hoy" / "US.csv").write_bytes(r.content)
    rows = list(csv.DictReader(io.StringIO(r.content.decode("utf-8"))))
    states = []
    for x in rows:
        voted, t22 = num(x["voted_all"]), num(x["turn_2022"])
        d, rp, n = num(x["voted_dem"]), num(x["voted_rep"]), num(x["voted_none"])
        states.append(dict(
            st=x["state_abbv"], name=x["state"], voted=voted, mail=num(x["accept_all"]),
            inperson=num(x["inperson_all"]), turn22=t22, pct22=round(voted / t22, 4) if t22 else None,
            dem=d, rep=rp, none=n, party=bool(d + rp), last=x["last_update"]))
    states.sort(key=lambda s: -s["voted"])
    wp = [s for s in states if s["party"]]
    tot = lambda k, ss=states: sum(s[k] for s in ss)
    return dict(
        source="UF Election Lab (election.lab.ufl.edu), datos oficiales de cada estado",
        url="https://election.lab.ufl.edu/early-vote/2026-early-voting/",
        voted=tot("voted"), mail=tot("mail"), inperson=tot("inperson"), turn22=tot("turn22"),
        missing=sorted({"AL", "NH"} - {s["st"] for s in states}),
        party=dict(states=len(wp), dem=tot("dem", wp), rep=tot("rep", wp), none=tot("none", wp),
                   voted=tot("voted", wp)),
        states=states)


def ours():
    d = json.loads((DASH / "data.json").read_text())
    ch = {k: {kk: v[kk] for kk in ("p_D", "p_R", "D_med", "R_med", "D_ci90", "R_ci90")}
          for k, v in d["chambers"].items()}
    races = {}
    for r in d["races"]:
        if r["office"] in ("S", "G") and r.get("proj_B") is not None:
            d_share = r["proj_B"] if r["x_caucus"] == "D" else r["proj_R"]
            races[f'{r["state"]}-{r["office"]}'] = dict(
                p_D=r["p_B_win"] if r["x_caucus"] == "D" else (1 - r["p_B_win"] if r["p_B_win"] is not None else None),
                share_D=d_share, share_R=round(100 - d_share, 2), x=r["x_name"], y=r["y_name"],
                rating=r.get("rating"))
    return dict(updated=d.get("updated"), chambers=ch, races=races)


def main():
    out = dict(updated=time.strftime("%Y-%m-%d %H:%M"), early=early(), ours=ours())
    p = ROOT / "research" / "previa_encuestas.json"
    out["polls"] = json.loads(p.read_text()) if p.exists() else {}
    tmp = DASH / "previa.tmp"
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(DASH / "previa.json")
    e = out["early"]
    print(f'anticipado {e["voted"]:,} votos ({e["voted"] / e["turn22"]:.0%} del total 2022) · '
          f'encuestas: {len(out["polls"].get("races", []))} carreras')


if __name__ == "__main__":
    main()
