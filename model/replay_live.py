"""Ensayo de punta a punta sobre la página real: reproduce la noche de 2024 a velocidad rápida.

Usa el mismo modelo y la misma publicación que la noche real. El conteo sintético es el de
rehearse.py (condados que reportan según la hora de cierre y el tamaño, con sesgo de orden de
conteo). Al terminar deja el último estado publicado; los datos de 2026 se restauran aparte
con model/project.py + live.publish (y borrando dash/history.json).

Uso: uv run --with requests --with tqdm --with numpy --with scipy --with pandas model/replay_live.py
"""
import argparse, json, os, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live  # noqa: E402
import project as P  # noqa: E402
import rehearse as H  # noqa: E402

ROOT = P.ROOT
DASH = ROOT / "dash"


def write(name, obj):
    tmp = DASH / (name + ".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":")))
    tmp.replace(DASH / name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=40)
    ap.add_argument("--every", type=int, default=60)
    ap.add_argument("--push", type=int, default=420)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    df = P.load("2024-11-05", base_year=2020).reset_index(drop=True)
    df = df[~df.race_id.str.startswith("US-")].reset_index(drop=True)
    rng = np.random.default_rng(a.seed)
    size = df.expected.rank(pct=True).values
    tau = df.state.map(H.CLOSE).fillna(1).values + 0.3 + 1.5 * size * rng.uniform(0.3, 1, len(df))
    dur = 0.5 + 3 * size * rng.uniform(0.5, 1.5, len(df))
    sb = {s: rng.normal(0, 0.04) for s in df.state.unique()}
    beta = df.state.map(sb).values * rng.uniform(0.5, 1.5, len(df))
    noise = np.exp(rng.normal(0, 0.03, len(df)))
    state = (tau, dur, beta, noise)
    control = P.control_from_raw("2024-11-05")

    n = int(a.minutes * 60 / a.every)
    hist, last_push = [], 0.0
    bar = tqdm(range(n), desc="Ensayo 2024 en la página", unit="ciclo", goal="probar el circuito completo en vivo")
    bar.info(duración=f"{a.minutes} min", publica=f"cada {a.push}s", carreras=df.race_id.nunique())
    for k in bar:
        t0 = time.time()
        hrs = 0.3 + 10.5 * k / max(n - 1, 1)
        hh, mm = divmod(int((19 + hrs) * 60), 60)
        clock = f"Hora simulada: {hh % 24:02d}:{mm:02d} ET del 5-nov-2024."
        bar.status(clock)
        d = H.rebuild_state_rows(H.synth(df, hrs, state, 0.04)).assign(b=df.b.values)
        m = P.Model(d).fit().simulate()
        s = m.summary(control)
        s.update(updated=f"ensayo 2024 · {hh % 24:02d}:{mm:02d} ET", mode="ensayo", clock=clock, cells=m.ncells)
        write("data.json", s)
        write("units.json", m.map_units())
        hist.append(dict(t=f"{hh % 24:02d}:{mm:02d}", **{o: {kk: v[kk] for kk in ("p_D", "p_R", "D_med", "R_med", "D_ci90", "R_ci90")}
                                                         for o, v in s["chambers"].items()}))
        write("history.json", hist)
        S = s["chambers"]["S"]
        bar.log(f"{hh % 24:02d}:{mm:02d} ET · Senado P(D)={S['p_D']:.2f} D={S['D_med']} · celdas {m.ncells}")
        if not a.no_push and (time.time() - last_push >= a.push or k == n - 1):
            bar.status("publicando")
            bar.log(f"publicación: {live.publish('ensayo ' + clock[15:20])}")
            last_push = time.time()
        time.sleep(max(1, a.every - (time.time() - t0)))
    bar.close()


if __name__ == "__main__":
    main()
