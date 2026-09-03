"""
Testes da tabela que junta as duas energias por comercializador.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dados  # noqa: E402


def tabela(linhas):
    """Uma simulacao de mentira, so com as colunas que o juntar_ele_gn usa."""
    return pd.DataFrame(
        [
            {
                "marca": marca,
                "proposta": proposta,
                "total": total,
                "media_mensal": total,
                "preco_kwh": preco,
                "termo_fixo": 0.5,
            }
            for marca, proposta, total, preco in linhas
        ]
    )


class TestJuntarEleGn(unittest.TestCase):
    def test_soma_as_duas_energias(self):
        ele = tabela([("EDP", "Luz", 59.80, 0.1337)])
        gn = tabela([("EDP", "Gás", 18.82, 0.0901)])
        d = dados.juntar_ele_gn(ele, gn)
        self.assertEqual(len(d), 1)
        linha = d.iloc[0]
        self.assertAlmostEqual(linha["total_ele"], 59.80)
        self.assertAlmostEqual(linha["total_gn"], 18.82)
        self.assertAlmostEqual(linha["total"], 78.62)

    def test_guarda_o_preco_por_kwh_de_cada_energia(self):
        ele = tabela([("EDP", "Luz", 59.80, 0.1337)])
        gn = tabela([("EDP", "Gás", 18.82, 0.0901)])
        linha = dados.juntar_ele_gn(ele, gn).iloc[0]
        self.assertAlmostEqual(linha["preco_kwh_ele"], 0.1337)
        self.assertAlmostEqual(linha["preco_kwh_gn"], 0.0901)
        self.assertEqual(linha["proposta_ele"], "Luz")
        self.assertEqual(linha["proposta_gn"], "Gás")

    def test_uma_linha_por_comercializador(self):
        ele = tabela(
            [("EDP", "Luz cara", 70.0, 0.16), ("EDP", "Luz barata", 59.80, 0.1337)]
        )
        gn = tabela([("EDP", "Gás", 18.82, 0.0901)])
        d = dados.juntar_ele_gn(ele, gn)
        self.assertEqual(len(d), 1)
        # De cada lado fica a proposta mais barata.
        self.assertEqual(d.iloc[0]["proposta_ele"], "Luz barata")

    def test_so_entra_quem_tem_as_duas(self):
        """Somar uma fatura a zero punha um vendedor de uma energia em primeiro."""
        ele = tabela(
            [("EDP", "Luz", 59.80, 0.1337), ("SóLuz", "Luz", 40.0, 0.10)]
        )
        gn = tabela([("EDP", "Gás", 18.82, 0.0901), ("SóGás", "Gás", 15.0, 0.08)])
        d = dados.juntar_ele_gn(ele, gn)
        self.assertEqual(list(d["marca"]), ["EDP"])

    def test_ordena_pelo_total(self):
        ele = tabela([("A", "L", 60.0, 0.13), ("B", "L", 50.0, 0.12)])
        gn = tabela([("A", "G", 10.0, 0.09), ("B", "G", 30.0, 0.11)])
        d = dados.juntar_ele_gn(ele, gn)
        # A soma 70, B soma 80.
        self.assertEqual(list(d["marca"]), ["A", "B"])

    def test_tem_as_colunas_que_o_podio_e_o_grafico_pedem(self):
        ele = tabela([("EDP", "Luz", 59.80, 0.1337)])
        gn = tabela([("EDP", "Gás", 18.82, 0.0901)])
        d = dados.juntar_ele_gn(ele, gn)
        for coluna in ("marca", "proposta", "total", "media_mensal"):
            self.assertIn(coluna, d.columns, msg=coluna)

    def test_sem_sobreposicao_devolve_vazio(self):
        ele = tabela([("SóLuz", "Luz", 40.0, 0.10)])
        gn = tabela([("SóGás", "Gás", 15.0, 0.08)])
        self.assertTrue(dados.juntar_ele_gn(ele, gn).empty)

    def test_lado_vazio_devolve_vazio(self):
        ele = tabela([("EDP", "Luz", 59.80, 0.1337)])
        self.assertTrue(dados.juntar_ele_gn(ele, pd.DataFrame()).empty)
        self.assertTrue(dados.juntar_ele_gn(pd.DataFrame(), ele).empty)
        self.assertTrue(dados.juntar_ele_gn(None, ele).empty)


if __name__ == "__main__":
    unittest.main()
