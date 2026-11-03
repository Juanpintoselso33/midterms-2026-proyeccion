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


def expected():
    """Votos totales esperados según AP (feed del NYT), nacional y por estado.

    Por estado se usa la carrera estatal más grande (gobernación o Senado); si no hay, la suma de
    la Cámara, que se queda corta donde hay bancas sin rival."""
    raw = ROOT / "data" / "live" / "2026-11-03" / "raw"
    nat, st = None, {}
    for f in ("results-house", "results-senate", "results-governor"):
        house, acc = f == "results-house", {}
        for r in json.loads((raw / f"{f}.json").read_text())["races"]:
            t = r.get("top_reporting_unit") or (r.get("reporting_units") or [{}])[0]
            if r["nyt_id"].startswith("US-"):
                nat = t.get("total_expected_vote")
                continue
            s, v = t.get("state_postal"), t.get("total_expected_vote") or 0
            acc[s] = acc.get(s, 0) + v if house else max(acc.get(s, 0), v)
        for s, v in acc.items():
            st[s] = max(st.get(s, 0), v)
    return nat, st


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
    nat, st = expected()
    e = out["early"]
    e["expected"] = nat
    e["expected_states"] = sum(st.values())
    for s in e["states"]:
        s["exp"] = st.get(s["st"])
        s["pct_exp"] = round(s["voted"] / s["exp"], 4) if s.get("exp") else None
    # Estados sin voto anticipado publicado (AL, NH): igual van en la tabla de participación.
    have = {s["st"] for s in e["states"]}
    for k, v in st.items():
        if k not in have:
            e["states"].append(dict(st=k, name=k, voted=None, mail=None, inperson=None, turn22=None, pct22=None,
                                    dem=0, rep=0, none=0, party=False, last="", exp=v, pct_exp=None))
    p = ROOT / "research" / "previa_encuestas.json"
    out["polls"] = json.loads(p.read_text()) if p.exists() else {}
    tmp = DASH / "previa.tmp"
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(DASH / "previa.json")
    print(f'anticipado {e["voted"]:,} votos ({e["voted"] / e["turn22"]:.0%} del total 2022) · '
          f'encuestas: {len(out["polls"].get("races", []))} carreras')


if __name__ == "__main__":
    main()
