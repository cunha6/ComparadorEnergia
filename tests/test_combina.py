"""
Testes das regras do Galp COMBINA.

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
    """A matriz completa da seccao 7 do pedido, linha a linha."""

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
        self.assertEqual(r["galp_por_litro"], 0.20)

    def test_3_so_nos(self):
        r = self.nivel(False, False, True)
        self.assertEqual(r["nivel"], 1)
        self.assertEqual(r["continente_percentagem"], 2.0)
        self.assertEqual(r["galp_por_litro"], 0.20)

    def test_4_eletricidade_e_gas(self):
        r = self.nivel(True, True, False)
        self.assertEqual(r["nivel"], 2)
        self.assertEqual(r["continente_percentagem"], 5.0)
        self.assertEqual(r["galp_por_litro"], 0.25)

    def test_5_eletricidade_e_nos(self):
        r = self.nivel(True, False, True)
        self.assertEqual(r["nivel"], 2)
        self.assertEqual(r["continente_percentagem"], 5.0)
        self.assertEqual(r["galp_por_litro"], 0.25)

    def test_6_gas_e_nos(self):
        r = self.nivel(False, True, True)
        self.assertEqual(r["nivel"], 2)
        self.assertEqual(r["continente_percentagem"], 5.0)
        self.assertEqual(r["galp_por_litro"], 0.25)

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
        """Seccao 9: so contam juntos se forem do mesmo local de consumo."""
        r = dados.nivel_combina(True, True, False, mesmo_local=False)
        self.assertEqual(r["nivel"], 1)
        # O gas continua a ser um servico do cliente, so nao soma nivel.
        self.assertTrue(r["servicos"]["gas"])

    def test_local_diferente_sem_eletricidade_o_gas_conta(self):
        r = dados.nivel_combina(False, True, True, mesmo_local=False)
        self.assertEqual(r["nivel"], 2)


class TestContinente(unittest.TestCase):
    def test_8_preco_efetivo_com_continente(self):
        """300 kWh a 0,15 EUR, COMBINA 3."""
        r = dados.simular_combina(
            eletricidade=True,
            gas=True,
            nos=True,
            fatura_ele=45.0,
            energia_ele=45.0,
            kwh_ele=300.0,
        )
        self.assertEqual(r["nivel"], 3)
        self.assertAlmostEqual(r["fatura_energia"], 45.0)
        self.assertAlmostEqual(r["poupanca_continente"], 4.50)
        self.assertAlmostEqual(r["fatura_energia"] - r["poupanca_continente"], 40.50)
        self.assertAlmostEqual(r["preco_normal"], 0.15)
        self.assertAlmostEqual(r["preco_continente"], 0.135)

    def test_11_limite_dos_450_euros(self):
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


class TestGalp(unittest.TestCase):
    def test_9_cento_e_cinquenta_litros(self):
        r = dados.beneficio_galp(150.0, 0.30)
        self.assertAlmostEqual(r["beneficio"], 45.0)
        self.assertFalse(r["limitado"])

    def test_10_limite_dos_250_litros(self):
        r = dados.beneficio_galp(300.0, 0.30)
        self.assertAlmostEqual(r["litros"], 300.0)
        self.assertAlmostEqual(r["elegiveis"], 250.0)
        self.assertAlmostEqual(r["beneficio"], 75.0)
        self.assertTrue(r["limitado"])

    def test_12_zero_litros(self):
        r = dados.simular_combina(
            eletricidade=True,
            nos=True,
            fatura_ele=45.0,
            energia_ele=45.0,
            kwh_ele=300.0,
            litros=0.0,
        )
        self.assertEqual(r["nivel"], 2)
        self.assertAlmostEqual(r["poupanca_galp"], 0.0)
        # Seccao 23: sem litros o cliente nao perde o nivel.
        self.assertTrue(r["elegivel"])
        self.assertAlmostEqual(r["continente_percentagem"], 5.0)

    def test_beneficio_por_nivel(self):
        esperado = {1: 30.0, 2: 37.50, 3: 45.0}
        for nivel, valor in esperado.items():
            por_litro = dados.COMBINA_NIVEIS[nivel]["galp"]
            self.assertAlmostEqual(
                dados.beneficio_galp(150.0, por_litro)["beneficio"],
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


class TestCenarios(unittest.TestCase):
    def test_13_eletricidade_mais_nos(self):
        """O exemplo final da seccao 35."""
        r = dados.simular_combina(
            eletricidade=True,
            nos=True,
            fatura_ele=45.0,
            energia_ele=45.0,
            kwh_ele=300.0,
            litros=150.0,
        )
        self.assertEqual(r["nivel"], 2)
        self.assertAlmostEqual(r["continente_percentagem"], 5.0)
        self.assertAlmostEqual(r["galp_por_litro"], 0.25)
        self.assertAlmostEqual(r["poupanca_continente"], 2.25)
        self.assertAlmostEqual(r["poupanca_galp"], 37.50)
        self.assertAlmostEqual(r["poupanca_total"], 39.75)
        self.assertAlmostEqual(r["preco_normal"], 0.15)
        self.assertAlmostEqual(r["preco_continente"], 0.1425)

    def test_14_eletricidade_mais_gas_mais_nos(self):
        r = dados.simular_combina(
            eletricidade=True,
            gas=True,
            nos=True,
            fatura_ele=45.0, energia_ele=45.0,
            kwh_ele=300.0,
            fatura_gas=10.0, energia_gas=10.0,
            kwh_gas=100.0,
            litros=150.0,
        )
        self.assertEqual(r["nivel"], 3)
        self.assertAlmostEqual(r["continente_percentagem"], 10.0)
        self.assertAlmostEqual(r["galp_por_litro"], 0.30)
        self.assertAlmostEqual(r["fatura_energia"], 55.0)
        self.assertAlmostEqual(r["poupanca_galp"], 45.0)

    def test_20_eletricidade_mais_gas_a_5_por_cento(self):
        """Exemplo da seccao 20: 55 EUR de energia com COMBINA 2."""
        r = dados.simular_combina(
            eletricidade=True,
            gas=True,
            fatura_ele=45.0, energia_ele=45.0,
            kwh_ele=300.0,
            fatura_gas=10.0, energia_gas=10.0,
            kwh_gas=100.0,
        )
        self.assertEqual(r["nivel"], 2)
        self.assertAlmostEqual(r["fatura_energia"], 55.0)
        self.assertAlmostEqual(r["poupanca_continente"], 2.75)

    def test_beneficio_reparte_se_pelas_duas_energias(self):
        r = dados.simular_combina(
            eletricidade=True,
            gas=True,
            fatura_ele=45.0, energia_ele=45.0,
            kwh_ele=300.0,
            fatura_gas=10.0, energia_gas=10.0,
            kwh_gas=100.0,
        )
        # 2,75 EUR repartidos na proporcao 45/55 e 10/55.
        parte_ele = 2.75 * (45.0 / 55.0)
        parte_gas = 2.75 * (10.0 / 55.0)
        self.assertAlmostEqual(r["preco_efetivo_ele"], (45.0 - parte_ele) / 300.0)
        self.assertAlmostEqual(r["preco_efetivo_gas"], (10.0 - parte_gas) / 100.0)

    def test_22_sem_servicos_nao_ha_beneficios(self):
        r = dados.simular_combina(litros=150.0)
        self.assertFalse(r["elegivel"])
        self.assertEqual(r["nivel"], 0)
        self.assertAlmostEqual(r["poupanca_continente"], 0.0)
        self.assertAlmostEqual(r["poupanca_galp"], 0.0)
        self.assertAlmostEqual(r["poupanca_total"], 0.0)


class TestPrecoEquivalente(unittest.TestCase):
    def test_18_nunca_devolve_preco_negativo(self):
        """Os 45 EUR de combustivel nao podem levar a fatura abaixo de zero."""
        r = dados.simular_combina(
            eletricidade=True,
            gas=True,
            nos=True,
            fatura_ele=45.0, energia_ele=45.0,
            kwh_ele=300.0,
            litros=150.0,
        )
        self.assertAlmostEqual(r["poupanca_galp"], 45.0)
        self.assertEqual(r["preco_equivalente"], 0.0)
        self.assertTrue(r["preco_equivalente_limitado"])

    def test_21_galp_nao_se_subtrai_a_fatura_de_energia(self):
        r = dados.simular_combina(
            eletricidade=True,
            nos=True,
            fatura_ele=45.0, energia_ele=45.0,
            kwh_ele=300.0,
            litros=150.0,
        )
        # A fatura e o preco com Continente ignoram o combustivel.
        self.assertAlmostEqual(r["fatura_energia"], 45.0)
        self.assertAlmostEqual(r["preco_continente"], 0.1425)
        # O combustivel so aparece na poupanca total.
        self.assertAlmostEqual(
            r["poupanca_total"], r["poupanca_continente"] + r["poupanca_galp"]
        )

    def test_poupanca_por_kwh_e_informativa(self):
        r = dados.simular_combina(
            eletricidade=True,
            nos=True,
            fatura_ele=45.0, energia_ele=45.0,
            kwh_ele=300.0,
            litros=150.0,
        )
        self.assertAlmostEqual(r["poupanca_por_kwh"], 39.75 / 300.0)

    def test_sem_consumo_nao_ha_preco(self):
        r = dados.simular_combina(
            eletricidade=True, fatura_ele=0.0, energia_ele=0.0, kwh_ele=0.0
        )
        self.assertIsNone(r["preco_normal"])
        self.assertIsNone(r["preco_continente"])


class TestBaseDoDesconto(unittest.TestCase):
    """A percentagem do Continente incide so sobre a energia."""

    def test_a_base_e_a_energia_e_nao_a_fatura(self):
        # Fatura de 85,65 EUR mas so 49,20 EUR de energia, que e o caso real de
        # uma proposta com termo fixo, taxas e IVA por cima.
        r = dados.simular_combina(
            eletricidade=True,
            gas=True,
            nos=True,
            fatura_ele=85.65,
            energia_ele=49.20,
            kwh_ele=300.0,
        )
        self.assertEqual(r["nivel"], 3)
        # 10% de 49,20 e nao de 85,65.
        self.assertAlmostEqual(r["poupanca_continente"], 4.92)
        self.assertAlmostEqual(r["custo_energia"], 49.20)
        self.assertAlmostEqual(r["fatura_energia"], 85.65)

    def test_preco_por_kwh_e_o_da_energia(self):
        r = dados.simular_combina(
            eletricidade=True,
            fatura_ele=85.65,
            energia_ele=49.20,
            kwh_ele=300.0,
        )
        self.assertAlmostEqual(r["preco_normal"], 0.164)
        # COMBINA 1, 2%: o preco desce na mesma percentagem.
        self.assertAlmostEqual(r["preco_continente"], 0.164 * 0.98)

    def test_valor_final_desconta_as_duas_poupancas(self):
        r = dados.simular_combina(
            eletricidade=True,
            nos=True,
            fatura_ele=85.65,
            energia_ele=49.20,
            kwh_ele=300.0,
            litros=150.0,
        )
        esperado = 85.65 - r["poupanca_continente"] - r["poupanca_galp"]
        self.assertAlmostEqual(r["valor_final"], esperado)
        self.assertAlmostEqual(r["poupanca_continente"], 49.20 * 0.05)
        self.assertAlmostEqual(r["poupanca_galp"], 150.0 * 0.25)
        self.assertFalse(r["valor_final_negativo"])

    def test_valor_final_pode_ficar_negativo(self):
        r = dados.simular_combina(
            eletricidade=True,
            gas=True,
            nos=True,
            fatura_ele=40.0,
            energia_ele=30.0,
            kwh_ele=200.0,
            litros=250.0,
        )
        self.assertAlmostEqual(r["poupanca_galp"], 75.0)
        self.assertLess(r["valor_final"], 0)
        self.assertTrue(r["valor_final_negativo"])


class TestValidacao(unittest.TestCase):
    """Seccao 24: nunca aceitar valores negativos."""

    def test_litros_negativos_valem_zero(self):
        r = dados.beneficio_galp(-50.0, 0.30)
        self.assertAlmostEqual(r["litros"], 0.0)
        self.assertAlmostEqual(r["beneficio"], 0.0)

    def test_compras_negativas_valem_zero(self):
        r = dados.beneficio_continente(-100.0, 10.0)
        self.assertAlmostEqual(r["elegivel"], 0.0)
        self.assertAlmostEqual(r["beneficio"], 0.0)

    def test_consumo_negativo_vale_zero(self):
        r = dados.simular_combina(
            eletricidade=True,
            fatura_ele=-45.0,
            energia_ele=-45.0,
            kwh_ele=-300.0,
            litros=-10.0,
        )
        self.assertAlmostEqual(r["fatura_energia"], 0.0)
        self.assertAlmostEqual(r["kwh_total"], 0.0)
        self.assertAlmostEqual(r["poupanca_total"], 0.0)


if __name__ == "__main__":
    unittest.main()
