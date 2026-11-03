"""Lector de los JSON públicos del NYT (datos AP) para la noche del 3-nov-2026.

Baja los tres archivos generales (senate, governor, house) y las páginas por estado de
Senado y gobernación (que traen el detalle por condado). Guarda la última versión de cada
uno y un snapshot comprimido sólo cuando cambia. Después aplana todo en units.csv.

Uso:
  uv run --with requests --with tqdm model/fetch_nyt.py --once
  uv run --with requests --with tqdm model/fetch_nyt.py --every 90
  uv run --with requests --with tqdm model/fetch_nyt.py --date 2024-11-05 --once   # ensayo
"""
import argparse, csv, gzip, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://static01.nyt.com/elections-assets/pages/data/{date}/{slug}.json"
UA = {"User-Agent": "Mozilla/5.0 (proyeccion personal midterms 2026)"}
TYPES = ("advance", "absentee_mail", "election_day_in_person", "provisional")
THREADS = 4

def poll_leaders():
    """(estado, cargo) -> apellido del independiente que encabeza las encuestas frente al
    republicano (p. ej. Osborn en Nebraska). Sólo se usa para elegir el rival antes de que haya votos."""
    p = ROOT / "research" / "previa_encuestas.json"
    if not p.exists():
        return {}
    out = {}
    for r in json.loads(p.read_text()).get("races", []):
        if r.get("other") is not None and (r.get("D") is None or r["other"] > r["D"]) and r.get("other_name"):
            out[(r["state"], r["office"])] = r["other_name"].split(" (")[0].split()[-1].lower()
    return out


PREFER = poll_leaders()
session = requests.Session()
session.headers.update(UA)
etags = {}


def get(date, slug, tries=6):
    """GET condicional con backoff. Devuelve (status, bytes|None)."""
    url = BASE.format(date=date, slug=slug)
    h = {"If-None-Match": etags[slug]} if slug in etags else {}
    for i in range(tries):
        try:
            r = session.get(url, headers=h, timeout=30)
        except requests.RequestException:
            time.sleep(2 ** i)
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(float(r.headers.get("Retry-After", 2 ** i)))
            continue
        if r.status_code == 200 and r.headers.get("ETag"):
            etags[slug] = r.headers["ETag"]
        return r.status_code, (r.content if r.status_code == 200 else None)
    return 0, None


def state_slugs(overview):
    """'https://.../results-alabama-us-senate.html' -> 'results-alabama-us-senate'."""
    out = []
    for r in overview.get("races", []):
        u = r.get("url")
        if u:
            out.append(u.rsplit("/", 1)[1].removesuffix(".html"))
    return out


def save(outdir, slug, content, stamp):
    (outdir / "raw").mkdir(parents=True, exist_ok=True)
    latest = outdir / "raw" / f"{slug}.json"
    if latest.exists() and latest.read_bytes() == content:
        return False
    tmp = latest.with_suffix(".tmp")
    tmp.write_bytes(content)
    tmp.replace(latest)
    snap = outdir / "snap" / slug
    snap.mkdir(parents=True, exist_ok=True)
    with gzip.open(snap / f"{stamp}.json.gz", "wb") as f:
        f.write(content)
    return True


def party_of(meta):
    p = ((meta or {}).get("party") or {}) if isinstance(meta, dict) else {}
    return {"DEM": "D", "GOP": "R"}.get(p.get("nyt_id"), "I")


def caucus_of(meta):
    """Bancada: la declarada por el feed (p. ej. King/Sanders votan con los demócratas)."""
    c = (meta or {}).get("party_caucus") if isinstance(meta, dict) else None
    c = c.get("nyt_id") if isinstance(c, dict) else c
    return {"DEM": "D", "GOP": "R"}.get(c, party_of(meta))


def main_pair(r):
    """Los dos candidatos que se modelan: X = principal no republicano, Y = principal rival
    (el republicano con más votos; si no hay republicano, el siguiente más votado).
    Sin votos todavía: el independiente que lideran las encuestas > demócrata > incumbente >
    orden en la boleta."""
    meta = r.get("candidate_metadata") or {}
    top = r.get("top_reporting_unit") or (r.get("reporting_units") or [{}])[0]
    votes = {c["nyt_id"]: (c.get("votes") or {}).get("total") or 0 for c in top.get("candidates", [])}
    ids = list(meta) or list(votes)
    pref = PREFER.get((top.get("state_postal"), r.get("office_id")), "\0")
    rank = lambda i: (votes.get(i, 0), ((meta.get(i) or {}).get("last_name") or "").lower() == pref,
                      party_of(meta.get(i)) == "D", bool((meta.get(i) or {}).get("incumbent")),
                      -((meta.get(i) or {}).get("ballot_order") or 99))
    non_r = sorted([i for i in ids if party_of(meta.get(i)) != "R"], key=rank, reverse=True)
    rep = sorted([i for i in ids if party_of(meta.get(i)) == "R"], key=rank, reverse=True)
    if not non_r:  # sólo republicanos (R contra R)
        x = rep[0] if rep else None
        y = rep[1] if len(rep) > 1 else None
    else:
        x = non_r[0]
        y = rep[0] if rep else (non_r[1] if len(non_r) > 1 else None)
    return x, y, meta


def race_rows(r):
    x, y, meta = main_pair(r)
    won = (r.get("outcome") or {}).get("won") or []
    out = []
    for u in r.get("reporting_units", []):
        tv = {"X": {"total": 0, **{t: 0 for t in TYPES}}, "Y": {"total": 0, **{t: 0 for t in TYPES}},
              "T": {t: 0 for t in TYPES}}
        for c in u.get("candidates", []):
            k = "X" if c["nyt_id"] == x else ("Y" if c["nyt_id"] == y else None)
            for t, n in (c.get("votes") or {}).items():
                if t in TYPES:
                    tv["T"][t] += n or 0
                if k and t in tv[k]:
                    tv[k][t] += n or 0
        ev = u.get("expected_vote_by_vote_type") or {}
        ee = u.get("eevp_by_vote_type") or {}
        hist = next(iter((u.get("historical_comparison_race_data") or {}).values()), {}) or {}
        row = {
            "race_id": r["nyt_id"], "office": r.get("office_id"), "state": u.get("state_postal"),
            "seat": r.get("seat_number"), "rating": r.get("rating"), "call": r.get("race_call_status"),
            "winner_ids": ",".join(won), "uncontested": r.get("uncontested"),
            "tabulation": r.get("tabulation_method"), "win_threshold": r.get("win_threshold"),
            "race_type": r.get("race_type_id"), "updated_at": r.get("updated_at"),
            "x_id": x, "y_id": y,
            "x_party": party_of(meta.get(x)) if x else "", "y_party": party_of(meta.get(y)) if y else "",
            "x_caucus": caucus_of(meta.get(x)) if x else "", "y_caucus": caucus_of(meta.get(y)) if y else "",
            "x_name": (meta.get(x) or {}).get("last_name", ""), "y_name": (meta.get(y) or {}).get("last_name", ""),
            "unit_id": u["nyt_id"], "level": u.get("level"), "name": u.get("name"),
            "fips": (u.get("fips_state") or "") + (u.get("fips_county") or ""),
            "eevp": u.get("eevp"), "expected": u.get("total_expected_vote"), "total": u.get("total_votes"),
            "prec_rep": u.get("precincts_reporting"), "prec_tot": u.get("precincts_total"),
            "hist_dem": hist.get("pct_dem"), "hist_rep": hist.get("pct_rep"),
            "X": tv["X"]["total"], "Y": tv["Y"]["total"],
        }
        for t in TYPES:
            row[f"X_{t}"], row[f"Y_{t}"], row[f"T_{t}"] = tv["X"][t], tv["Y"][t], tv["T"][t]
            row[f"exp_{t}"], row[f"eevp_{t}"] = ev.get(t), ee.get(t)
        out.append(row)
    return out


def flatten(outdir):
    """Una fila por (carrera, unidad de reporte) con los dos candidatos principales.

    Cada carrera aparece en el archivo general y en su página por estado. Se usa la fuente con
    más votos contados en la unidad de arriba (los conteos sólo suben); a igualdad, la que trae
    más detalle geográfico. Así una página estatal que dejó de actualizarse no tapa al general.
    """
    best = {}
    for f in sorted((outdir / "raw").glob("*.json")):
        try:
            d = json.loads(f.read_bytes())
        except json.JSONDecodeError:
            continue
        for r in d.get("races", []):
            top = r.get("top_reporting_unit") or (r.get("reporting_units") or [{}])[0]
            score = (top.get("total_votes") or 0, len(r.get("winner_ids", []) or (r.get("outcome") or {}).get("won") or []),
                     len(r.get("reporting_units") or []))
            if r["nyt_id"] not in best or score > best[r["nyt_id"]][0]:
                best[r["nyt_id"]] = (score, r)
    rows = [row for _, r in best.values() for row in race_rows(r)]
    if rows:
        tmp = outdir / "units.tmp"
        with open(tmp, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        tmp.replace(outdir / "units.csv")
    return len(rows)


def cycle(date, outdir, bar):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    overviews = ["results-senate", "results-governor", "results-house"]
    changed, missing = 0, 0
    slugs = list(overviews)
    for s in overviews:
        st, body = get(date, s)
        if body:
            changed += save(outdir, s, body, stamp)
            slugs += state_slugs(json.loads(body))
        elif (outdir / "raw" / f"{s}.json").exists():  # 304: usar el último para la lista
            slugs += state_slugs(json.loads((outdir / "raw" / f"{s}.json").read_bytes()))
    per_state = [s for s in dict.fromkeys(slugs) if s not in overviews and "-us-house-" not in s]
    bar.reset(total=len(per_state))
    bar.status(f"{len(per_state)} páginas por estado")

    def one(s):
        return s, *get(date, s)

    with ThreadPoolExecutor(THREADS) as ex:
        for s, st, body in ex.map(one, per_state):
            if body:
                changed += save(outdir, s, body, stamp)
            elif st == 404:
                missing += 1
            bar.update(1)
    n = flatten(outdir)
    bar.log(f"{stamp}: {changed} archivos nuevos · {missing} páginas aún sin publicar · {n} filas")
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-03")
    ap.add_argument("--every", type=int, default=0, help="segundos entre ciclos (0 = una vez)")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    outdir = ROOT / "data" / "live" / a.date
    bar = tqdm(total=1, desc=f"NYT {a.date}", unit="página", goal="bajar resultados en vivo")
    bar.info(fuente="NYT / AP", hilos=THREADS, intervalo=f"{a.every}s" if a.every else "una vez")
    while True:
        cycle(a.date, outdir, bar)
        if a.once or not a.every:
            break
        time.sleep(a.every)
    bar.close()


if __name__ == "__main__":
    main()
