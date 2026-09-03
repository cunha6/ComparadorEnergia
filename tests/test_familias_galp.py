"""
Testes da separacao das familias de ofertas da Galp.

A ERSE publica todas as ofertas da Galp com o mesmo codigo de comercializador.
Sem as separar, a coluna Comercializador diz "Galp" em todas e o Plano COMBINA
fica escondido por tras do Casa & Estrada nas tabelas, que guardam so a
proposta mais barata de cada comercializador.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dados  # noqa: E402


class TestFamiliaGalp(unittest.TestCase):
    def test_plano_combina(self):
        nomes = [
            "Plano COMBINA Eletricidade Verde",
            "Plano COMBINA Dual (DD)",
            "Plano COMBINA GásNatural + NOS",
            "Plano COMBINA Dual + SOLAR 360Casa",
        ]
        for nome in nomes:
            self.assertEqual(dados.familia_galp(nome), "Galp COMBINA", msg=nome)

    def test_casa_e_estrada(self):
        nomes = [
            "Casa & Estrada Eletricidade Verde & Combustível",
            "Casa & Estrada Gás Natural & Combustível (DD)",
            "Casa & Estrada  Eletricidade Verde & Combustível + 2 serviços",
        ]
        for nome in nomes:
            self.assertEqual(dados.familia_galp(nome), "Galp Casa & Estrada", msg=nome)

    def test_negocios(self):
        nomes = [
            "Galp Negócios Eletricidade Verde",
            "Galp Negócios Gas Natural",
            "Plano Negócios Plus Gás Natural - Galp 360 Assist+",
        ]
        for nome in nomes:
            self.assertEqual(dados.familia_galp(nome), "Galp Negócios", msg=nome)

    def test_nome_desconhecido_fica_sem_familia(self):
        self.assertIsNone(dados.familia_galp("Tarifa qualquer"))
        self.assertIsNone(dados.familia_galp(""))
        self.assertIsNone(dados.familia_galp(None))

    def test_nao_depende_de_maiusculas(self):
        self.assertEqual(
            dados.familia_galp("PLANO COMBINA ELETRICIDADE VERDE"), "Galp COMBINA"
        )
        self.assertEqual(
            dados.familia_galp("casa & estrada gás natural"), "Galp Casa & Estrada"
        )

    def test_combina_e_casa_estrada_nao_se_confundem(self):
        """As duas familias tem de dar marcas diferentes, que e o objetivo."""
        combina = dados.familia_galp("Plano COMBINA Dual")
        casa = dados.familia_galp("Casa & Estrada Gás Natural & Combustível")
        self.assertNotEqual(combina, casa)

    def test_familias_estao_nos_principais(self):
        """Sem isto deixavam de vir pre-selecionadas nos filtros."""
        for familia in ("Galp COMBINA", "Galp Casa & Estrada", "Galp Negócios"):
            self.assertIn(familia, dados.PRINCIPAIS, msg=familia)


if __name__ == "__main__":
    unittest.main()
