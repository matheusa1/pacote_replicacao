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
        tem_ex = any(re.fullmatch(r"Ex\d+", x) and
                     os.path.isdir(os.path.join(caminho, x))
                     for x in os.listdir(caminho))
        if not tem_ex:
            continue
        if nome[0] in "._" or nome.lower() in IGNORAR_MODELOS:
            registrar("AVISO", f"Pasta ignorada na descoberta de modelos: {nome}")
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
