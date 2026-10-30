import base64, json, subprocess, os
import asn1tools

D = "/private/tmp/claude-501/-Users-juan/1dc079a7-9ad1-4c7f-a0fd-1a00e80929c8/scratchpad/bu"
SPECS = ["kuca-belludo/urnas:spec/bu.asn1", "doccaz/urnas-br:docv2/spec/bu.asn1",
         "doccaz/urnas-br:doc/spec/bu.asn1", "tonylampada/eleicoes22:tse/spec/bu.asn1"]
data = open(os.path.join(D, "sample.bu"), "rb").read()
for s in SPECS:
    repo, path = s.split(":")
    out = os.path.join(D, "spec_" + repo.replace("/", "_") + ".asn1")
    if not os.path.exists(out):
        b64 = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}", "--jq", ".content"],
                             capture_output=True, text=True).stdout
        open(out, "wb").write(base64.b64decode(b64))
    try:
        c = asn1tools.compile_files(out, codec="ber")
        e = c.decode("EntidadeEnvelopeGenerico", data)
        bu = c.decode("EntidadeBoletimUrna", e["conteudo"])
        for r in bu["resultadosVotacaoPorEleicao"]:
            for rv in r["resultadosVotacao"]:
                votes = [(v["tipoVoto"], v.get("identificacaoVotavel", {}).get("codigo"), v["quantidadeVotos"])
                         for tc in rv["totaisVotosCargo"] for v in tc["votosVotaveis"]]
                print(repo, "OK aptos", r["qtdEleitoresAptos"], "comp", rv["qtdComparecimento"], votes)
    except Exception as ex:
        print(repo, "FALLA", str(ex)[-160:])
