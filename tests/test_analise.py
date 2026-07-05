import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import analise


class TestRegistrar(unittest.TestCase):
    def setUp(self):
        analise._AVISOS.clear()

    def test_registrar_acumula(self):
        analise.registrar("AVISO", "algo faltou")
        self.assertEqual(analise._AVISOS, ["[AVISO] algo faltou"])


class TestParseUsage(unittest.TestCase):
    def test_expandir_tokens_k(self):
        self.assertEqual(analise.expandir_tokens("6.3k"), 6300)

    def test_expandir_tokens_inteiro(self):
        self.assertEqual(analise.expandir_tokens("239"), 239)

    def test_parse_usage_dois_submodelos(self):
        texto = (
            "Usage by model:\n"
            "    claude-haiku-4-5:  610 input, 16 output, 0 cache read, 0 cache write ($0.0007)\n"
            "     claude-opus-4-8:  5.7k input, 180 output, 23.5k cache read, 8.3k cache write ($0.1280)\n"
        )
        r = analise.parse_usage(texto)
        self.assertEqual(len(r), 2)
        opus = [x for x in r if x["submodelo"] == "claude-opus-4-8"][0]
        self.assertEqual(opus["input"], 5700)
        self.assertEqual(opus["output"], 180)
        self.assertEqual(opus["cache_read"], 23500)
        self.assertEqual(opus["cache_write"], 8300)


class TestParseUsageTotal(unittest.TestCase):
    def test_com_nome_modelo_e_used(self):
        # o total é o ÚLTIMO número; '5.5' do nome do modelo é ignorado
        self.assertEqual(analise.parse_usage_total("gpt-5.5 · 12.4K used"), 12400)

    def test_nome_modelo_e_sufixo_k(self):
        self.assertEqual(analise.parse_usage_total("gpt 5.5  11.479k"), 11479)

    def test_bare_k(self):
        self.assertEqual(analise.parse_usage_total("11.010k"), 11010)

    def test_ponto_como_milhares(self):
        self.assertEqual(analise.parse_usage_total("5.642"), 5642)
        self.assertEqual(analise.parse_usage_total("19.149"), 19149)

    def test_inteiro_puro(self):
        self.assertEqual(analise.parse_usage_total("7444"), 7444)
        self.assertEqual(analise.parse_usage_total("4818"), 4818)

    def test_sem_numero(self):
        self.assertIsNone(analise.parse_usage_total("nenhum numero aqui"))


class TestComparacao(unittest.TestCase):
    def test_normalizar_remove_espacos_e_linhas(self):
        self.assertEqual(analise.normalizar_saida("  2 \n\n"), "2")

    def test_comparar_texto_igual(self):
        self.assertTrue(analise.comparar_saida("(2, 4, 6)\n", "(2, 4, 6)"))

    def test_comparar_numerico_2_vs_2ponto0(self):
        self.assertTrue(analise.comparar_saida("2.0", "2"))

    def test_comparar_numerico_diferente(self):
        self.assertFalse(analise.comparar_saida("3", "2"))

    def test_comparar_texto_diferente(self):
        self.assertFalse(analise.comparar_saida("[36, 'Norway', 'John']",
                                                "['age', 'country', 'name']"))


class TestDescoberta(unittest.TestCase):
    def setUp(self):
        analise._AVISOS.clear()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _criar_modelo(self, nome, com_ex=True):
        base = os.path.join(self.tmp, nome)
        os.makedirs(os.path.join(base, "Ex1", "1")) if com_ex else os.makedirs(base)

    def test_descobre_modelo_valido(self):
        self._criar_modelo("Claude")
        self.assertEqual(analise.descobrir_modelos(self.tmp), ["Claude"])

    def test_ignora_underscore_e_ponto(self):
        self._criar_modelo("Claude")
        self._criar_modelo("_backup")
        self._criar_modelo(".old")
        self.assertEqual(analise.descobrir_modelos(self.tmp), ["Claude"])

    def test_ignora_lista_negra(self):
        self._criar_modelo("Claude")
        self._criar_modelo("tmp")
        self.assertEqual(analise.descobrir_modelos(self.tmp), ["Claude"])

    def test_ignora_pasta_sem_ex(self):
        self._criar_modelo("Claude")
        self._criar_modelo("Prompt", com_ex=False)
        self.assertEqual(analise.descobrir_modelos(self.tmp), ["Claude"])

    def test_pasta_salvaguarda_sem_ex_e_descartada_com_log(self):
        self._criar_modelo("Claude")
        self._criar_modelo("_backup", com_ex=False)
        resultado = analise.descobrir_modelos(self.tmp)
        self.assertEqual(resultado, ["Claude"])
        self.assertTrue(
            any("_backup" in aviso for aviso in analise._AVISOS),
            f"Esperava aviso de descarte mencionando '_backup', obtido: {analise._AVISOS}",
        )


class TestIterExecucoes(unittest.TestCase):
    def setUp(self):
        analise._AVISOS.clear()
        self.tmp = tempfile.mkdtemp()
        self._orig_respostas_dir = analise.RESPOSTAS_DIR
        analise.RESPOSTAS_DIR = self.tmp

    def tearDown(self):
        analise.RESPOSTAS_DIR = self._orig_respostas_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ignora_arquivo_ex_espurio(self):
        mdir = os.path.join(self.tmp, "Claude")
        os.makedirs(os.path.join(mdir, "Ex1", "1"))
        with open(os.path.join(mdir, "Ex1", "1", "output.txt"), "w", encoding="utf-8") as f:
            f.write("2")
        with open(os.path.join(mdir, "Ex1", "1", "err.txt"), "w", encoding="utf-8") as f:
            f.write("")
        with open(os.path.join(mdir, "Ex1", "1", "usage.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        # Arquivo espúrio (não diretório) chamado Ex2
        with open(os.path.join(mdir, "Ex2"), "w", encoding="utf-8") as f:
            f.write("nao sou um diretorio")

        resultado = list(analise._iter_execucoes(modelos=["Claude"]))
        self.assertEqual(len(resultado), 1)
        modelo, tarefa, edir = resultado[0]
        self.assertEqual(modelo, "Claude")
        self.assertEqual(tarefa, "ex1")


class TestAvaliarStatus(unittest.TestCase):
    def setUp(self):
        analise._AVISOS.clear()
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _exec(self, output=None, err=""):
        d = os.path.join(self.tmp, "1")
        os.makedirs(d)
        if output is not None:
            with open(os.path.join(d, "output.txt"), "w", encoding="utf-8") as f:
                f.write(output)
        with open(os.path.join(d, "err.txt"), "w", encoding="utf-8") as f:
            f.write(err)
        with open(os.path.join(d, "usage.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        return d

    def test_ok(self):
        d = self._exec(output="2")
        self.assertEqual(analise.avaliar_status(d, "2"), "ok")

    def test_saida_incorreta(self):
        d = self._exec(output="3")
        self.assertEqual(analise.avaliar_status(d, "2"), "saida_incorreta")

    def test_erro_execucao(self):
        d = self._exec(output="2", err="Traceback...")
        self.assertEqual(analise.avaliar_status(d, "2"), "erro_execucao")

    def test_ausente_sem_output(self):
        d = self._exec(output=None)
        self.assertEqual(analise.avaliar_status(d, "2"), "ausente")

    def test_ausente_sem_gabarito(self):
        d = self._exec(output="2")
        self.assertEqual(analise.avaliar_status(d, None), "ausente")


class TestAgregacaoRQ1(unittest.TestCase):
    def setUp(self):
        self.tarefas = {
            "ex1": {"construto": "lambda", "variante": "funcional"},
            "ex2": {"construto": "comprehension", "variante": "funcional"},
        }
        self.linhas = [
            {"modelo": "Claude", "tarefa": "ex1", "exec": "1", "status": "ok"},
            {"modelo": "Claude", "tarefa": "ex1", "exec": "2", "status": "saida_incorreta"},
            {"modelo": "Claude", "tarefa": "ex2", "exec": "1", "status": "ok"},
        ]

    def test_taxa_por_tarefa(self):
        r = analise.taxa_por(self.linhas, ["tarefa"], self.tarefas)
        ex1 = [x for x in r if x["tarefa"] == "ex1"][0]
        self.assertEqual(ex1["sucessos"], 1)
        self.assertEqual(ex1["total"], 2)
        self.assertEqual(ex1["taxa"], 0.5)

    def test_taxa_por_construto(self):
        r = analise.taxa_por(self.linhas, ["construto"], self.tarefas)
        self.assertEqual(len(r), 2)
        lam = [x for x in r if x["construto"] == "lambda"][0]
        self.assertEqual(lam["taxa"], 0.5)


class TestRQ2(unittest.TestCase):
    def test_estatisticas(self):
        r = analise.estatisticas([10, 20, 30])
        self.assertEqual(r["media"], 20.0)
        self.assertEqual(r["mediana"], 20.0)
        self.assertEqual(r["desvio"], 8.16)

    def test_estatisticas_vazio(self):
        self.assertEqual(analise.estatisticas([]),
                         {"media": 0.0, "mediana": 0.0, "desvio": 0.0})

    def test_agregar_soma_submodelos_por_execucao(self):
        linhas = [
            {"modelo": "Claude", "tarefa": "ex1", "exec": "1",
             "submodelo": "haiku", "input": 100, "output": 10, "total": 110},
            {"modelo": "Claude", "tarefa": "ex1", "exec": "1",
             "submodelo": "opus", "input": 900, "output": 90, "total": 990},
            {"modelo": "Claude", "tarefa": "ex1", "exec": "2",
             "submodelo": "opus", "input": 1000, "output": 100, "total": 1100},
        ]
        r = analise.agregar_rq2(linhas, ["modelo", "tarefa"])
        self.assertEqual(len(r), 1)
        # execução 1 soma 1000 input; execução 2 soma 1000 input -> média 1000
        self.assertEqual(r[0]["input_media"], 1000.0)
        self.assertEqual(r[0]["total_media"], 1100.0)

    def test_agregar_rq2_por_tarefa_nao_conflate_modelos(self):
        # Duas execuções de MODELOS diferentes com o mesmo id de exec ("1")
        # compartilhando a mesma tarefa não podem ser somadas em uma só observação.
        linhas = [
            {"modelo": "Claude", "tarefa": "ex1", "exec": "1",
             "submodelo": "haiku", "input": 100, "output": 10, "total": 110},
            {"modelo": "Codex", "tarefa": "ex1", "exec": "1",
             "submodelo": "gpt", "input": 900, "output": 90, "total": 990},
        ]
        r = analise.agregar_rq2(linhas, ["tarefa"])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["execucoes"], 2)
        self.assertEqual(r[0]["input_media"], 500.0)

    def test_agregar_total_only_ignora_entrada_saida(self):
        # Codex só reporta total: input/output=None. O total agrega os dois
        # modelos; input/output ficam vazios quando não há dados no grupo.
        linhas = [
            {"modelo": "Codex", "tarefa": "ex1", "exec": "1", "submodelo": "total",
             "input": None, "output": None, "cache_read": None,
             "cache_write": None, "total": 5000},
            {"modelo": "Codex", "tarefa": "ex1", "exec": "2", "submodelo": "total",
             "input": None, "output": None, "cache_read": None,
             "cache_write": None, "total": 7000},
        ]
        r = analise.agregar_rq2(linhas, ["modelo", "tarefa"])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["execucoes"], 2)
        self.assertEqual(r[0]["total_media"], 6000.0)
        # sem breakdown de entrada/saída -> colunas vazias, não zero
        self.assertEqual(r[0]["input_media"], "")
        self.assertEqual(r[0]["output_media"], "")


class TestRQ3(unittest.TestCase):
    def setUp(self):
        analise._AVISOS.clear()

    def test_parse_rq3_completo(self):
        texto = ("## 1. Quando usar funcional\nA\n"
                 "## 2. Quando usar procedural\nB\n"
                 "## 3. Regra\nC\n## 4. Exemplo\nD\n## 5. Risco\nE\n")
        r = analise.parse_rq3(texto)
        self.assertEqual(r[1].strip(), "A")
        self.assertEqual(r[5].strip(), "E")

    def test_parse_rq3_sem_hashes(self):
        texto = "1. Funcional\nA\n2. Proc\nB\n3. R\nC\n4. Ex\nD\n5. Risco\nE\n"
        r = analise.parse_rq3(texto)
        self.assertEqual(r[2].strip(), "B")

    def test_parse_rq3_com_bullet_e_indentacao(self):
        # Formato Codex: seção 1 com prefixo de bullet, demais indentadas
        texto = ("• ## 1. Funcional\n  corpo1\n"
                 "  ## 2. Procedural\n  corpo2\n"
                 "  ## 3. Regra\n  c3\n  ## 4. Ex\n  c4\n  ## 5. Risco\n  c5\n")
        r = analise.parse_rq3(texto)
        self.assertEqual(r[1].strip(), "corpo1")
        self.assertEqual(r[2].strip(), "corpo2")
        self.assertEqual(r[5].strip(), "c5")

    def test_parse_rq3_secao_faltando(self):
        texto = "## 1. F\nA\n## 2. P\nB\n## 3. R\nC\n## 4. E\nD\n"
        r = analise.parse_rq3(texto)
        self.assertIsNone(r[5])

    def test_contar_termos(self):
        texto = "Legibilidade importa. O código legível vence. Estilo funcional."
        r = analise.contar_termos(texto)
        self.assertEqual(r["legibilidade"], 2)
        self.assertEqual(r["funcional"], 1)
        self.assertEqual(r["procedural"], 0)


class TestEscrita(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_escrever_csv(self):
        caminho = os.path.join(self.tmp, "x.csv")
        analise.escrever_csv(caminho, [{"a": 1, "b": 2}, {"a": 3, "b": 4}])
        with open(caminho, encoding="utf-8") as f:
            conteudo = f.read()
        self.assertIn("a,b", conteudo)
        self.assertIn("3,4", conteudo)

    def test_comparativo_marca_secao_ausente(self):
        caminho = os.path.join(self.tmp, "c.md")
        dados = {"Claude": {"secoes": {1: "texto1", 2: None, 3: None,
                                       4: None, 5: None}, "termos": {}}}
        analise.escrever_rq3_comparativo(caminho, dados)
        with open(caminho, encoding="utf-8") as f:
            conteudo = f.read()
        self.assertIn("texto1", conteudo)
        self.assertIn("*(seção ausente)*", conteudo)


if __name__ == "__main__":
    unittest.main()
