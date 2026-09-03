"""
Testes das regras do Galp COMBINA.

Nenhum dos dois beneficios sai da fatura de energia. A percentagem do
Continente incide sobre as compras do mes no supermercado e volta em saldo no
cartao; o desconto da Galp incide sobre os litros de combustivel.

Usa so o unittest da biblioteca padrao, para nao acrescentar dependencias ao
projeto. Correr da raiz do repositorio com:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dados  # noqa: E402


class TestNivel(unittest.TestCase):
    """A matriz completa dos niveis, linha a linha."""

    def nivel(self, ele: bool, gas: bool, nos: bool) -> dict:
        return dados.nivel_combina(ele, gas, nos)

    def test_0_sem_servicos(self):
        r = self.nivel(False, False, False)
        self.assertEqual(r["nivel"], 0)
        self.assertEqual(r["n_servicos"], 0)
        self.assertFalse(r["elegivel"])
        self.assertEqual(r["continente_percentagem"], 0.0)
        self.assertEqual(r["galp_por_litro"], 0.0)

    def test_1_so_eletricidade(self):
        r = self.nivel(True, False, False)
        self.assertEqual(r["nivel"], 1)
        self.assertEqual(r["continente_percentagem"], 2.0)
        self.assertEqual(r["galp_por_litro"], 0.20)

    def test_2_so_gas(self):
        r = self.nivel(False, True, False)
        self.assertEqual(r["nivel"], 1)
        self.assertEqual(r["continente_percentagem"], 2.0)

    def test_3_so_nos(self):
        r = self.nivel(False, False, True)
        self.assertEqual(r["nivel"], 1)
        self.assertEqual(r["continente_percentagem"], 2.0)

    def test_4_eletricidade_e_gas(self):
        r = self.nivel(True, True, False)
        self.assertEqual(r["nivel"], 2)
        self.assertEqual(r["continente_percentagem"], 5.0)
        self.assertEqual(r["galp_por_litro"], 0.25)

    def test_5_eletricidade_e_nos(self):
        r = self.nivel(True, False, True)
        self.assertEqual(r["nivel"], 2)
        self.assertEqual(r["continente_percentagem"], 5.0)

    def test_6_gas_e_nos(self):
        r = self.nivel(False, True, True)
        self.assertEqual(r["nivel"], 2)
        self.assertEqual(r["continente_percentagem"], 5.0)

    def test_7_os_tres(self):
        r = self.nivel(True, True, True)
        self.assertEqual(r["nivel"], 3)
        self.assertEqual(r["continente_percentagem"], 10.0)
        self.assertEqual(r["galp_por_litro"], 0.30)

    def test_nunca_passa_do_nivel_3(self):
        self.assertEqual(max(dados.COMBINA_NIVEIS), 3)
        self.assertEqual(self.nivel(True, True, True)["nivel"], 3)

    def test_servicos_devolvidos_como_foram_dados(self):
        r = self.nivel(True, False, True)
        self.assertEqual(
            r["servicos"], {"eletricidade": True, "gas": False, "nos": True}
        )

    def test_local_diferente_nao_soma_gas_a_eletricidade(self):
        """So contam juntos se forem do mesmo local de consumo."""
        r = dados.nivel_combina(True, True, False, mesmo_local=False)
        self.assertEqual(r["nivel"], 1)
        self.assertTrue(r["servicos"]["gas"])

    def test_local_diferente_sem_eletricidade_o_gas_conta(self):
        r = dados.nivel_combina(False, True, True, mesmo_local=False)
        self.assertEqual(r["nivel"], 2)


class TestContinente(unittest.TestCase):
    """A percentagem incide sobre as compras do supermercado."""

    def test_exemplo_do_cliente(self):
        """COMBINA 1 com 300 EUR de compras da 6 EUR de saldo no cartao."""
        r = dados.beneficio_continente(300.0, 2.0)
        self.assertAlmostEqual(r["beneficio"], 6.0)
        self.assertAlmostEqual(r["elegivel"], 300.0)
        self.assertFalse(r["limitado"])

    def test_as_tres_percentagens_com_300_euros(self):
        esperado = {1: 6.0, 2: 15.0, 3: 30.0}
        for nivel, saldo in esperado.items():
            percentagem = dados.COMBINA_NIVEIS[nivel]["continente"]
            self.assertAlmostEqual(
                dados.beneficio_continente(300.0, percentagem)["beneficio"],
                saldo,
                msg=f"COMBINA {nivel}",
            )

    def test_limite_dos_450_euros(self):
        r = dados.beneficio_continente(500.0, 10.0)
        self.assertAlmostEqual(r["elegivel"], 450.0)
        self.assertAlmostEqual(r["beneficio"], 45.0)
        self.assertTrue(r["limitado"])

    def test_limite_nao_marca_abaixo_do_teto(self):
        r = dados.beneficio_continente(100.0, 10.0)
        self.assertAlmostEqual(r["beneficio"], 10.0)
        self.assertFalse(r["limitado"])

    def test_tetos_mensais_por_nivel(self):
        esperado = {1: 9.0, 2: 22.50, 3: 45.0}
        for nivel, maximo in esperado.items():
            percentagem = dados.COMBINA_NIVEIS[nivel]["continente"]
            r = dados.beneficio_continente(10_000.0, percentagem)
            self.assertAlmostEqual(r["beneficio"], maximo, msg=f"COMBINA {nivel}")

    def test_a_fatura_de_energia_nao_entra_na_conta(self):
        """O erro que isto corrige: a percentagem era sobre a fatura."""
        magra = dados.simular_combina(
            eletricidade=True, compras=300.0, fatura_ele=40.0, energia_ele=25.0
        )
        gorda = dados.simular_combina(
            eletricidade=True, compras=300.0, fatura_ele=200.0, energia_ele=150.0
        )
        self.assertAlmostEqual(magra["poupanca_continente"], 6.0)
        self.assertAlmostEqual(gorda["poupanca_continente"], 6.0)


class TestGalp(unittest.TestCase):
    def test_cento_e_cinquenta_litros(self):
        r = dados.beneficio_galp(150.0, 0.30)
        self.assertAlmostEqual(r["beneficio"], 45.0)
        self.assertFalse(r["limitado"])

    def test_limite_dos_250_litros(self):
        r = dados.beneficio_galp(300.0, 0.30)
        self.assertAlmostEqual(r["litros"], 300.0)
        self.assertAlmostEqual(r["elegiveis"], 250.0)
        self.assertAlmostEqual(r["beneficio"], 75.0)
        self.assertTrue(r["limitado"])

    def test_quarenta_litros_por_nivel(self):
        """O valor que vem por omissao no simulador."""
        esperado = {1: 8.0, 2: 10.0, 3: 12.0}
        for nivel, valor in esperado.items():
            por_litro = dados.COMBINA_NIVEIS[nivel]["galp"]
            self.assertAlmostEqual(
                dados.beneficio_galp(40.0, por_litro)["beneficio"],
                valor,
                msg=f"COMBINA {nivel}",
            )

    def test_tetos_mensais_por_nivel(self):
        esperado = {1: 50.0, 2: 62.50, 3: 75.0}
        for nivel, maximo in esperado.items():
            por_litro = dados.COMBINA_NIVEIS[nivel]["galp"]
            self.assertAlmostEqual(
                dados.beneficio_galp(1000.0, por_litro)["beneficio"],
                maximo,
                msg=f"COMBINA {nivel}",
            )

    def test_zero_litros_nao_tira_o_nivel(self):
        r = dados.simular_combina(
            eletricidade=True,
            nos=True,
            compras=300.0,
            fatura_ele=62.65,
            energia_ele=46.83,
            kwh_ele=300.0,
            litros=0.0,
        )
        self.assertEqual(r["nivel"], 2)
        self.assertAlmostEqual(r["poupanca_galp"], 0.0)
        self.assertTrue(r["elegivel"])
        # O saldo do Continente nao depende dos litros.
        self.assertAlmostEqual(r["poupanca_continente"], 15.0)


class TestCenarios(unittest.TestCase):
    """Os valores por omissao do simulador: 300 EUR de compras e 40 L."""

    def cenario(self, **extra):
        base = dict(
            compras=300.0,
            litros=40.0,
            fatura_ele=62.65,
            energia_ele=46.83,
            kwh_ele=300.0,
        )
        base.update(extra)
        return dados.simular_combina(**base)

    def test_combina_1_so_eletricidade(self):
        r = self.cenario(eletricidade=True)
        self.assertEqual(r["nivel"], 1)
        self.assertAlmostEqual(r["poupanca_continente"], 6.0)
        self.assertAlmostEqual(r["poupanca_galp"], 8.0)
        self.assertAlmostEqual(r["poupanca_total"], 14.0)

    def test_combina_2_eletricidade_e_nos(self):
        r = self.cenario(eletricidade=True, nos=True)
        self.assertEqual(r["nivel"], 2)
        self.assertAlmostEqual(r["poupanca_continente"], 15.0)
        self.assertAlmostEqual(r["poupanca_galp"], 10.0)
        self.assertAlmostEqual(r["poupanca_total"], 25.0)

    def test_combina_3_os_tres_servicos(self):
        r = self.cenario(eletricidade=True, gas=True, nos=True)
        self.assertEqual(r["nivel"], 3)
        self.assertAlmostEqual(r["poupanca_continente"], 30.0)
        self.assertAlmostEqual(r["poupanca_galp"], 12.0)
        self.assertAlmostEqual(r["poupanca_total"], 42.0)

    def test_valor_final_desconta_as_duas_poupancas(self):
        r = self.cenario(eletricidade=True, nos=True)
        self.assertAlmostEqual(r["valor_final"], 62.65 - 15.0 - 10.0)
        self.assertFalse(r["valor_final_negativo"])

    def test_valor_final_pode_ficar_negativo(self):
        r = self.cenario(
            eletricidade=True, gas=True, nos=True, compras=450.0, litros=250.0
        )
        # 45 EUR de cartao mais 75 EUR de combustivel contra 62,65 de fatura.
        self.assertAlmostEqual(r["poupanca_total"], 120.0)
        self.assertLess(r["valor_final"], 0)
        self.assertTrue(r["valor_final_negativo"])

    def test_soma_as_duas_energias(self):
        r = self.cenario(
            eletricidade=True, gas=True, fatura_gas=18.71, energia_gas=13.08
        )
        self.assertAlmostEqual(r["fatura_energia"], 62.65 + 18.71)
        self.assertAlmostEqual(r["custo_energia"], 46.83 + 13.08)

    def test_sem_servicos_nao_ha_beneficios(self):
        r = dados.simular_combina(compras=300.0, litros=40.0)
        self.assertFalse(r["elegivel"])
        self.assertEqual(r["nivel"], 0)
        self.assertAlmostEqual(r["poupanca_continente"], 0.0)
        self.assertAlmostEqual(r["poupanca_galp"], 0.0)
        self.assertAlmostEqual(r["poupanca_total"], 0.0)


class TestPrecos(unittest.TestCase):
    """
    Os precos por kWh saem do custo da energia. Os que descontam beneficios sao
    equivalencias, porque nenhum dos dois abate na fatura.
    """

    def base(self, **extra):
        conta = dict(
            eletricidade=True,
            compras=300.0,
            litros=40.0,
            fatura_ele=62.65,
            energia_ele=46.83,
            kwh_ele=300.0,
        )
        conta.update(extra)
        return dados.simular_combina(**conta)

    def test_preco_normal_e_o_da_energia(self):
        r = self.base()
        self.assertAlmostEqual(r["preco_normal"], 46.83 / 300.0)

    def test_preco_com_saldo_do_continente(self):
        r = self.base(nos=True)
        self.assertAlmostEqual(r["preco_continente"], (46.83 - 15.0) / 300.0)

    def test_preco_com_os_dois_beneficios(self):
        r = self.base(nos=True)
        self.assertAlmostEqual(r["preco_equivalente"], (46.83 - 15.0 - 10.0) / 300.0)

    def test_o_combustivel_pode_levar_o_equivalente_a_zero(self):
        r = self.base(gas=True, nos=True, compras=450.0, litros=250.0)
        # 45 EUR de saldo contra 46,83 de energia: ainda sobra alguma coisa.
        self.assertAlmostEqual(r["preco_continente"], (46.83 - 45.0) / 300.0)
        self.assertFalse(r["preco_continente_limitado"])
        # Somados os 75 EUR de combustivel, ja nao sobra.
        self.assertEqual(r["preco_equivalente"], 0.0)
        self.assertTrue(r["preco_equivalente_limitado"])

    def test_o_saldo_sozinho_tambem_pode_levar_a_zero(self):
        """Compras grandes e energia pequena: o cartao cobre a energia toda."""
        r = self.base(gas=True, nos=True, compras=450.0, energia_ele=30.0)
        self.assertAlmostEqual(r["poupanca_continente"], 45.0)
        self.assertEqual(r["preco_continente"], 0.0)
        self.assertTrue(r["preco_continente_limitado"])

    def test_a_fatura_nao_muda_com_os_beneficios(self):
        r = self.base(nos=True)
        self.assertAlmostEqual(r["fatura_energia"], 62.65)
        self.assertAlmostEqual(r["custo_energia"], 46.83)

    def test_poupanca_por_kwh_e_informativa(self):
        r = self.base(nos=True)
        self.assertAlmostEqual(r["poupanca_por_kwh"], 25.0 / 300.0)

    def test_saldo_reparte_se_pelas_duas_energias(self):
        r = self.base(gas=True, fatura_gas=18.71, energia_gas=13.08, kwh_gas=150.0)
        custo = 46.83 + 13.08
        saldo = r["poupanca_continente"]
        self.assertAlmostEqual(
            r["preco_efetivo_ele"], (46.83 - saldo * 46.83 / custo) / 300.0
        )
        self.assertAlmostEqual(
            r["preco_efetivo_gas"], (13.08 - saldo * 13.08 / custo) / 150.0
        )

    def test_sem_consumo_nao_ha_preco(self):
        r = dados.simular_combina(
            eletricidade=True, compras=300.0, fatura_ele=0.0, energia_ele=0.0
        )
        self.assertIsNone(r["preco_normal"])
        self.assertIsNone(r["preco_continente"])


class TestValidacao(unittest.TestCase):
    """Nunca aceitar valores negativos."""

    def test_litros_negativos_valem_zero(self):
        r = dados.beneficio_galp(-50.0, 0.30)
        self.assertAlmostEqual(r["litros"], 0.0)
        self.assertAlmostEqual(r["beneficio"], 0.0)

    def test_compras_negativas_valem_zero(self):
        r = dados.beneficio_continente(-100.0, 10.0)
        self.assertAlmostEqual(r["elegivel"], 0.0)
        self.assertAlmostEqual(r["beneficio"], 0.0)

    def test_tudo_negativo_vale_zero(self):
        r = dados.simular_combina(
            eletricidade=True,
            fatura_ele=-45.0,
            energia_ele=-45.0,
            kwh_ele=-300.0,
            litros=-10.0,
            compras=-300.0,
        )
        self.assertAlmostEqual(r["fatura_energia"], 0.0)
        self.assertAlmostEqual(r["kwh_total"], 0.0)
        self.assertAlmostEqual(r["poupanca_total"], 0.0)


if __name__ == "__main__":
    unittest.main()
