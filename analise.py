"""Análise das RQs (RQ1, RQ2, RQ3) do experimento. Stdlib apenas."""
import csv
import math
import os
import re
import statistics

RESPOSTAS_DIR = "Respostas"
TAREFAS_DIR = "Material/Tarefas"
GABARITO_DIR = "Material/Gabarito"
TAREFAS_CSV = "Material/tarefas.csv"
RESULTADOS_DIR = "resultados"
IGNORAR_MODELOS = {"tmp", "old", "backup"}
REL_TOL = 1e-9

TERMOS_RQ3 = {
    "legibilidade": ["legibilidade", "legível", "legivel", "legíveis", "legiveis"],
    "concisao": ["concisão", "concisao", "conciso", "concisa", "concisos", "concisas"],
    "modificabilidade": ["modificabilidade", "modificável", "modificavel"],
    "funcional": ["funcional", "funcionais"],
    "procedural": ["procedural", "procedurais"],
}

_AVISOS = []


def registrar(nivel, msg):
    """Imprime no terminal e acumula para resultados/avisos.log."""
    linha = f"[{nivel}] {msg}"
    print(linha)
    _AVISOS.append(linha)


def ler_texto(caminho):
    """Lê um arquivo utf-8; retorna None se não existir."""
    if not os.path.isfile(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def expandir_tokens(s):
    """Converte '6.3k' -> 6300 e '239' -> 239."""
    s = s.strip().lower()
    if s.endswith("k"):
        return int(round(float(s[:-1]) * 1000))
    return int(s)


_LINHA_USAGE = re.compile(
    r"^\s*([\w.-]+):\s*"
    r"([\d.]+k?)\s+input,\s*"
    r"([\d.]+k?)\s+output,\s*"
    r"([\d.]+k?)\s+cache read,\s*"
    r"([\d.]+k?)\s+cache write",
    re.MULTILINE,
)


def parse_usage(texto):
    """Extrai tokens por sub-modelo de um usage.txt."""
    entradas = []
    for m in _LINHA_USAGE.finditer(texto):
        entradas.append({
            "submodelo": m.group(1),
            "input": expandir_tokens(m.group(2)),
            "output": expandir_tokens(m.group(3)),
            "cache_read": expandir_tokens(m.group(4)),
            "cache_write": expandir_tokens(m.group(5)),
        })
    return entradas


def normalizar_saida(texto):
    """Normaliza: strip por linha, remove linhas vazias nas pontas."""
    linhas = texto.replace("\r\n", "\n").split("\n")
    linhas = [ln.strip() for ln in linhas]
    while linhas and linhas[0] == "":
        linhas.pop(0)
    while linhas and linhas[-1] == "":
        linhas.pop()
    return "\n".join(linhas)


def _como_numeros(texto):
    """Retorna lista de floats se todos os tokens do texto forem numéricos, senão None."""
    tokens = texto.replace(",", " ").split()
    if not tokens:
        return None
    try:
        return [float(t) for t in tokens]
    except ValueError:
        return None


def comparar_saida(saida, gabarito):
    """True se a saída bate com o gabarito (numérico com tolerância, senão texto)."""
    ns, ng = normalizar_saida(saida), normalizar_saida(gabarito)
    nums_s, nums_g = _como_numeros(ns), _como_numeros(ng)
    if nums_s is not None and nums_g is not None and len(nums_s) == len(nums_g):
        return all(math.isclose(a, b, rel_tol=REL_TOL) for a, b in zip(nums_s, nums_g))
    return ns == ng


def descobrir_modelos(base=RESPOSTAS_DIR):
    """Lista pastas-modelo válidas em `base`, com salvaguarda contra modelos fantasma."""
    modelos = []
    if not os.path.isdir(base):
        registrar("ERRO", f"Diretório de respostas não encontrado: {base}")
        return modelos
    for nome in sorted(os.listdir(base)):
        caminho = os.path.join(base, nome)
        if not os.path.isdir(caminho):
            continue
        if nome[0] in "._" or nome.lower() in IGNORAR_MODELOS:
            registrar("AVISO", f"Pasta ignorada na descoberta de modelos: {nome}")
            continue
        tem_ex = any(re.fullmatch(r"Ex\d+", x) and
                     os.path.isdir(os.path.join(caminho, x))
                     for x in os.listdir(caminho))
        if not tem_ex:
            continue
        modelos.append(nome)
    return modelos


def avaliar_status(exec_dir, gabarito):
    """Classifica uma execução: ausente / erro_execucao / saida_incorreta / ok."""
    output = ler_texto(os.path.join(exec_dir, "output.txt"))
    usage = ler_texto(os.path.join(exec_dir, "usage.txt"))
    if output is None or usage is None or gabarito is None:
        registrar("AVISO", f"Arquivo ausente (output/usage/gabarito) em: {exec_dir}")
        return "ausente"
    err = ler_texto(os.path.join(exec_dir, "err.txt"))
    if err is not None and err.strip():
        return "erro_execucao"
    return "ok" if comparar_saida(output, gabarito) else "saida_incorreta"


def carregar_tarefas():
    """Lê Material/tarefas.csv -> {tarefa: {construto, variante}}."""
    tarefas = {}
    texto = ler_texto(TAREFAS_CSV)
    if texto is None:
        registrar("ERRO", f"tarefas.csv não encontrado: {TAREFAS_CSV}")
        return tarefas
    for row in csv.DictReader(texto.splitlines()):
        t = row["tarefa"].strip().lower()
        tarefas[t] = {
            "construto": row["construto"].strip(),
            "variante": row["variante"].strip(),
        }
        if "PLACEHOLDER" in (row["construto"] + row["variante"]).upper():
            registrar("AVISO", f"tarefas.csv ainda com placeholder em: {t}")
    return tarefas


def coletar_rq1():
    """Varre as execuções e classifica o status de cada uma."""
    linhas = []
    for modelo in descobrir_modelos():
        mdir = os.path.join(RESPOSTAS_DIR, modelo)
        for tdir in sorted(os.listdir(mdir)):
            if not re.fullmatch(r"Ex\d+", tdir):
                continue
            tarefa = tdir.lower()
            gabarito = ler_texto(os.path.join(GABARITO_DIR, f"{tarefa}.txt"))
            tcaminho = os.path.join(mdir, tdir)
            for ex in sorted(os.listdir(tcaminho)):
                edir = os.path.join(tcaminho, ex)
                if not os.path.isdir(edir):
                    continue
                linhas.append({
                    "modelo": modelo, "tarefa": tarefa, "exec": ex,
                    "status": avaliar_status(edir, gabarito),
                })
    return linhas


def _resolver_chave(linha, chave, tarefas):
    if chave in ("construto", "variante"):
        return tarefas.get(linha["tarefa"], {}).get(chave, "DESCONHECIDO")
    return linha[chave]


def taxa_por(linhas, chaves, tarefas):
    """Agrega taxa de sucesso (status=='ok') por combinação de `chaves`."""
    grupos = {}
    for ln in linhas:
        k = tuple(_resolver_chave(ln, c, tarefas) for c in chaves)
        g = grupos.setdefault(k, {"sucessos": 0, "total": 0})
        g["total"] += 1
        if ln["status"] == "ok":
            g["sucessos"] += 1
    resultado = []
    for k, g in sorted(grupos.items()):
        linha = dict(zip(chaves, k))
        linha["sucessos"] = g["sucessos"]
        linha["total"] = g["total"]
        linha["taxa"] = round(g["sucessos"] / g["total"], 2) if g["total"] else 0.0
        resultado.append(linha)
    return resultado


def coletar_rq2():
    """Uma linha por (execução × sub-modelo) com os tokens."""
    linhas = []
    for modelo in descobrir_modelos():
        mdir = os.path.join(RESPOSTAS_DIR, modelo)
        for tdir in sorted(os.listdir(mdir)):
            if not re.fullmatch(r"Ex\d+", tdir):
                continue
            tarefa = tdir.lower()
            tcaminho = os.path.join(mdir, tdir)
            for ex in sorted(os.listdir(tcaminho)):
                edir = os.path.join(tcaminho, ex)
                if not os.path.isdir(edir):
                    continue
                texto = ler_texto(os.path.join(edir, "usage.txt"))
                if texto is None:
                    registrar("AVISO", f"usage.txt ausente (RQ2 pulada) em: {edir}")
                    continue
                for e in parse_usage(texto):
                    e.update({"modelo": modelo, "tarefa": tarefa, "exec": ex,
                              "total": e["input"] + e["output"]})
                    linhas.append(e)
    return linhas


def estatisticas(valores):
    """Média, mediana e desvio populacional; vazio -> zeros."""
    if not valores:
        return {"media": 0.0, "mediana": 0.0, "desvio": 0.0}
    return {
        "media": round(statistics.mean(valores), 2),
        "mediana": round(statistics.median(valores), 2),
        "desvio": round(statistics.pstdev(valores), 2),
    }


def agregar_rq2(linhas, chaves):
    """Agrega tokens por `chaves`, somando sub-modelos dentro de cada execução."""
    # 1) soma sub-modelos por execução completa (chaves + exec)
    por_exec = {}
    for ln in linhas:
        k = tuple(ln[c] for c in chaves) + (ln["exec"],)
        acc = por_exec.setdefault(k, {"input": 0, "output": 0, "total": 0})
        for campo in ("input", "output", "total"):
            acc[campo] += ln[campo]
    # 2) agrupa execuções por `chaves`
    grupos = {}
    for k, v in por_exec.items():
        gk = k[:len(chaves)]
        g = grupos.setdefault(gk, {"input": [], "output": [], "total": []})
        for campo in ("input", "output", "total"):
            g[campo].append(v[campo])
    # 3) estatísticas
    resultado = []
    for gk, g in sorted(grupos.items()):
        linha = dict(zip(chaves, gk))
        linha["execucoes"] = len(g["total"])
        for campo in ("input", "output", "total"):
            est = estatisticas(g[campo])
            linha[f"{campo}_media"] = est["media"]
            linha[f"{campo}_mediana"] = est["mediana"]
            linha[f"{campo}_desvio"] = est["desvio"]
        resultado.append(linha)
    return resultado
