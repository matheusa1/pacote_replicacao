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
    """Extrai tokens por sub-modelo de um usage.txt (formato Claude Code)."""
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


_LINHA_USAGE_GEMINI = re.compile(
    r"Thought for\s+\d+(?:\.\d+)?s,\s*([\d.]+k?)\s*tokens", re.IGNORECASE)


def parse_usage_gemini(texto):
    """Soma os tokens de cada bloco 'Thought for Ns, M tokens' (formato Gemini).

    Um usage.txt do Gemini lista um ou mais blocos de raciocínio; o total da
    execução é a soma de todos eles, não apenas o último (ao contrário do
    formato Codex, que reporta um único total já consolidado).
    Retorna None se nenhum bloco for encontrado.
    """
    tokens = [expandir_tokens(m.group(1)) for m in _LINHA_USAGE_GEMINI.finditer(texto)]
    if not tokens:
        return None
    return sum(tokens)


_NUM_USAGE_TOTAL = re.compile(r"(\d+(?:\.\d+)?)\s*([kK])?")


def parse_usage_total(texto):
    """Extrai um único total de tokens de formatos alternativos (ex.: Codex).

    O total é sempre o último número da linha (o nome/versão do modelo, ex.
    'gpt-5.5', vem antes). Convenção 'ponto = milhares': '12.4K'->12400,
    '11.479k'->11479, '5.642'->5642, '7444'->7444, '4818'->4818.
    Retorna None se nenhum número for encontrado.
    """
    matches = [(m.group(1), m.group(2)) for m in _NUM_USAGE_TOTAL.finditer(texto)]
    if not matches:
        return None
    num, suf = matches[-1]
    if suf or "." in num:
        return int(round(float(num) * 1000))
    return int(num)


def remover_wrapper_numpy(texto):
    """Remove o wrapper 'array(...)' do repr do NumPy, preservando o conteúdo
    interno (ex.: 'array([2, 3])' -> '[2, 3]'), recursivamente para casos
    aninhados. Sem isso, uma saída correta como '[array([2, 3]), array([4,
    5])]' seria comparada literalmente contra o gabarito '[[2, 3], [4, 5]]'
    e marcada como incorreta.
    """
    marcador = "array("
    resultado = []
    i, n = 0, len(texto)
    while i < n:
        if texto.startswith(marcador, i):
            i += len(marcador)
            profundidade = 1
            inicio = i
            while i < n and profundidade > 0:
                if texto[i] == "(":
                    profundidade += 1
                elif texto[i] == ")":
                    profundidade -= 1
                i += 1
            interior = texto[inicio:i - 1]
            resultado.append(remover_wrapper_numpy(interior))
        else:
            resultado.append(texto[i])
            i += 1
    return "".join(resultado)


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
    ns = normalizar_saida(remover_wrapper_numpy(saida))
    ng = normalizar_saida(remover_wrapper_numpy(gabarito))
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
    """Lê Material/tarefas.csv -> {(modelo, tarefa): {construto, variante}}.

    Cada modelo recebeu uma variante diferente (funcional/procedural) do
    mesmo exercício, então construto/variante são chaveados por modelo+tarefa.
    """
    tarefas = {}
    texto = ler_texto(TAREFAS_CSV)
    if texto is None:
        registrar("ERRO", f"tarefas.csv não encontrado: {TAREFAS_CSV}")
        return tarefas
    for row in csv.DictReader(texto.splitlines()):
        m = row["modelo"].strip()
        t = row["tarefa"].strip().lower()
        tarefas[(m, t)] = {
            "construto": row["construto"].strip(),
            "variante": row["variante"].strip(),
        }
        if "PLACEHOLDER" in (row["construto"] + row["variante"]).upper():
            registrar("AVISO", f"tarefas.csv ainda com placeholder em: {m}/{t}")
    return tarefas


def _iter_execucoes(modelos=None):
    """Yields (modelo, tarefa, exec_dir) for every execution directory."""
    for modelo in (modelos if modelos is not None else descobrir_modelos()):
        mdir = os.path.join(RESPOSTAS_DIR, modelo)
        for tdir in sorted(os.listdir(mdir)):
            tcaminho = os.path.join(mdir, tdir)
            if not re.fullmatch(r"Ex\d+", tdir) or not os.path.isdir(tcaminho):
                continue
            for ex in sorted(os.listdir(tcaminho)):
                edir = os.path.join(tcaminho, ex)
                if not os.path.isdir(edir):
                    continue
                yield modelo, tdir.lower(), edir


def coletar_rq1(modelos=None):
    """Varre as execuções e classifica o status de cada uma.

    O gabarito é buscado por (modelo, tarefa): cada modelo recebeu uma
    variante diferente do mesmo exercício, então a resposta certa também
    varia por modelo.
    """
    linhas = []
    gabaritos = {}
    for modelo, tarefa, edir in _iter_execucoes(modelos):
        chave = (modelo, tarefa)
        if chave not in gabaritos:
            gabaritos[chave] = ler_texto(
                os.path.join(GABARITO_DIR, modelo, f"{tarefa}.txt"))
        gabarito = gabaritos[chave]
        ex = os.path.basename(edir)
        linhas.append({
            "modelo": modelo, "tarefa": tarefa, "exec": ex,
            "status": avaliar_status(edir, gabarito),
        })
    return linhas


def _resolver_chave(linha, chave, tarefas):
    if chave in ("construto", "variante"):
        return tarefas.get((linha["modelo"], linha["tarefa"]), {}).get(chave, "DESCONHECIDO")
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


def coletar_rq2(modelos=None):
    """Uma linha por (execução × sub-modelo) com os tokens."""
    linhas = []
    for modelo, tarefa, edir in _iter_execucoes(modelos):
        ex = os.path.basename(edir)
        texto = ler_texto(os.path.join(edir, "usage.txt"))
        if texto is None:
            registrar("AVISO", f"usage.txt ausente (RQ2 pulada) em: {edir}")
            continue
        entradas = parse_usage(texto)
        if entradas:
            for e in entradas:
                e.update({"modelo": modelo, "tarefa": tarefa, "exec": ex,
                          "total": e["input"] + e["output"]})
                linhas.append(e)
            continue
        # Formatos alternativos com total único (sem breakdown entrada/saída,
        # que fica vazio/None): Gemini soma os blocos "Thought for..."; Codex
        # reporta um único total já consolidado.
        total = parse_usage_gemini(texto)
        if total is None:
            total = parse_usage_total(texto)
        if total is None:
            registrar("AVISO", f"usage.txt não reconhecido (RQ2 pulada) em: {edir}")
            continue
        linhas.append({
            "submodelo": "total", "input": None, "output": None,
            "cache_read": None, "cache_write": None,
            "modelo": modelo, "tarefa": tarefa, "exec": ex, "total": total,
        })
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
    """Agrega tokens por `chaves`, somando sub-modelos dentro de cada execução.

    Campos ausentes (None) — ex.: entrada/saída do Codex, que só reporta total —
    são ignorados: a execução não contribui para a estatística daquele campo, e
    um grupo sem nenhum dado de um campo tem suas colunas deixadas vazias.
    """
    # 1) soma sub-modelos por execução completa (identidade: modelo+tarefa+exec).
    #    Um campo permanece None enquanto nenhum sub-modelo tiver valor para ele.
    por_exec = {}
    for ln in linhas:
        k = (ln["modelo"], ln["tarefa"], ln["exec"])
        acc = por_exec.setdefault(k, {"input": None, "output": None, "total": None})
        for campo in ("input", "output", "total"):
            v = ln[campo]
            if v is not None:
                acc[campo] = (acc[campo] or 0) + v
    # 2) agrupa execuções por `chaves` (derivadas dos campos da própria execução)
    exec_campos = {}
    for ln in linhas:
        exec_campos.setdefault((ln["modelo"], ln["tarefa"], ln["exec"]), ln)
    grupos = {}
    execs_por_grupo = {}
    for k, v in por_exec.items():
        ln = exec_campos[k]
        gk = tuple(ln[c] for c in chaves)
        g = grupos.setdefault(gk, {"input": [], "output": [], "total": []})
        execs_por_grupo[gk] = execs_por_grupo.get(gk, 0) + 1
        for campo in ("input", "output", "total"):
            if v[campo] is not None:
                g[campo].append(v[campo])
    # 3) estatísticas (campo sem dados -> colunas vazias)
    resultado = []
    for gk, g in sorted(grupos.items()):
        linha = dict(zip(chaves, gk))
        linha["execucoes"] = execs_por_grupo[gk]
        for campo in ("input", "output", "total"):
            if g[campo]:
                est = estatisticas(g[campo])
                linha[f"{campo}_media"] = est["media"]
                linha[f"{campo}_mediana"] = est["mediana"]
                linha[f"{campo}_desvio"] = est["desvio"]
            else:
                linha[f"{campo}_media"] = ""
                linha[f"{campo}_mediana"] = ""
                linha[f"{campo}_desvio"] = ""
        resultado.append(linha)
    return resultado


_ANCORA_RQ3 = re.compile(r"^\s*(?:[•\-\*]\s*)?(?:#+\s*)?([1-5])\.\s*(.*)$", re.MULTILINE)


def parse_rq3(texto):
    """Divide o RQ3.txt nas seções 1..5; ausentes -> None."""
    secoes = {i: None for i in range(1, 6)}
    marcas = [(int(m.group(1)), m.start(), m.end()) for m in _ANCORA_RQ3.finditer(texto)]
    for idx, (num, _, fim) in enumerate(marcas):
        inicio_corpo = fim
        fim_corpo = marcas[idx + 1][1] if idx + 1 < len(marcas) else len(texto)
        secoes[num] = texto[inicio_corpo:fim_corpo].strip()
    return secoes


def contar_termos(texto):
    """Conta menções (case-insensitive) por termo canônico, somando variações."""
    baixo = texto.lower()
    contagem = {}
    for canonico, variacoes in TERMOS_RQ3.items():
        total = 0
        for v in variacoes:
            total += len(re.findall(r"\b" + re.escape(v.lower()) + r"\b", baixo))
        contagem[canonico] = total
    return contagem


def _achar_rq3(mdir):
    """Acha o arquivo de resposta RQ3 numa pasta-modelo (case-insensitive)."""
    if not os.path.isdir(mdir):
        return None
    for nome in sorted(os.listdir(mdir)):
        if nome.lower() == "rq3.txt":
            return os.path.join(mdir, nome)
    return None


def coletar_rq3(modelos=None):
    """Coleta seções e termos por modelo; loga seções ausentes."""
    dados = {}
    for modelo in (modelos if modelos is not None else descobrir_modelos()):
        caminho = _achar_rq3(os.path.join(RESPOSTAS_DIR, modelo))
        texto = ler_texto(caminho) if caminho else None
        if texto is None:
            registrar("AVISO", f"RQ3 (rq3.txt) ausente para o modelo: {modelo}")
            continue
        secoes = parse_rq3(texto)
        faltando = [str(n) for n, v in secoes.items() if v is None]
        if faltando:
            registrar("AVISO", f"RQ3 [{modelo}]: seções ausentes: {', '.join(faltando)}")
        dados[modelo] = {"secoes": secoes, "termos": contar_termos(texto)}
    return dados


def escrever_csv(caminho, linhas):
    """Escreve uma lista de dicts como CSV utf-8."""
    if not linhas:
        registrar("AVISO", f"Sem dados para {caminho} (CSV não gerado).")
        return
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)


def escrever_rq3_comparativo(caminho, dados):
    """Gera .md comparando as 5 seções da RQ3 entre modelos."""
    titulos = {
        1: "Quando usar funcional", 2: "Quando usar procedural",
        3: "Regra prática de decisão", 4: "Exemplo mínimo",
        5: "Maior risco/armadilha",
    }
    partes = ["# RQ3 — Comparativo entre modelos\n"]
    for num in range(1, 6):
        partes.append(f"\n## Seção {num} — {titulos[num]}\n")
        for modelo, d in sorted(dados.items()):
            corpo = d["secoes"].get(num)
            partes.append(f"\n### {modelo}\n")
            partes.append(f"\n{corpo if corpo else '*(seção ausente)*'}\n")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("".join(partes))


def escrever_avisos(caminho):
    """Persiste todos os avisos/erros acumulados."""
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(_AVISOS) + ("\n" if _AVISOS else ""))


def main():
    os.makedirs(RESULTADOS_DIR, exist_ok=True)
    tarefas = carregar_tarefas()
    modelos = descobrir_modelos()

    # RQ1
    rq1 = coletar_rq1(modelos)
    escrever_csv(os.path.join(RESULTADOS_DIR, "rq1_execucoes.csv"), rq1)
    for nome, chaves in [
        ("rq1_por_modelo", ["modelo"]),
        ("rq1_por_tarefa", ["tarefa"]),
        ("rq1_por_construto", ["construto"]),
        ("rq1_por_variante", ["variante"]),
        ("rq1_por_modelo_tarefa", ["modelo", "tarefa"]),
    ]:
        escrever_csv(os.path.join(RESULTADOS_DIR, f"{nome}.csv"),
                     taxa_por(rq1, chaves, tarefas))

    # RQ2
    rq2 = coletar_rq2(modelos)
    escrever_csv(os.path.join(RESULTADOS_DIR, "rq2_execucoes.csv"), rq2)
    escrever_csv(os.path.join(RESULTADOS_DIR, "rq2_por_modelo_tarefa.csv"),
                 agregar_rq2(rq2, ["modelo", "tarefa"]))
    escrever_csv(os.path.join(RESULTADOS_DIR, "rq2_por_tarefa.csv"),
                 agregar_rq2(rq2, ["tarefa"]))

    # RQ3
    rq3 = coletar_rq3(modelos)
    escrever_rq3_comparativo(os.path.join(RESULTADOS_DIR, "rq3_comparativo.md"), rq3)
    termos = [{"modelo": m, **rq3[m]["termos"]} for m in sorted(rq3)]
    escrever_csv(os.path.join(RESULTADOS_DIR, "rq3_termos.csv"), termos)

    # Resumo + log
    print(f"\nModelos: {modelos} | execuções RQ1: {len(rq1)} | "
          f"linhas RQ2: {len(rq2)} | avisos: {len(_AVISOS)}")
    escrever_avisos(os.path.join(RESULTADOS_DIR, "avisos.log"))


if __name__ == "__main__":
    main()
