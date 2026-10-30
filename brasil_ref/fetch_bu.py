"""Download a state-stratified random sample of runoff ballot-box reports (BU) and extract presidential votes.
Resumable: appends one JSON line per section to bu_r2.jsonl and skips sections already there."""
import json, os, sys, time, random, concurrent.futures as cf
import requests, asn1tools

sys.path.insert(0, os.path.expanduser("~/.claude/tools"))
from claude_tqdm import tqdm

D = "/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/bu"
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221"
OUT = os.path.join(D, "bu_r2.jsonl")
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
S = requests.Session()
S.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=16))
SPEC = asn1tools.compile_files(os.path.join(D, "spec_doccaz_urnas-br.asn1"), codec="ber")
UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to".split()


def get(url, binary=False):
    for i in range(10):
        try:
            r = S.get(url, timeout=25)
            if r.status_code == 200:
                return r.content if binary else r.json()
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 3 * (i + 1)))); continue
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(0.5 * (i + 1))
    return None


def sections():
    p = os.path.join(D, "sections_r2.json")
    if os.path.exists(p):
        return json.load(open(p))
    out = []
    for uf in tqdm(UFS, desc="lista de mesas por estado", unit="UF"):
        cfg = get(f"{BASE}/config/{uf}/{uf}-p003221-cs.json")
        for a in cfg["abr"]:
            for m in a["mu"]:
                for z in m["zon"]:
                    for s in z["sec"]:
                        out.append([uf, m["cd"], z["cd"], s["ns"]])
    json.dump(out, open(p, "w"))
    return out


def one(sec):
    uf, mu, zo, se = sec
    d = f"{BASE}/dados/{uf}/{mu}/{zo}/{se}"
    aux = get(f"{d}/p003221-{uf}-m{mu}-z{zo}-s{se}-aux.json")
    if not aux:
        return None
    h = next((x for x in aux.get("hashes", []) if x.get("st") in ("Totalizado", "Recebido")), None)
    if not h:
        return None
    nm = next((a["nm"] for a in h["arq"] if a["tp"] == "bu"), None)
    raw = get(f"{d}/{h['hash']}/{nm}", binary=True) if nm else None
    if not raw:
        return None
    env = SPEC.decode("EntidadeEnvelopeGenerico", raw)
    bu = SPEC.decode("EntidadeBoletimUrna", env["conteudo"])
    for r in bu["resultadosVotacaoPorEleicao"]:
        if r["idEleicao"] != 6258:
            continue
        rv = r["resultadosVotacao"][0]
        v = {"F": 0, "L": 0, "B": 0, "N": 0}
        for tc in rv["totaisVotosCargo"]:
            for x in tc["votosVotaveis"]:
                code = x.get("identificacaoVotavel", {}).get("codigo")
                k = {22: "F", 13: "L"}.get(code) if x["tipoVoto"] == "nominal" else {"branco": "B", "nulo": "N"}.get(x["tipoVoto"])
                if k:
                    v[k] += x["quantidadeVotos"]
        return dict(uf=uf, mu=mu, zo=zo, se=se, aptos=r["qtdEleitoresAptos"], comp=rv["qtdComparecimento"], **v)
    return None


def main():
    allsec = sections()
    random.seed(2026)
    by = {}
    for s in allsec:
        by.setdefault(s[0], []).append(s)
    pick = []
    for uf, lst in by.items():
        k = max(300, round(TARGET * len(lst) / len(allsec)))
        pick += random.sample(lst, min(k, len(lst)))
    done = set()
    if os.path.exists(OUT):
        for line in open(OUT):
            j = json.loads(line); done.add((j["uf"], j["mu"], j["zo"], j["se"]))
    todo = [s for s in pick if tuple(s) not in done]
    bar = tqdm(total=len(pick), initial=len(pick) - len(todo), desc="boletines 2º turno", unit="mesa",
               goal=f"muestra de {len(pick)} de {len(allsec)} mesas, estratificada por estado")
    bar.info(mesas_totales=len(allsec), muestra=len(pick), hilos=8)
    fails = 0
    with open(OUT, "a") as f, cf.ThreadPoolExecutor(8) as ex:
        for res in ex.map(one, todo):
            if res:
                f.write(json.dumps(res) + "\n"); f.flush()
            else:
                fails += 1
            bar.update(1)
            if bar.n % 500 == 0:
                bar.status(f"fallidas {fails}")
    bar.close()
    print(f"listo: {len(pick)-fails} mesas, {fails} fallidas")


if __name__ == "__main__":
    main()
