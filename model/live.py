"""Circuito de la noche: bajar → proyectar → publicar.

Cada --every segundos baja los JSON del NYT y corre el modelo sobre dash/. Cada --push
segundos sube data/units/history a la rama `datos` (worktree en ../midterms-2026-datos), que la
página lee por raw.githubusercontent.com: no dispara builds de Pages. Cada --pages segundos
copia además el tablero entero a gh-pages (../midterms-2026-pages), como respaldo; GitHub
Pages admite ~10 builds por hora y cancela los que se encolan, así que --pages va alto.

Uso: uv run --with requests --with tqdm --with numpy --with scipy --with pandas model/live.py
"""
import argparse, os, shutil, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_nyt as F  # noqa: E402
import previa as V  # noqa: E402
import project as P  # noqa: E402

ROOT = P.ROOT
PAGES = ROOT.parent / "midterms-2026-pages"
DATOS = ROOT.parent / "midterms-2026-datos"
PUBLISH = ["index.html", "app.js", "style.css", "previa.html", "previa.js", "previa.css", "previa.json", "data.json", "units.json", "history.json", "lib", "geo"]
DATA_FILES = ["data.json", "units.json", "history.json", "previa.json"]


def publish(stamp, dest=PAGES, branch="gh-pages", names=PUBLISH):
    for name in names:
        src = ROOT / "dash" / name
        if not src.exists():
            continue
        dst = dest / name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    run = lambda *a: subprocess.run(["git", "-C", str(dest), *a], capture_output=True, text=True)
    run("add", "-A")
    if run("diff", "--cached", "--quiet").returncode == 0:
        return "sin cambios"
    run("commit", "-qm", f"Datos {stamp}")
    r = run("push", "-q", "origin", branch)
    return "publicado" if r.returncode == 0 else f"push falló: {r.stderr.strip()[:120]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-03")
    ap.add_argument("--every", type=int, default=60)
    ap.add_argument("--push", type=int, default=180)
    ap.add_argument("--pages", type=int, default=900)
    ap.add_argument("--previa", type=int, default=1800, help="cada cuánto rehacer la pestaña Previa")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    outdir = ROOT / "data" / "live" / a.date
    bar = tqdm(total=1, desc="Noche electoral", unit="página", goal="bajar, proyectar y publicar en vivo")
    bar.info(fuente="NYT / AP", ciclo=f"{a.every}s", publica="no" if a.no_push else f"datos cada {a.push}s · Pages cada {a.pages}s")
    last_push = last_pages = last_previa = 0.0
    while True:
        t0 = time.time()
        try:
            F.cycle(a.date, outdir, bar)
            bar.status("proyectando")
            sys.argv = ["project.py", "--date", a.date, "--out", str(ROOT / "dash")]
            P.main()
            if time.time() - last_previa >= a.previa:
                bar.status("rehaciendo la Previa")
                try:
                    V.main()
                except Exception as e:  # la Previa nunca frena la noche
                    bar.log(f"previa: {type(e).__name__}: {str(e)[:100]}")
                last_previa = time.time()
            stamp = time.strftime("%H:%M")
            if not a.no_push and time.time() - last_push >= a.push:
                bar.status("publicando datos")
                bar.log(f"{stamp} datos: {publish(stamp, DATOS, 'datos', DATA_FILES)}")
                last_push = time.time()
            if not a.no_push and time.time() - last_pages >= a.pages:
                bar.status("publicando respaldo en Pages")
                bar.log(f"{stamp} Pages: {publish(stamp)}")
                last_pages = time.time()
        except Exception as e:  # una caída de red o un JSON a medio escribir no corta la noche
            bar.log(f"error: {type(e).__name__}: {str(e)[:120]}")
        bar.status("esperando el próximo ciclo")
        time.sleep(max(5, a.every - (time.time() - t0)))


if __name__ == "__main__":
    main()
