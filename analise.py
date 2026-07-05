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
