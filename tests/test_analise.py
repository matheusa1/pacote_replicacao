import os
import sys
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


if __name__ == "__main__":
    unittest.main()
