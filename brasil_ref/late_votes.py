"""Count runoff votes cast after 17:00 (Brasília) in EVERY section, without storing downloads on disk.
Per section: aux.json -> ballot-box report (BU, in memory) for closing time and votes;
only if the section closed after 17:00 Brasília, fetch the urn log (in memory) and count timestamped votes.
Resumable: one JSON line per section in late.jsonl."""
import io, json, os, sys, time, zipfile, threading, concurrent.futures as cf
from datetime import datetime, timedelta
import requests, asn1tools

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm

D = "/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad"
OUT = f"{D}/late/late.jsonl"
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados"
SPEC = asn1tools.compile_files(f"{D}/bu/spec_doccaz_urnas-br.asn1", codec="ber")
THREADS = int(sys.argv[1]) if len(sys.argv) > 1 else 12
# local offset from Brasília time (hours)
TZ = {"ac": -2, "am": -1, "ro": -1, "rr": -1, "mt": -1, "ms": -1}
S = requests.Session()
S.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=THREADS * 2))
lock = threading.Lock()
stats = {"429": 0}


def get(url, binary=False):
    for i in range(12):
        try:
            r = S.get(url, timeout=30)
            if r.status_code == 200:
                return r.content if binary else r.json()
            if r.status_code == 429:
                with lock:
                    stats["429"] += 1
                time.sleep(float(r.headers.get("Retry-After", 2 * (i + 1)))); continue
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(0.5 * (i + 1))
    return None


def ts(s):
    return datetime.strptime(s, "%Y%m%dT%H%M%S")


def one(sec):
    uf, mu, zo, se = sec
    d = f"{BASE}/{uf}/{mu}/{zo}/{se}"
    aux = get(f"{d}/p003221-{uf}-m{mu}-z{zo}-s{se}-aux.json")
    if not aux:
        return dict(uf=uf, mu=mu, zo=zo, se=se, err="aux")
    h = next((x for x in aux.get("hashes", []) if x.get("st") in ("Totalizado", "Recebido")), None)
    if not h:
        return dict(uf=uf, mu=mu, zo=zo, se=se, err="hash")
    files = {a["tp"]: a["nm"] for a in h["arq"]}
    raw = get(f"{d}/{h['hash']}/{files.get('bu')}", binary=True) if "bu" in files else None
    if not raw:
        return dict(uf=uf, mu=mu, zo=zo, se=se, err="bu")
    bu = SPEC.decode("EntidadeBoletimUrna", SPEC.decode("EntidadeEnvelopeGenerico", raw)["conteudo"])
    ds = bu.get("dadosSecaoSA", (None, {}))[1]
    ab, enc = ds.get("dataHoraAbertura"), ds.get("dataHoraEncerramento")
    res = dict(uf=uf, mu=mu, zo=zo, se=se, ab=ab, enc=enc, F=0, L=0, B=0, N=0)
    for r in bu["resultadosVotacaoPorEleicao"]:
        if r["idEleicao"] != 6258:
            continue
        rv = r["resultadosVotacao"][0]
        res.update(aptos=r["qtdEleitoresAptos"], comp=rv["qtdComparecimento"])
        for tc in rv["totaisVotosCargo"]:
            for x in tc["votosVotaveis"]:
                code = x.get("identificacaoVotavel", {}).get("codigo")
                k = {22: "F", 13: "L"}.get(code) if x["tipoVoto"] == "nominal" else {"branco": "B", "nulo": "N"}.get(x["tipoVoto"])
                if k:
                    res[k] += x["quantidadeVotos"]
    off = TZ.get(uf, 0)
    if uf == "pe" and ab and ts(ab).hour == 9:  # Fernando de Noronha (UTC-2)
        off = 1
    res["off"] = off
    cut17 = datetime(2026, 10, 25, 17) + timedelta(hours=off)
    if not enc or ts(enc) <= cut17:
        res["late"] = 0
        return res
    # closed after 17:00 Brasília: read the urn log in memory and count votes by time
    lraw = get(f"{d}/{h['hash']}/{files.get('log')}", binary=True) if "log" in files else None
    if not lraw:
        res["err"] = "log"; return res
    z = zipfile.ZipFile(io.BytesIO(lraw))
    txt = z.read(z.namelist()[0]).decode("latin-1")
    times = []
    for line in txt.splitlines():
        if line.startswith("25/10/2026") and "O voto do eleitor foi computado" in line:
            times.append(datetime.strptime(line[:19], "%d/%m/%Y %H:%M:%S") - timedelta(hours=off))
    a17 = [t for t in times if t >= datetime(2026, 10, 25, 17)]
    res.update(late=1, votes_log=len(times), after17=len(a17),
               after18=sum(t >= datetime(2026, 10, 25, 18) for t in a17),
               after19=sum(t >= datetime(2026, 10, 25, 19) for t in a17),
               last=max(times).strftime("%H:%M:%S") if times else None)
    return res


def main():
    allsec = json.load(open(f"{D}/bu/sections_r2.json"))
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            j = json.loads(line)
            if "err" not in j:
                done.add((j["uf"], j["mu"], j["zo"], j["se"]))
    todo = [s for s in allsec if tuple(s) not in done]
    bar = tqdm(total=len(allsec), initial=len(allsec) - len(todo), desc="Votos después de las 17 h", unit="mesa",
               goal="todas las mesas del 2º turno: hora de cierre, y si cerró tarde, votos con hora del log")
    bar.info(mesas=len(allsec), hilos=THREADS, disco="nada: todo en memoria")
    n_late = a17 = errs = 0
    with open(OUT, "a") as f, cf.ThreadPoolExecutor(THREADS) as ex:
        for res in ex.map(one, todo):
            f.write(json.dumps(res) + "\n")
            if "err" in res:
                errs += 1
            elif res.get("late"):
                n_late += 1; a17 += res["after17"]
            bar.update(1)
            if bar.n % 200 == 0:
                f.flush()
                bar.info(mesas_tarde=n_late, votos_post17=a17, errores=errs, http429=stats["429"])
                bar.status(f"{res['uf'].upper()} · mesas que cerraron tarde: {n_late} · votos después de las 17: {a17}")
    bar.close()
    print(f"listo: tarde {n_late}, votos post-17 {a17}, errores {errs}")


if __name__ == "__main__":
    main()
