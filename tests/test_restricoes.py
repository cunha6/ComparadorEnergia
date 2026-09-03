"""
Testes do filtro das ofertas com condicoes de acesso.

O CSV da ERSE marca em FiltroRestricoes as ofertas reservadas a quem pertence
a alguma coisa, e explica em TxTRestricoesAdic qual e a condicao. Sao muitas
das mais baratas da tabela, por isso vale a pena poder tira-las.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dados  # noqa: E402


def linhas():
    return pd.DataFrame(
        [
            {
                "marca": "Goldenergy",
                "proposta": "Monoeletrico ACP",
                "segmento": "Dom",
                "com_restricoes": True,
                "restricoes": "Para associados ACP",
                "indexada": False,
                "so_novos_clientes": False,
                "renovavel": True,
                "data_ini": pd.NaT,
                "data_fim": pd.NaT,
            },
            {
                "marca": "EDP",
                "proposta": "Eletricidade DD+FE",
                "segmento": "Dom",
                "com_restricoes": False,
                "restricoes": "",
                "indexada": False,
                "so_novos_clientes": False,
                "renovavel": True,
                "data_ini": pd.NaT,
                "data_fim": pd.NaT,
            },
        ]
    )


def filtra(**extra):
    base = dict(
        segmento="Todos",
        comercializadores=None,
        so_ativas=False,
        sem_indexadas=False,
        sem_so_novos_clientes=False,
        so_renovavel=False,
        dia=dt.date(2026, 9, 3),
    )
    base.update(extra)
    return dados._aplicar_filtros(linhas(), **base)


class TestFiltroRestricoes(unittest.TestCase):
    def test_por_omissao_mostra_tudo(self):
        self.assertEqual(len(filtra()), 2)

    def test_exclui_as_que_tem_condicoes(self):
        r = filtra(sem_restricoes=True)
        self.assertEqual(list(r["marca"]), ["EDP"])

    def test_o_texto_da_condicao_fica_disponivel(self):
        r = filtra()
        acp = r[r["marca"] == "Goldenergy"].iloc[0]
        self.assertEqual(acp["restricoes"], "Para associados ACP")

    def test_nao_estraga_os_outros_filtros(self):
        r = filtra(sem_restricoes=True, comercializadores=["Goldenergy"])
        self.assertTrue(r.empty)


class TestColunasLidas(unittest.TestCase):
    """As duas colunas do CSV tem de estar no mapa, senao nada disto existe."""

    def test_colunas_no_mapa(self):
        self.assertEqual(
            dados.COLUNAS_CONDICOES.get("FiltroRestrições"), "com_restricoes"
        )
        self.assertEqual(
            dados.COLUNAS_CONDICOES.get("TxTRestricoesAdic"), "restricoes"
        )


if __name__ == "__main__":
    unittest.main()
