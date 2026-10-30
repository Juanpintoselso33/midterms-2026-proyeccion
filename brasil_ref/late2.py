"""Faster late-vote count: aux.json -> urn log (in memory) for every section; the ballot-box report (BU)
only for sections with votes after 17:00 Brasília. Sharded across processes: python late2.py <shard> <nshards> <threads>.
Resumable: skips sections already in any late*.jsonl."""
import glob, io, json, os, re, sys, time, zipfile, threading, concurrent.futures as cf
import requests, asn1tools

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm

D = "/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad"
SHARD, NSH, THREADS = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
OUT = f"{D}/late/late2_{SHARD}.jsonl"
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados"
SPEC = asn1tools.compile_files(f"{D}/bu/spec_doccaz_urnas-br.asn1", codec="ber")
TZ = {"ac": -2, "am": -1, "ro": -1, "rr": -1, "mt": -1, "ms": -1}  # local offset from Brasília (hours)
S = requests.Session()
S.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=THREADS * 2))
lock = threading.Lock()
stats = {"429": 0}
VOTE = re.compile(rb"^25/10/2026 (\d\d):(\d\d):(\d\d)\tINFO\t\d+\tVOTA\tO voto do eleitor foi computado", re.M)
OPEN = re.compile(rb"^25/10/2026 (\d\d):(\d\d):(\d\d)\tINFO\t\d+\tVOTA\tUrna pronta para receber votos", re.M)
CLOSE = re.compile(rb"^25/10/2026 (\d\d):(\d\d):(\d\d)\tINFO\t\d+\tVOTA\tProcedimento de encerramento confirmado", re.M)


def get(url, binary=False):
    for i in range(12):
        try:
            r = S.get(url, timeout=30)
            if r.status_code == 200:
                return r.content if binary else r.json()
            if r.status_code == 429:
                with lock:
                    stats["429"] += 1
                time.sleep(min(float(r.headers.get("Retry-After", 2)), 5) + 0.5 * i); continue
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(0.5 * (i + 1))
    return None


def secs(m, off):
    """Seconds since midnight in Brasília time."""
    h, mi, s = (int(x) for x in m)
    return (h - off) * 3600 + mi * 60 + s


def hms(x):
    return f"{x // 3600:02d}:{x % 3600 // 60:02d}:{x % 60:02d}" if x is not None else None


def bu_votes(raw):
    bu = SPEC.decode("EntidadeBoletimUrna", SPEC.decode("EntidadeEnvelopeGenerico", raw)["conteudo"])
    v = {"F": 0, "L": 0, "B": 0, "N": 0}
    for r in bu["resultadosVotacaoPorEleicao"]:
        if r["idEleicao"] != 6258:
            continue
        rv = r["resultadosVotacao"][0]
        v.update(aptos=r["qtdEleitoresAptos"], comp=rv["qtdComparecimento"])
        for tc in rv["totaisVotosCargo"]:
            for x in tc["votosVotaveis"]:
                code = x.get("identificacaoVotavel", {}).get("codigo")
                k = {22: "F", 13: "L"}.get(code) if x["tipoVoto"] == "nominal" else {"branco": "B", "nulo": "N"}.get(x["tipoVoto"])
                if k:
                    v[k] += x["quantidadeVotos"]
    return v


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
    lraw = get(f"{d}/{h['hash']}/{files['log']}", binary=True) if "log" in files else None
    if not lraw:
        return dict(uf=uf, mu=mu, zo=zo, se=se, err="log")
    z = zipfile.ZipFile(io.BytesIO(lraw))
    txt = z.read(z.namelist()[0])
    txt = txt[max(txt.find(b"25/10/2026"), 0):]
    op = OPEN.findall(txt)
    off = TZ.get(uf, 0)
    if uf == "pe" and op and int(op[0][0]) == 9:  # Fernando de Noronha (UTC-2)
        off = 1
    votes = [secs(m, off) for m in VOTE.findall(txt)]
    cl = CLOSE.findall(txt)
    res = dict(uf=uf, mu=mu, zo=zo, se=se, off=off, votes=len(votes),
               open=hms(secs(op[0], off)) if op else None, close=hms(secs(cl[-1], off)) if cl else None,
               last=hms(max(votes)) if votes else None,
               after17=sum(v >= 17 * 3600 for v in votes), after18=sum(v >= 18 * 3600 for v in votes),
               after19=sum(v >= 19 * 3600 for v in votes))
    if res["after17"] and "bu" in files:
        raw = get(f"{d}/{h['hash']}/{files['bu']}", binary=True)
        if raw:
            res.update(bu_votes(raw))
    return res


def main():
    allsec = json.load(open(f"{D}/bu/sections_r2.json"))
    done = set()
    for p in glob.glob(f"{D}/late/late2_*.jsonl"):
        for line in open(p):
            j = json.loads(line)
            if "err" not in j:
                done.add((j["uf"], j["mu"], j["zo"], j["se"]))
    mine = [s for i, s in enumerate(allsec) if i % NSH == SHARD]
    todo = [s for s in mine if tuple(s) not in done]
    bar = tqdm(total=len(mine), initial=len(mine) - len(todo), desc=f"Votos post-17 h · parte {SHARD + 1}/{NSH}", unit="mesa",
               goal="log de cada mesa del 2º turno, en memoria; votos con hora después de las 17 (Brasília)")
    bar.info(hilos=THREADS, disco="nada: todo en memoria")
    a17 = n17 = errs = 0
    with open(OUT, "a") as f, cf.ThreadPoolExecutor(THREADS) as ex:
        futs = [ex.submit(one, s) for s in todo]
        for fu in cf.as_completed(futs):
            res = fu.result()
            f.write(json.dumps(res) + "\n")
            if "err" in res:
                errs += 1
            elif res["after17"]:
                n17 += 1; a17 += res["after17"]
            bar.update(1)
            if bar.n % 200 == 0:
                f.flush()
                bar.info(mesas_con_votos_post17=n17, votos_post17=a17, errores=errs, http429=stats["429"])
    bar.close()
    print(f"parte {SHARD}: mesas con votos post-17 {n17}, votos {a17}, errores {errs}")


if __name__ == "__main__":
    main()
