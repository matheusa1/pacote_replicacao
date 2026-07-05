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


if __name__ == "__main__":
    unittest.main()
