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
    p = (meta or {}).get("party") or {} if isinstance(meta, dict) else {}
    return {"DEM": "D", "GOP": "R"}.get(p.get("nyt_id"), "O")


def flatten(outdir):
    """Una fila por (carrera, unidad de reporte) con votos D/R/otros y votos esperados."""
    rows, seen = [], set()
    files = sorted((outdir / "raw").glob("*.json"))
    # Las páginas por estado primero: tienen condados; las generales sólo completan lo que falte.
    files.sort(key=lambda p: p.stem in ("results-senate", "results-governor", "results-house"))
    for f in files:
        try:
            d = json.loads(f.read_bytes())
        except json.JSONDecodeError:
            continue
        for r in d.get("races", []):
            meta = r.get("candidate_metadata") or {}
            won = (r.get("outcome") or {}).get("won") or []
            parties = "".join(sorted(party_of(m) for m in meta.values()))
            for u in r.get("reporting_units", []):
                key = (r["nyt_id"], u["nyt_id"])
                if key in seen:
                    continue
                seen.add(key)
                v = {p: {"total": 0, **{t: 0 for t in TYPES}} for p in "DRO"}
                for c in u.get("candidates", []):
                    p = party_of(meta.get(c["nyt_id"]))
                    for k, n in (c.get("votes") or {}).items():
                        if k in v[p]:
                            v[p][k] += n or 0
                ev = u.get("expected_vote_by_vote_type") or {}
                ee = u.get("eevp_by_vote_type") or {}
                hist = next(iter((u.get("historical_comparison_race_data") or {}).values()), {}) or {}
                row = {
                    "race_id": r["nyt_id"], "office": r.get("office_id"), "state": u.get("state_postal"),
                    "seat": r.get("seat_number"), "rating": r.get("rating"),
                    "call": r.get("race_call_status"), "winner": ",".join(party_of(meta.get(w)) for w in won),
                    "uncontested": r.get("uncontested"), "tabulation": r.get("tabulation_method"),
                    "parties": parties, "race_type": r.get("race_type_id"),
                    "unit_id": u["nyt_id"], "level": u.get("level"), "name": u.get("name"),
                    "fips": (u.get("fips_state") or "") + (u.get("fips_county") or ""),
                    "eevp": u.get("eevp"), "expected": u.get("total_expected_vote"),
                    "total": u.get("total_votes"),
                    "prec_rep": u.get("precincts_reporting"), "prec_tot": u.get("precincts_total"),
                    "hist_dem": hist.get("pct_dem"), "hist_rep": hist.get("pct_rep"),
                }
                for p in "DRO":
                    row[p] = v[p]["total"]
                    for t in TYPES:
                        row[f"{p}_{t}"] = v[p][t]
                for t in TYPES:
                    row[f"exp_{t}"] = ev.get(t)
                    row[f"eevp_{t}"] = ee.get(t)
                rows.append(row)
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
