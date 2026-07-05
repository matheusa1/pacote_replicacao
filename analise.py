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
