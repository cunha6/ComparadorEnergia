"""
Camada de dados do comparador.

Le os dois CSV do simulador de precos da ERSE e transforma-os em tabelas
prontas a mostrar:

  Precos_ELEGN.csv   precos por proposta
                     eletricidade  ->  linhas com Pot_Cont e Contagem
                     gas natural   ->  linhas com Escalao e TFGN/TVGN
  CondComerciais.csv condicoes comerciais de cada proposta

Funcoes principais
  carregar(precos, condicoes) -> Catalogo
  Catalogo.tabela_ele(...)    -> DataFrame com os precos de eletricidade
  Catalogo.tabela_gn(...)     -> DataFrame com os precos de gas natural
  simular_ele(...)            -> estimativa de fatura de eletricidade
  simular_gn(...)             -> estimativa de fatura de gas natural
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

import pandas as pd

# Contagem no CSV da ERSE.
SIMPLES = 1
BI_HORARIO = 2
TRI_HORARIO = 3

NOMES_CICLO = {
    SIMPLES: "Simples",
    BI_HORARIO: "Bi-horário",
    TRI_HORARIO: "Tri-horário",
}

# Colunas de energia. O significado muda conforme a contagem.
COL_TF = "TF"
COL_P1 = "TV|TVFV|TVP"  # simples, fora de vazio, ou ponta
COL_P2 = "TVV|TVC"      # vazio no bi-horario, cheias no tri-horario
COL_P3 = "TVVz"         # vazio no tri-horario

PERIODOS = {
    SIMPLES: ["Energia"],
    BI_HORARIO: ["Fora de vazio", "Vazio"],
    TRI_HORARIO: ["Ponta", "Cheias", "Vazio"],
}

ESCALOES_GN = {
    1: "Escalão 1 · até 220 m³/ano",
    2: "Escalão 2 · 220 a 500 m³/ano",
    3: "Escalão 3 · 500 a 1000 m³/ano",
    4: "Escalão 4 · 1000 a 10 000 m³/ano",
}

SEGMENTOS = {"Dom": "Doméstico", "Ndom": "Não doméstico", "Tod": "Todos"}

# O CSV traz codigos, as tabelas mostram o nome comercial.
NOMES_COMERCIALIZADORES = {
    "ACCIONA": "Acciona",
    "ALFAENERGIA": "Alfa Energia",
    "AUDAX": "Audax",
    "AXPO": "Axpo",
    "COOP": "Coopérnico",
    "CUR": "Tarifa regulada gás",
    "DOUROGAS": "Dourogás",
    "EDPC": "EDP",
    "ELERGONE": "Elergone",
    "END": "Endesa",
    "ENIPLENITUDE": "Plenitude",
    "EZUENERGIA": "EZU Energia",
    "GALP": "Galp",
    "GOLD": "Goldenergy",
    "IBD": "Iberdrola",
    "IBELECTRA": "Ibelectra",
    "JAFPLUS": "JAF Plus",
    "LOGICA": "Lógica Energy",
    "LUZBOA": "Luzboa",
    "LUZIGAS": "Luzigás",
    "MEOENERGIA": "MEO Energia",
    "MUON": "Muon",
    "NABALIAENERGIA": "Nabalia Energia",
    "NOSSAENERGIA": "Nossa Energia",
    "OENEO": "Oeneo",
    "PORTULOGOS": "Portulogos",
    "REPSOL": "Repsol",
    "TUR": "Tarifa regulada",
    "U1": "Preços do utilizador",
    "USENERGY": "Use Energy",
    "YESENERGY": "Yes Energy",
    "ZUG POWER": "Zug Power",
}

# Os comercializadores que aparecem escolhidos de raiz, pela ordem em que sao
# mostrados nas tabelas.
PRINCIPAIS = [
    "EDP",
    "Galp",
    "Iberdrola",
    "Endesa",
    "Goldenergy",
    "Repsol",
    "Plenitude",
    "MEO Energia",
]

# As potencias domesticas mais comuns, colunas da tabela comparativa.
POTENCIAS_HABITUAIS = [3.45, 4.6, 5.75, 6.9, 10.35]

# Linhas da tabela comparativa, por ciclo de contagem.
COMPONENTES_ELE = {
    SIMPLES: [
        ("termo_fixo", "Termo fixo simples (€/dia)"),
        ("preco_1", "Energia simples (€/kWh)"),
    ],
    BI_HORARIO: [
        ("termo_fixo", "Termo fixo bi (€/dia)"),
        ("preco_1", "Fora de vazio (€/kWh)"),
        ("preco_2", "Vazio (€/kWh)"),
    ],
    TRI_HORARIO: [
        ("termo_fixo", "Termo fixo tri (€/dia)"),
        ("preco_1", "Ponta (€/kWh)"),
        ("preco_2", "Cheias (€/kWh)"),
        ("preco_3", "Vazio (€/kWh)"),
    ],
}


def nome_comercializador(codigo: str) -> str:
    """Nome comercial a partir do codigo do CSV."""
    codigo = (codigo or "").strip()
    if codigo in NOMES_COMERCIALIZADORES:
        return NOMES_COMERCIALIZADORES[codigo]
    if codigo.startswith("CUR"):
        return "Tarifa regulada gás"
    return codigo.title()


def rotulo_potencia(potencia: float) -> str:
    return f"{potencia:.2f}".replace(".", ",")

# Valores por omissao dos encargos que aparecem na fatura de eletricidade.
CAV_MENSAL = 2.85       # contribuicao audiovisual, IVA a 6%
DGEG_MENSAL = 0.07      # taxa de exploracao DGEG, IVA a 23%
IVA_NORMAL = 23.0
IVA_REDUZIDO = 6.0
POTENCIA_IVA_REDUZIDO = 3.45  # kVA ate ao qual a potencia leva IVA reduzido


# --------------------------------------------------------------- leitura


def _numero(serie: pd.Series) -> pd.Series:
    """Converte texto com virgula decimal em numero."""
    limpo = serie.astype("string").str.strip().str.replace(",", ".", regex=False)
    return pd.to_numeric(limpo, errors="coerce")


def _texto(serie: pd.Series) -> pd.Series:
    return serie.astype("string").fillna("").str.strip()


def _sim(serie: pd.Series) -> pd.Series:
    return _texto(serie).str.upper().eq("S")


def _data(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(
        _texto(serie).replace("", None), format="%d/%m/%Y", errors="coerce"
    )


@dataclass
class Catalogo:
    """Tudo o que a aplicacao precisa, ja tratado."""

    ele: pd.DataFrame
    gn: pd.DataFrame
    condicoes: pd.DataFrame

    # ------------------------------------------------------- listas de opcoes

    def potencias(self) -> list[float]:
        return sorted(self.ele["potencia"].dropna().unique().tolist())

    def contagens(self, potencia: float | None = None) -> list[int]:
        linhas = self.ele
        if potencia is not None:
            linhas = linhas[linhas["potencia"] == potencia]
        return sorted(int(c) for c in linhas["contagem"].dropna().unique())

    def escaloes(self) -> list[int]:
        return sorted(int(e) for e in self.gn["escalao"].dropna().unique())

    def comercializadores(self, energia: str = "ele") -> list[str]:
        """Nomes comerciais, com os principais primeiro."""
        origem = self.ele if energia == "ele" else self.gn
        presentes = set(origem["marca"].dropna().unique().tolist())
        primeiros = [m for m in PRINCIPAIS if m in presentes]
        return primeiros + sorted(presentes - set(primeiros))

    # ------------------------------------------------------- tabelas

    def tabela_ele(
        self,
        potencia: float,
        contagem: int,
        segmento: str = "Todos",
        comercializadores: list[str] | None = None,
        so_ativas: bool = True,
        sem_indexadas: bool = False,
        sem_so_novos_clientes: bool = False,
        so_renovavel: bool = False,
        dia: _dt.date | None = None,
    ) -> pd.DataFrame:
        linhas = self.ele
        linhas = linhas[
            (linhas["potencia"] == potencia) & (linhas["contagem"] == contagem)
        ]
        linhas = _aplicar_filtros(
            linhas,
            segmento=segmento,
            comercializadores=comercializadores,
            so_ativas=so_ativas,
            sem_indexadas=sem_indexadas,
            sem_so_novos_clientes=sem_so_novos_clientes,
            so_renovavel=so_renovavel,
            dia=dia,
        )
        return linhas.sort_values(["preco_1", "termo_fixo"]).reset_index(drop=True)

    def tabela_gn(
        self,
        escalao: int,
        segmento: str = "Todos",
        comercializadores: list[str] | None = None,
        so_ativas: bool = True,
        sem_so_novos_clientes: bool = False,
        dia: _dt.date | None = None,
    ) -> pd.DataFrame:
        linhas = self.gn[self.gn["escalao"] == escalao]
        linhas = _aplicar_filtros(
            linhas,
            segmento=segmento,
            comercializadores=comercializadores,
            so_ativas=so_ativas,
            sem_indexadas=False,
            sem_so_novos_clientes=sem_so_novos_clientes,
            so_renovavel=False,
            dia=dia,
        )
        return linhas.sort_values(["energia", "termo_fixo"]).reset_index(drop=True)


def _aplicar_filtros(
    linhas: pd.DataFrame,
    segmento: str,
    comercializadores: list[str] | None,
    so_ativas: bool,
    sem_indexadas: bool,
    sem_so_novos_clientes: bool,
    so_renovavel: bool,
    dia: _dt.date | None,
) -> pd.DataFrame:
    if segmento and segmento != "Todos":
        linhas = linhas[linhas["segmento"].isin([segmento, "Tod"])]
    if comercializadores:
        linhas = linhas[linhas["marca"].isin(comercializadores)]
    if sem_indexadas and "indexada" in linhas.columns:
        linhas = linhas[~linhas["indexada"]]
    if sem_so_novos_clientes and "so_novos_clientes" in linhas.columns:
        linhas = linhas[~linhas["so_novos_clientes"]]
    if so_renovavel and "renovavel" in linhas.columns:
        linhas = linhas[linhas["renovavel"]]
    if so_ativas:
        momento = pd.Timestamp(dia or _dt.date.today())
        inicio = linhas["data_ini"]
        fim = linhas["data_fim"]
        linhas = linhas[
            (inicio.isna() | (inicio <= momento)) & (fim.isna() | (fim >= momento))
        ]
    return linhas


# --------------------------------------------------------------- carregar


COLUNAS_CONDICOES = {
    "COD_Proposta": "codigo",
    "COM": "com_codigo",
    "NomeProposta": "proposta",
    "Segmento": "segmento",
    "Fornecimento": "fornecimento",
    "DuracaoContrato": "duracao",
    "Data ini": "data_ini",
    "Data fim": "data_fim",
    "FiltroPrecosIndex_ELE": "indexada",
    "FiltroNovosClientes": "so_novos_clientes",
    "FiltroRenovavel_ELE": "renovavel",
    "FiltroTarifaSocial": "tarifa_social",
    "TxTFidelização": "fidelizacao",
    "TxTPagamento": "pagamento",
    "TxTFatura": "faturacao",
    "TxTContratação": "contratacao",
    "TxTAtualizaPrecos": "atualizacao_precos",
    "TxTOferta": "descricao",
    "TxTServicoAdic": "servicos",
    "LinkOfertaCom": "link_oferta",
    "LinkFichaPadrao": "link_ficha",
    "ContactoComercialTel": "telefone",
    "ContactoWEBouMAIL": "contacto_web",
}


def _ler_condicoes(caminho: str) -> pd.DataFrame:
    bruto = pd.read_csv(
        caminho, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False
    )
    if "COD_Proposta" not in bruto.columns or "NomeProposta" not in bruto.columns:
        raise ValueError(
            "O ficheiro de condicoes comerciais nao tem as colunas esperadas "
            "(COD_Proposta, NomeProposta). Verifique se e o CondComerciais.csv."
        )

    tabela = pd.DataFrame(index=bruto.index)
    for origem, destino in COLUNAS_CONDICOES.items():
        tabela[destino] = _texto(bruto[origem]) if origem in bruto.columns else ""

    for coluna in ("indexada", "so_novos_clientes", "renovavel", "tarifa_social"):
        tabela[coluna] = _sim(tabela[coluna])
    tabela["data_ini"] = _data(tabela["data_ini"])
    tabela["data_fim"] = _data(tabela["data_fim"])
    tabela["segmento_nome"] = tabela["segmento"].map(SEGMENTOS).fillna(
        tabela["segmento"]
    )
    return tabela.drop_duplicates(subset="codigo").set_index("codigo")


def _ler_precos(caminho: str) -> pd.DataFrame:
    bruto = pd.read_csv(
        caminho, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False
    )
    em_falta = [c for c in ("COM", "COD_Proposta", COL_TF) if c not in bruto.columns]
    if em_falta:
        raise ValueError(
            "O ficheiro de precos nao tem as colunas esperadas "
            f"({', '.join(em_falta)}). Verifique se e o Precos_ELEGN.csv."
        )
    return bruto


def carregar(caminho_precos: str, caminho_condicoes: str) -> Catalogo:
    """Le os dois CSV e devolve o catalogo pronto a usar."""
    bruto = _ler_precos(caminho_precos)
    condicoes = _ler_condicoes(caminho_condicoes)

    base = pd.DataFrame(
        {
            "codigo": _texto(bruto["COD_Proposta"]),
            "comercializador": _texto(bruto["COM"]),
            "potencia": _numero(bruto["Pot_Cont"]),
            "contagem": _numero(bruto["Contagem"]),
            "escalao": _numero(bruto["Escalao"]),
            "regiao": _texto(bruto["ORD"]) if "ORD" in bruto.columns else "",
            "termo_fixo": _numero(bruto[COL_TF]),
            "preco_1": _numero(bruto[COL_P1]),
            "preco_2": _numero(bruto[COL_P2]),
            "preco_3": _numero(bruto[COL_P3]),
            "tf_gn": _numero(bruto["TFGN"]) if "TFGN" in bruto.columns else pd.NA,
            "energia_gn": _numero(bruto["TVGN"]) if "TVGN" in bruto.columns else pd.NA,
        }
    )

    # Eletricidade: linhas com potencia, contagem e pelo menos um preco.
    ele = base[
        base["potencia"].notna()
        & base["contagem"].notna()
        & (base["preco_1"].notna() | base["termo_fixo"].notna())
    ].copy()
    ele["contagem"] = ele["contagem"].astype(int)
    ele["potencia"] = ele["potencia"].round(2)
    ele = ele[
        [
            "codigo",
            "comercializador",
            "potencia",
            "contagem",
            "termo_fixo",
            "preco_1",
            "preco_2",
            "preco_3",
        ]
    ]

    # Gas natural: o escalao manda, as colunas de potencia sao reaproveitadas.
    gn = base[
        base["escalao"].notna()
        & (base["tf_gn"].notna() | base["energia_gn"].notna())
    ].copy()
    gn["escalao"] = gn["escalao"].astype(int)
    gn = gn.rename(columns={"tf_gn": "termo_fixo_gn", "energia_gn": "energia"})
    gn = gn[["codigo", "comercializador", "escalao", "regiao", "termo_fixo_gn", "energia"]]
    gn = gn.rename(columns={"termo_fixo_gn": "termo_fixo"})
    gn = gn.drop_duplicates(subset=["codigo", "escalao", "regiao"])

    return Catalogo(
        ele=_juntar(ele, condicoes),
        gn=_juntar(gn, condicoes),
        condicoes=condicoes,
    )


def _juntar(precos: pd.DataFrame, condicoes: pd.DataFrame) -> pd.DataFrame:
    junto = precos.join(condicoes, on="codigo")
    junto["marca"] = junto["comercializador"].map(nome_comercializador)
    junto["proposta"] = junto["proposta"].fillna("").replace("", pd.NA)
    junto["proposta"] = junto["proposta"].fillna(junto["codigo"])
    for coluna in ("indexada", "so_novos_clientes", "renovavel", "tarifa_social"):
        junto[coluna] = junto[coluna].fillna(False).astype(bool)
    for coluna in condicoes.columns:
        if junto[coluna].dtype == object or str(junto[coluna].dtype) == "string":
            junto[coluna] = junto[coluna].fillna("")
    return junto.reset_index(drop=True)


# --------------------------------------------------------------- simulador


def simular_ele(
    tabela: pd.DataFrame,
    potencia: float,
    contagem: int,
    dias: int,
    consumos: list[float],
    iva: float = IVA_NORMAL,
    iva_reduzido_potencia: bool = True,
    cav: float = CAV_MENSAL,
    dgeg: float = DGEG_MENSAL,
    meses: float = 1.0,
) -> pd.DataFrame:
    """
    Estima o custo do periodo para cada proposta da tabela.

    consumos tem um valor por periodo horario, pela ordem de PERIODOS.
    """
    if tabela.empty:
        return tabela.copy()

    colunas = ["preco_1", "preco_2", "preco_3"][: len(PERIODOS[contagem])]
    resultado = tabela.copy()

    custo_energia = pd.Series(0.0, index=resultado.index)
    valido = pd.Series(True, index=resultado.index)
    for coluna, kwh in zip(colunas, consumos):
        preco = pd.to_numeric(resultado[coluna], errors="coerce")
        valido &= preco.notna()
        custo_energia = custo_energia + preco.fillna(0.0) * float(kwh)
    resultado = resultado[valido].copy()
    custo_energia = custo_energia[valido]

    custo_potencia = resultado["termo_fixo"].fillna(0.0) * dias

    taxa_potencia = (
        IVA_REDUZIDO
        if (iva_reduzido_potencia and potencia <= POTENCIA_IVA_REDUZIDO)
        else iva
    )
    encargo_cav = cav * meses
    encargo_dgeg = dgeg * meses

    iva_energia = custo_energia * iva / 100.0
    iva_potencia = custo_potencia * taxa_potencia / 100.0
    iva_encargos = encargo_cav * IVA_REDUZIDO / 100.0 + encargo_dgeg * iva / 100.0

    resultado["custo_energia"] = custo_energia
    resultado["custo_potencia"] = custo_potencia
    resultado["encargos"] = encargo_cav + encargo_dgeg
    resultado["sem_iva"] = custo_energia + custo_potencia + encargo_cav + encargo_dgeg
    resultado["iva"] = iva_energia + iva_potencia + iva_encargos
    resultado["total"] = resultado["sem_iva"] + resultado["iva"]
    resultado["media_mensal"] = resultado["total"] / max(meses, 0.0001)
    return resultado.sort_values("total").reset_index(drop=True)


def simular_gn(
    tabela: pd.DataFrame,
    escalao: int,
    dias: int,
    kwh: float,
    iva: float = IVA_NORMAL,
    iva_reduzido_termo_fixo: bool = True,
    encargos: float = 0.0,
    meses: float = 1.0,
) -> pd.DataFrame:
    """Estima o custo do periodo para cada proposta de gas natural."""
    if tabela.empty:
        return tabela.copy()

    resultado = tabela[tabela["energia"].notna()].copy()
    custo_energia = resultado["energia"] * float(kwh)
    custo_termo = resultado["termo_fixo"].fillna(0.0) * dias

    taxa_termo = IVA_REDUZIDO if (iva_reduzido_termo_fixo and escalao == 1) else iva
    total_encargos = encargos * meses

    resultado["custo_energia"] = custo_energia
    resultado["custo_potencia"] = custo_termo
    resultado["encargos"] = total_encargos
    resultado["sem_iva"] = custo_energia + custo_termo + total_encargos
    resultado["iva"] = (
        custo_energia * iva / 100.0
        + custo_termo * taxa_termo / 100.0
        + total_encargos * iva / 100.0
    )
    resultado["total"] = resultado["sem_iva"] + resultado["iva"]
    resultado["media_mensal"] = resultado["total"] / max(meses, 0.0001)
    return resultado.sort_values("total").reset_index(drop=True)


def melhor_por_comercializador(tabela: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Guarda so a proposta mais barata de cada comercializador."""
    if tabela.empty:
        return tabela
    criterio = [coluna, "termo_fixo"] if "termo_fixo" in tabela.columns else [coluna]
    ordenada = tabela.sort_values(criterio)
    return ordenada.drop_duplicates(subset="marca").reset_index(drop=True)


# --------------------------------------------------------------- galp combina

# Valores do programa Galp COMBINA. Ficam todos aqui, num sitio so, para nao
# andarem espalhados pelos ecras. A chave e o numero de servicos elegiveis.
COMBINA_NIVEIS = {
    1: {"continente": 2.0, "galp": 0.20},
    2: {"continente": 5.0, "galp": 0.25},
    3: {"continente": 10.0, "galp": 0.30},
}

# Teto mensal de compras que contam para a percentagem do Continente.
COMBINA_MAX_COMPRAS = 450.0

# Teto mensal de litros que contam para o desconto da Galp.
COMBINA_MAX_LITROS = 250.0

# Limite por abastecimento. Nao entra na conta mensal, porque o simulador
# pergunta o consumo do mes e nao ha maneira de saber em quantas idas a bomba
# esse mes foi feito. Fica so como regra a mostrar ao utilizador.
COMBINA_MAX_LITROS_ABASTECIMENTO = 60.0

NOMES_SERVICOS_COMBINA = {
    "eletricidade": "Eletricidade",
    "gas": "Gás natural",
    "nos": "NOS",
}


def nivel_combina(
    eletricidade: bool, gas: bool, nos: bool, mesmo_local: bool = True
) -> dict:
    """
    Nivel COMBINA a partir dos servicos que o cliente tem.

    mesmo_local diz se a eletricidade e o gas sao do mesmo local de consumo,
    que e a condicao para contarem como dois servicos. A aplicacao nao tem
    hoje dados de morada, por isso o valor por omissao e True e nao existe
    campo para isto no ecra. O parametro fica preparado para quando essa
    informacao existir.
    """
    tem_ele = bool(eletricidade)
    tem_gas = bool(gas)
    tem_nos = bool(nos)

    # Sem a garantia de ser o mesmo local, o gas nao acrescenta um segundo
    # servico a eletricidade.
    conta_gas = tem_gas and (mesmo_local or not tem_ele)

    quantos = min(sum((tem_ele, conta_gas, tem_nos)), 3)
    beneficios = COMBINA_NIVEIS.get(quantos, {"continente": 0.0, "galp": 0.0})
    return {
        "nivel": quantos,
        "servicos": {"eletricidade": tem_ele, "gas": tem_gas, "nos": tem_nos},
        "n_servicos": quantos,
        "elegivel": quantos > 0,
        "continente_percentagem": beneficios["continente"],
        "galp_por_litro": beneficios["galp"],
    }


def beneficio_continente(valor_mensal: float, percentagem: float) -> dict:
    """Cartao Continente: percentagem sobre o valor mensal, com teto."""
    valor = max(float(valor_mensal), 0.0)
    elegivel = min(valor, COMBINA_MAX_COMPRAS)
    return {
        "valor": valor,
        "elegivel": elegivel,
        "beneficio": elegivel * float(percentagem) / 100.0,
        "limitado": valor > COMBINA_MAX_COMPRAS,
    }


def beneficio_galp(litros_mensais: float, por_litro: float) -> dict:
    """Desconto no combustivel: euros por litro, com teto mensal de litros."""
    litros = max(float(litros_mensais), 0.0)
    elegiveis = min(litros, COMBINA_MAX_LITROS)
    return {
        "litros": litros,
        "elegiveis": elegiveis,
        "beneficio": elegiveis * float(por_litro),
        "limitado": litros > COMBINA_MAX_LITROS,
    }


def preco_por_kwh(fatura: float, kwh: float) -> float | None:
    """Preco medio do kWh. None quando nao ha consumo para dividir."""
    kwh = float(kwh)
    if kwh <= 0:
        return None
    return float(fatura) / kwh


def simular_combina(
    eletricidade: bool = False,
    gas: bool = False,
    nos: bool = False,
    fatura_ele: float = 0.0,
    kwh_ele: float = 0.0,
    fatura_gas: float = 0.0,
    kwh_gas: float = 0.0,
    litros: float = 0.0,
    mesmo_local: bool = True,
) -> dict:
    """
    Tudo o que a seccao Galp COMBINA precisa de mostrar, ja calculado.

    Todos os valores de entrada e de saida sao mensais, porque os limites do
    programa sao mensais. Quem chama trata de dividir o periodo simulado.

    O beneficio da Galp e sobre combustivel e nao se subtrai a fatura de
    energia. So entra na poupanca total e no preco equivalente, que e uma
    metrica de comparacao e vem marcada como tal em preco_equivalente_limitado.
    """
    nivel = nivel_combina(eletricidade, gas, nos, mesmo_local)

    # Uma energia que o cliente nao tem nao traz fatura nem consumo.
    valor_ele = max(float(fatura_ele), 0.0) if nivel["servicos"]["eletricidade"] else 0.0
    consumo_ele = max(float(kwh_ele), 0.0) if nivel["servicos"]["eletricidade"] else 0.0
    valor_gas = max(float(fatura_gas), 0.0) if nivel["servicos"]["gas"] else 0.0
    consumo_gas = max(float(kwh_gas), 0.0) if nivel["servicos"]["gas"] else 0.0

    fatura_energia = valor_ele + valor_gas
    kwh_total = consumo_ele + consumo_gas

    continente = beneficio_continente(fatura_energia, nivel["continente_percentagem"])
    galp = beneficio_galp(litros, nivel["galp_por_litro"])
    poupanca_total = continente["beneficio"] + galp["beneficio"]

    # O beneficio do Continente reparte-se pelas duas energias na proporcao do
    # peso de cada fatura, para o preco efetivo de cada uma fazer sentido.
    def _efetivo(valor: float, consumo: float) -> float | None:
        if fatura_energia <= 0:
            return preco_por_kwh(valor, consumo)
        parte = continente["beneficio"] * (valor / fatura_energia)
        return preco_por_kwh(valor - parte, consumo)

    # Quando os beneficios passam a fatura, o preco equivalente para em zero.
    # Um preco negativo nao diria nada a ninguem.
    sobra = fatura_energia - continente["beneficio"] - galp["beneficio"]
    return {
        "nivel": nivel["nivel"],
        "servicos": nivel["servicos"],
        "n_servicos": nivel["n_servicos"],
        "elegivel": nivel["elegivel"],
        "continente_percentagem": nivel["continente_percentagem"],
        "galp_por_litro": nivel["galp_por_litro"],
        "fatura_ele": valor_ele,
        "fatura_gas": valor_gas,
        "fatura_energia": fatura_energia,
        "kwh_ele": consumo_ele,
        "kwh_gas": consumo_gas,
        "kwh_total": kwh_total,
        "continente_elegivel": continente["elegivel"],
        "continente_limitado": continente["limitado"],
        "poupanca_continente": continente["beneficio"],
        "litros": galp["litros"],
        "litros_elegiveis": galp["elegiveis"],
        "litros_limitado": galp["limitado"],
        "poupanca_galp": galp["beneficio"],
        "poupanca_total": poupanca_total,
        "preco_normal": preco_por_kwh(fatura_energia, kwh_total),
        "preco_continente": preco_por_kwh(
            fatura_energia - continente["beneficio"], kwh_total
        ),
        "preco_equivalente": preco_por_kwh(max(sobra, 0.0), kwh_total),
        "preco_equivalente_limitado": sobra < 0,
        "poupanca_por_kwh": preco_por_kwh(poupanca_total, kwh_total),
        "preco_efetivo_ele": _efetivo(valor_ele, consumo_ele),
        "preco_efetivo_gas": _efetivo(valor_gas, consumo_gas),
    }

# --------------------------------------------------------------- comparativo


def _ordenar_marcas(marcas) -> list[str]:
    presentes = set(marcas)
    primeiras = [m for m in PRINCIPAIS if m in presentes]
    return primeiras + sorted(presentes - set(primeiras))


def tabela_comparativa(
    catalogo: Catalogo, contagem: int, potencias: list[float], **filtros
) -> pd.DataFrame:
    """
    Uma linha por comercializador e componente, uma coluna por potencia.

    Em cada potencia usa-se a proposta mais barata de cada comercializador.
    """
    componentes = COMPONENTES_ELE[contagem]
    melhores: dict[float, pd.DataFrame] = {}
    marcas: list[str] = []
    for potencia in potencias:
        linhas = catalogo.tabela_ele(potencia, contagem, **filtros)
        if linhas.empty:
            melhores[potencia] = pd.DataFrame()
            continue
        bloco = melhor_por_comercializador(linhas, "preco_1").set_index("marca")
        melhores[potencia] = bloco
        marcas += bloco.index.tolist()

    registos = []
    for marca in _ordenar_marcas(marcas):
        for coluna, etiqueta in componentes:
            registo = {"Comercializador": marca, "Componente": etiqueta}
            for potencia in potencias:
                bloco = melhores[potencia]
                valor = None
                if not bloco.empty and marca in bloco.index:
                    valor = bloco.loc[marca, coluna]
                registo[rotulo_potencia(potencia)] = valor
            registos.append(registo)
    return pd.DataFrame(registos)


def propostas_das_marcas(
    catalogo: Catalogo, contagem: int, potencias: list[float], **filtros
) -> pd.DataFrame:
    """Que proposta ficou por tras de cada celula da tabela comparativa."""
    linhas = []
    for potencia in potencias:
        tabela = catalogo.tabela_ele(potencia, contagem, **filtros)
        if tabela.empty:
            continue
        bloco = melhor_por_comercializador(tabela, "preco_1")
        bloco = bloco.assign(potencia_rotulo=rotulo_potencia(potencia))
        linhas.append(bloco)
    if not linhas:
        return pd.DataFrame()
    juntas = pd.concat(linhas, ignore_index=True)
    juntas["marca"] = pd.Categorical(
        juntas["marca"], categories=_ordenar_marcas(juntas["marca"]), ordered=True
    )
    return juntas.sort_values(["marca", "potencia_rotulo"]).reset_index(drop=True)


def mais_barata(tabela: pd.DataFrame, coluna: str) -> pd.Series | None:
    """A linha mais barata de uma tabela, ou None se estiver vazia."""
    if tabela.empty or tabela[coluna].isna().all():
        return None
    criterio = [coluna, "termo_fixo"] if "termo_fixo" in tabela.columns else [coluna]
    return tabela.sort_values(criterio).iloc[0]
