"""
Comparador de Energia - interface Streamlit.

Vai buscar sozinho o ZIP das ofertas comerciais ao simulador de precos da ERSE,
extrai os dois CSV para a pasta de dados e mostra a tabela comparativa de
precos e o simulador de fatura.

Executar durante o desenvolvimento
    streamlit run app.py
Executar como aplicacao
    python main.py
"""

from __future__ import annotations

import datetime as _dt
import os
import tempfile
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import dados
import erse

# --------------------------------------------------------------- constantes

TITULO = "Comparador de Energia"
SUBTITULO = "Ofertas comerciais de eletricidade e gás natural publicadas pela ERSE"


def pasta_de_dados() -> Path:
    """
    Onde ficam os CSV descarregados.

    No Windows vai para o LOCALAPPDATA, num servidor Linux para a cache do
    utilizador, e a variavel COMPARADOR_DADOS manda em tudo se estiver posta.
    """
    definida = os.environ.get("COMPARADOR_DADOS")
    if definida:
        return Path(definida)
    windows = os.environ.get("LOCALAPPDATA")
    if windows:
        return Path(windows) / "ComparadorEnergia" / "dados"
    candidatas = [
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"),
        Path(tempfile.gettempdir()),
    ]
    for candidata in candidatas:
        try:
            candidata.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if os.access(candidata, os.W_OK):
            return candidata / "ComparadorEnergia" / "dados"
    return Path(tempfile.gettempdir()) / "ComparadorEnergia" / "dados"


PASTA_DADOS = pasta_de_dados()

COR_ELE = "#0E7C86"
COR_GN = "#B54708"
COR_TEXTO = "#10151F"
COR_SUAVE = "#5B6472"

DIAS_POR_MES = 30.4

st.set_page_config(
    page_title=TITULO,
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={},
)


# --------------------------------------------------------------- aspeto

ESTILO = """
<style>
/* tirar a barra de ferramentas, o botao de deploy e o rodape do Streamlit */
#MainMenu, footer, header[data-testid="stHeader"] {display: none !important;}
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], [data-testid="stAppDeployButton"],
.stDeployButton {display: none !important;}

/* badge "Hosted with Streamlit" e avatar do criador, postos pelo Community
   Cloud. As classes sao geradas com hashes e mudam a cada versao, por isso
   ha varios selectores para o mesmo elemento. */
[class*="viewerBadge"], [class*="profileContainer"],
[data-testid="stAppViewerBadge"],
a[href*="streamlit.io/cloud"], a[href*="share.streamlit.io/user"],
a[href*="streamlit.io/?utm"] {display: none !important;}

.block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1560px;}

/* cabecalho */
.cabecalho {
  background: linear-gradient(120deg, #0B3B5C 0%, #0E7C86 100%);
  border-radius: 16px; padding: 26px 30px; color: #fff; margin-bottom: 18px;
  box-shadow: 0 8px 24px rgba(11, 59, 92, 0.18);
}
.cabecalho h1 {margin: 0; font-size: 2rem; font-weight: 700; letter-spacing: -0.4px;}
.cabecalho p {margin: 6px 0 0; opacity: 0.88; font-size: 1rem;}
.cabecalho .etiqueta {
  display: inline-block; margin-top: 14px; padding: 5px 12px; border-radius: 999px;
  background: rgba(255,255,255,0.16); font-size: 0.82rem; letter-spacing: 0.2px;
}

/* destaque da oferta mais barata */
.vencedor {
  border: 1px solid #B7E0DE; border-left: 5px solid #0E7C86; border-radius: 12px;
  background: #F2FAFA; padding: 14px 18px; margin: 4px 0 16px;
}
.vencedor.gas {border-color: #F0D2B4; border-left-color: #B54708; background: #FDF7F1;}
.vencedor .titulo {font-size: 0.75rem; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: #5B6472; margin-bottom: 8px;}
.vencedor .linha {font-size: 0.95rem; color: #10151F; line-height: 1.9;}
.vencedor .kva {display: inline-block; min-width: 78px; color: #5B6472;
  font-size: 0.85rem;}
.vencedor .marca {font-weight: 700;}
.vencedor .preco {font-weight: 700; color: #0B3B5C;}

/* cartoes do podio */
.podio {
  border: 1px solid #E4E7EC; border-radius: 14px; padding: 16px 18px;
  background: #fff; height: 100%; box-shadow: 0 1px 2px rgba(16,21,31,0.05);
}
.podio.vencedora {border-color: #0E7C86; box-shadow: 0 4px 16px rgba(14,124,134,0.16);}
.podio .lugar {font-size: 0.75rem; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: #5B6472;}
.podio .marca {font-size: 1.05rem; font-weight: 700; color: #10151F; margin-top: 4px;}
.podio .nome {font-size: 0.86rem; color: #5B6472; margin-top: 2px; min-height: 2.4em;}
.podio .valor {font-size: 1.9rem; font-weight: 700; color: #0B3B5C; margin-top: 10px;}
.podio .unidade {font-size: 0.8rem; color: #5B6472; font-weight: 500;}
.podio .poupanca {font-size: 0.84rem; color: #0E7C86; font-weight: 600; margin-top: 4px;}

div[data-testid="stMetricValue"] {font-size: 1.5rem;}
section[data-testid="stSidebar"] {background: #F6F8FA; border-right: 1px solid #E4E7EC;}
.rodape {color: #5B6472; font-size: 0.82rem; margin-top: 30px; line-height: 1.6;}
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)


# --------------------------------------------------------------- dados


@st.cache_data(show_spinner=False)
def _carregar(caminho_precos: str, caminho_condicoes: str, versao: float):
    """versao entra na chave da cache para recarregar quando o ficheiro muda."""
    del versao
    return dados.carregar(caminho_precos, caminho_condicoes)


def carregar_catalogo():
    ficheiros = erse.ficheiros_locais(str(PASTA_DADOS))
    if not ficheiros:
        return None
    precos, condicoes = ficheiros
    versao = max(os.path.getmtime(precos), os.path.getmtime(condicoes))
    return _carregar(precos, condicoes, versao)


def descarregar(mostrar_erro: bool = True) -> bool:
    """Vai ao site da ERSE buscar o ZIP e extrai os CSV. True se correu bem."""
    try:
        with st.spinner("A obter as ofertas comerciais no site da ERSE..."):
            info = erse.atualizar(str(PASTA_DADOS))
    except erse.ErroERSE as erro:
        if mostrar_erro:
            st.session_state["erro_descarga"] = str(erro)
        return False
    except Exception as erro:  # rede, disco, o que for
        if mostrar_erro:
            st.session_state["erro_descarga"] = (
                "Não foi possível descarregar os dados automaticamente.\n\n"
                f"Motivo: {erro}"
            )
        return False
    st.session_state["erro_descarga"] = ""
    st.session_state["info"] = info
    _carregar.clear()
    return True


def guardar_zip_enviado(conteudo: bytes) -> bool:
    try:
        erse.guardar_zip_manual(conteudo, str(PASTA_DADOS))
    except erse.ErroERSE as erro:
        st.error(str(erro), icon="⚠️")
        return False
    _carregar.clear()
    st.session_state["erro_descarga"] = ""
    return True


def painel_erro(motivo: str) -> None:
    """Explica ao utilizador como colocar os ficheiros à mão."""
    st.error(motivo, icon="⚠️")
    st.markdown(
        f"""
### Como resolver, demora menos de um minuto

1. Abra **[{erse.SITE}]({erse.SITE})**
2. Na página inicial carregue em **Ofertas comerciais (CSV)** e guarde o ficheiro ZIP
3. Volte aqui e escolha esse ZIP na caixa abaixo

Em alternativa, extraia o ZIP e copie os dois ficheiros
`{erse.NOME_PRECOS}` e `{erse.NOME_CONDICOES}` para esta pasta:

`{PASTA_DADOS}`
"""
    )
    coluna_zip, coluna_csv = st.columns(2)
    with coluna_zip:
        enviado = st.file_uploader(
            "Ficheiro ZIP descarregado do site", type=["zip"], key="envio_zip"
        )
        if enviado is not None and guardar_zip_enviado(enviado.getvalue()):
            st.success("Ficheiros guardados.")
            st.rerun()
    with coluna_csv:
        pares = st.file_uploader(
            "Ou os dois ficheiros CSV já extraídos",
            type=["csv"],
            accept_multiple_files=True,
            key="envio_csv",
        )
        if pares and len(pares) == 2:
            escolhidos: dict[str, bytes | None] = {"precos": None, "condicoes": None}
            for ficheiro in pares:
                alvo = "condicoes" if "cond" in ficheiro.name.lower() else "precos"
                escolhidos[alvo] = ficheiro.getvalue()
            if escolhidos["precos"] and escolhidos["condicoes"]:
                erse.guardar_csv_manual(
                    escolhidos["precos"], escolhidos["condicoes"], str(PASTA_DADOS)
                )
                _carregar.clear()
                st.session_state["erro_descarga"] = ""
                st.success("Ficheiros guardados.")
                st.rerun()
            else:
                st.warning(
                    "Escolha o ficheiro de preços e o das condições comerciais."
                )

    if st.button("Tentar descarregar outra vez", type="primary"):
        descarregar()
        st.rerun()


# --------------------------------------------------------------- apresentar


def cabecalho(info: dict) -> None:
    publicado = info.get("publicado") or "data desconhecida"
    descarregado = info.get("descarregado") or "-"
    st.markdown(
        f"""
<div class="cabecalho">
  <h1>⚡ {TITULO}</h1>
  <p>{SUBTITULO}</p>
  <span class="etiqueta">Preços publicados em {publicado} &nbsp;·&nbsp;
  dados obtidos em {descarregado}</span>
</div>
""",
        unsafe_allow_html=True,
    )


def euros(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}".replace(",", " ").replace(".", ",")
    return f"{texto} €"


def numero(valor: float, casas: int = 4) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _quinze_mais_baratas(tabela: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """As quinze ofertas mais baratas, ja com a etiqueta pronta para o eixo."""
    escolhidas = tabela.copy()
    escolhidas["etiqueta"] = (
        escolhidas["marca"] + " · " + escolhidas["proposta"].astype(str)
    )
    # Ha propostas diferentes com o mesmo nome comercial. Sem esta limpeza o
    # Altair juntava-as na mesma marca e somava os valores.
    escolhidas = (
        escolhidas.sort_values(coluna)
        .drop_duplicates(subset="etiqueta")
        .head(15)
        .reset_index(drop=True)
    )
    escolhidas["ordem"] = range(len(escolhidas))
    return escolhidas


def _eixo_y():
    return alt.Y(
        "etiqueta:N",
        sort=alt.EncodingSortField(field="ordem", order="ascending"),
        title=None,
        axis=alt.Axis(
            labelLimit=520, labelColor=COR_TEXTO, labelFontSize=12, tickSize=0
        ),
    )


def _dicas(coluna: str, unidade: str, formato: str) -> list:
    return [
        alt.Tooltip("marca:N", title="Comercializador"),
        alt.Tooltip("proposta:N", title="Proposta"),
        alt.Tooltip(f"{coluna}:Q", title=unidade, format=formato),
    ]


def grafico_barras(
    tabela: pd.DataFrame,
    coluna: str,
    titulo: str,
    cor: str,
    unidade: str,
    casas: int = 4,
):
    """Barras horizontais, uma série só, da mais barata para a mais cara."""
    grafico_dados = _quinze_mais_baratas(tabela, coluna)
    formato = f",.{casas}f"

    base = alt.Chart(grafico_dados).encode(
        y=_eixo_y(),
        x=alt.X(
            f"{coluna}:Q",
            title=unidade,
            scale=alt.Scale(nice=True),
            axis=alt.Axis(
                grid=True,
                gridColor="#EDF0F3",
                domain=False,
                tickSize=0,
                labelColor=COR_SUAVE,
                titleColor=COR_SUAVE,
            ),
        ),
        tooltip=_dicas(coluna, unidade, formato),
    )
    barras = base.mark_bar(size=15, cornerRadiusEnd=4, color=cor)
    valores = base.mark_text(align="left", dx=6, color=COR_SUAVE, fontSize=11).encode(
        text=alt.Text(f"{coluna}:Q", format=formato)
    )
    return (
        (barras + valores)
        .properties(height=max(220, 30 * len(grafico_dados)), title=titulo)
        .configure_view(stroke=None)
        .configure_title(fontSize=14, color=COR_TEXTO, anchor="start", dy=-6)
    )


def grafico_pontos(
    tabela: pd.DataFrame, coluna: str, titulo: str, cor: str, unidade: str
):
    """
    Precos unitarios variam pouco entre ofertas. Em barras a partir do zero as
    diferencas desapareciam, por isso usa-se um ponto por oferta, onde uma
    escala que nao comeca no zero continua a ser honesta.
    """
    pontos_dados = _quinze_mais_baratas(tabela, coluna)
    minimo = float(pontos_dados[coluna].min())
    maximo = float(pontos_dados[coluna].max())
    folga = max((maximo - minimo) * 0.18, maximo * 0.01)
    escala = alt.Scale(domain=[minimo - folga, maximo + folga], nice=False)

    base = alt.Chart(pontos_dados).encode(
        y=_eixo_y(),
        x=alt.X(
            f"{coluna}:Q",
            title=unidade,
            scale=escala,
            axis=alt.Axis(
                grid=True,
                gridColor="#EDF0F3",
                domain=False,
                tickSize=0,
                format=",.4f",
                labelColor=COR_SUAVE,
                titleColor=COR_SUAVE,
            ),
        ),
        tooltip=_dicas(coluna, unidade, ",.4f"),
    )
    linha = base.mark_rule(color="#D6DCE2", size=2).encode(
        x=alt.X(f"{coluna}:Q", scale=escala), x2=alt.datum(minimo - folga)
    )
    marcas = base.mark_circle(size=110, color=cor, stroke="#FFFFFF", strokeWidth=2)
    valores = base.mark_text(align="left", dx=10, color=COR_SUAVE, fontSize=11).encode(
        text=alt.Text(f"{coluna}:Q", format=",.4f")
    )
    return (
        (linha + marcas + valores)
        .properties(height=max(220, 30 * len(pontos_dados)), title=titulo)
        .configure_view(stroke=None)
        .configure_title(fontSize=14, color=COR_TEXTO, anchor="start", dy=-6)
    )


# --------------------------------------------------------------- filtros


def filtros_comuns(catalogo: dados.Catalogo, energia: str, chave: str) -> dict:
    """Linha de filtros partilhada pelas tabelas e pelo simulador."""
    restricoes = [
        "Apenas ofertas em vigor hoje",
        "Excluir ofertas só para novos clientes",
    ]
    predefinidas = ["Apenas ofertas em vigor hoje"]
    if energia == "ele":
        restricoes += ["Excluir preços indexados", "Apenas energia renovável"]
        predefinidas += ["Excluir preços indexados"]

    disponiveis = catalogo.comercializadores(energia)
    principais = [m for m in dados.PRINCIPAIS if m in disponiveis]

    coluna1, coluna2, coluna3 = st.columns([1, 3, 2.4])
    with coluna1:
        segmento = st.selectbox(
            "Segmento",
            ["Dom", "Ndom", "Todos"],
            format_func=lambda s: dados.SEGMENTOS.get(s, s),
            key=f"seg_{chave}",
        )
    with coluna2:
        marcas = st.multiselect(
            "Comercializadores",
            disponiveis,
            default=principais,
            placeholder="Todos",
            key=f"com_{chave}",
        )
    with coluna3:
        opcoes = st.multiselect(
            "Restrições",
            restricoes,
            default=predefinidas,
            key=f"opc_{chave}",
        )

    filtros = {
        "segmento": segmento,
        "comercializadores": marcas,
        "so_ativas": "Apenas ofertas em vigor hoje" in opcoes,
        "sem_so_novos_clientes": "Excluir ofertas só para novos clientes" in opcoes,
    }
    if energia == "ele":
        filtros["sem_indexadas"] = "Excluir preços indexados" in opcoes
        filtros["so_renovavel"] = "Apenas energia renovável" in opcoes
    return filtros


# --------------------------------------------------------------- tabelas


def destaque_mais_barata(linhas: list[str], gas: bool = False) -> None:
    classe = "vencedor gas" if gas else "vencedor"
    corpo = "".join(f'<div class="linha">{texto}</div>' for texto in linhas)
    st.markdown(
        f'<div class="{classe}"><div class="titulo">Energia mais barata</div>'
        f"{corpo}</div>",
        unsafe_allow_html=True,
    )


def mais_baratas_por_potencia(
    catalogo: dados.Catalogo, contagem: int, potencias: list[float], filtros: dict
) -> list[str]:
    """Uma frase por potencia a dizer qual e a oferta com energia mais barata."""
    frases = []
    for potencia in potencias:
        tabela = catalogo.tabela_ele(potencia, contagem, **filtros)
        melhor = dados.mais_barata(tabela, "preco_1")
        if melhor is None:
            continue
        frases.append(
            f'<span class="kva">{dados.rotulo_potencia(potencia)} kVA</span> '
            f'<span class="marca">{melhor["marca"]}</span> · {melhor["proposta"]} '
            f'— <span class="preco">{numero(melhor["preco_1"])} €/kWh</span>'
        )
    return frases


def mostrar_comparativa(tabela: pd.DataFrame, potencias: list[float]) -> None:
    rotulos = [dados.rotulo_potencia(p) for p in potencias]
    config = {
        "Comercializador": st.column_config.TextColumn(
            "Comercializador", width="medium"
        ),
        "Componente": st.column_config.TextColumn("Componente", width="medium"),
    }
    for rotulo in rotulos:
        config[rotulo] = st.column_config.TextColumn(
            rotulo, help=f"Potência contratada de {rotulo} kVA", width="small"
        )
    # O Styler trata da virgula decimal, que o formato do column_config nao faz.
    estilo = tabela.style.format("{:.4f}", subset=rotulos, decimal=",", na_rep="—")
    st.dataframe(
        estilo,
        column_config=config,
        hide_index=True,
        width="stretch",
        height=min(45 + 35 * len(tabela), 900),
    )


def mostrar_todas_ele(tabela: pd.DataFrame, contagem: int) -> None:
    colunas = ["marca", "proposta", "termo_fixo"]
    config = {
        "marca": st.column_config.TextColumn("Comercializador", width="medium"),
        "proposta": st.column_config.TextColumn("Proposta", width="large"),
        "termo_fixo": st.column_config.NumberColumn(
            "€/dia",
            help="Termo fixo de potência, em euros por dia",
            format="%.4f",
            width="small",
        ),
    }
    for coluna, nome in zip(["preco_1", "preco_2", "preco_3"], dados.PERIODOS[contagem]):
        colunas.append(coluna)
        config[coluna] = st.column_config.NumberColumn(
            nome,
            help="Preço da energia, em euros por kWh",
            format="%.4f",
            width="small",
        )
    colunas += ["indexada", "renovavel", "duracao", "segmento_nome", "link_oferta"]
    config.update(
        {
            "indexada": st.column_config.CheckboxColumn("Indexada", width="small"),
            "renovavel": st.column_config.CheckboxColumn("Renovável", width="small"),
            "duracao": st.column_config.TextColumn("Meses", width="small"),
            "segmento_nome": st.column_config.TextColumn("Segmento", width="small"),
            "link_oferta": st.column_config.LinkColumn(
                "Oferta", display_text="abrir", width="small"
            ),
        }
    )
    st.dataframe(
        tabela[colunas],
        column_config=config,
        hide_index=True,
        width="stretch",
        height=min(45 + 35 * len(tabela), 560),
    )


def mostrar_tabela_gn(tabela: pd.DataFrame) -> None:
    colunas = ["marca", "proposta", "termo_fixo", "energia", "duracao", "link_oferta"]
    config = {
        "marca": st.column_config.TextColumn("Comercializador", width="medium"),
        "proposta": st.column_config.TextColumn("Proposta", width="large"),
        "termo_fixo": st.column_config.NumberColumn(
            "€/dia",
            help="Termo fixo, em euros por dia",
            format="%.4f",
            width="small",
        ),
        "energia": st.column_config.NumberColumn(
            "Energia",
            help="Preço da energia, em euros por kWh",
            format="%.4f",
            width="small",
        ),
        "duracao": st.column_config.TextColumn("Meses", width="small"),
        "link_oferta": st.column_config.LinkColumn(
            "Oferta", display_text="abrir", width="small"
        ),
    }
    if tabela["regiao"].astype(str).str.strip().any():
        colunas.insert(2, "regiao")
        config["regiao"] = st.column_config.TextColumn("Região", width="small")
    st.dataframe(
        tabela[colunas],
        column_config=config,
        hide_index=True,
        width="stretch",
        height=min(45 + 35 * len(tabela), 560),
    )


def descarregar_tabela(tabela: pd.DataFrame, nome: str, chave: str) -> None:
    csv = tabela.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(
        "Guardar esta tabela em CSV",
        csv,
        file_name=nome,
        mime="text/csv",
        key=chave,
    )


# --------------------------------------------------------------- eletricidade


def separador_eletricidade(catalogo: dados.Catalogo) -> None:
    st.subheader("Preços de eletricidade")

    disponiveis = catalogo.potencias()
    habituais = [p for p in dados.POTENCIAS_HABITUAIS if p in disponiveis]
    coluna1, coluna2 = st.columns([1.2, 2.5])
    with coluna1:
        contagem = st.radio(
            "Ciclo de contagem",
            catalogo.contagens(),
            format_func=lambda c: dados.NOMES_CICLO[c],
            horizontal=True,
            key="cic_tab",
        )
    with coluna2:
        potencias = st.multiselect(
            "Potências contratadas (kVA)",
            disponiveis,
            default=habituais,
            format_func=dados.rotulo_potencia,
            key="pot_tab",
        )
    if not potencias:
        st.warning("Escolha pelo menos uma potência.")
        return

    filtros = filtros_comuns(catalogo, "ele", "ele")

    frases = mais_baratas_por_potencia(catalogo, contagem, potencias, filtros)
    if frases:
        destaque_mais_barata(frases)

    comparativa = dados.tabela_comparativa(catalogo, contagem, potencias, **filtros)
    if comparativa.empty:
        st.warning("Não há ofertas com estes filtros. Alargue os critérios.")
        return

    st.caption(
        "Em cada potência é mostrada a proposta mais barata de cada "
        "comercializador, escolhida pelo preço da energia."
    )
    mostrar_comparativa(comparativa, potencias)
    descarregar_tabela(comparativa, "precos_eletricidade.csv", "csv_ele")

    with st.expander("Ver a proposta por trás de cada valor"):
        detalhe = dados.propostas_das_marcas(catalogo, contagem, potencias, **filtros)
        if detalhe.empty:
            st.info("Sem propostas para mostrar.")
        else:
            st.dataframe(
                detalhe[["marca", "potencia_rotulo", "proposta", "link_oferta"]],
                column_config={
                    "marca": st.column_config.TextColumn(
                        "Comercializador", width="medium"
                    ),
                    "potencia_rotulo": st.column_config.TextColumn(
                        "kVA", width="small"
                    ),
                    "proposta": st.column_config.TextColumn("Proposta", width="large"),
                    "link_oferta": st.column_config.LinkColumn(
                        "Oferta", display_text="abrir", width="small"
                    ),
                },
                hide_index=True,
                width="stretch",
                height=420,
            )

    referencia = potencias[0]
    rotulo = dados.rotulo_potencia(referencia)
    with st.expander(f"Ver todas as ofertas em {rotulo} kVA"):
        todas = catalogo.tabela_ele(referencia, contagem, **filtros)
        if todas.empty:
            st.info("Sem ofertas para esta potência.")
        else:
            mostrar_todas_ele(todas, contagem)
            st.altair_chart(
                grafico_pontos(
                    todas,
                    "preco_1",
                    f"Energia mais barata · {rotulo} kVA",
                    COR_ELE,
                    "€/kWh",
                ),
                width="stretch",
            )


# --------------------------------------------------------------- gas natural


def separador_gas(catalogo: dados.Catalogo) -> None:
    st.subheader("Preços de gás natural")
    escaloes = catalogo.escaloes()
    escalao = st.selectbox(
        "Escalão de consumo",
        escaloes,
        format_func=lambda e: dados.ESCALOES_GN.get(e, f"Escalão {e}"),
        key="esc_tab",
    )
    filtros = filtros_comuns(catalogo, "gn", "gn")
    tabela = catalogo.tabela_gn(escalao, **filtros)

    if st.checkbox(
        "Mostrar só a oferta mais barata de cada comercializador",
        value=True,
        key="mb_gn",
    ):
        tabela = dados.melhor_por_comercializador(tabela, "energia")

    if tabela.empty:
        st.warning("Não há ofertas com estes filtros. Alargue os critérios.")
        return

    melhor = dados.mais_barata(tabela, "energia")
    if melhor is not None:
        termo = melhor["termo_fixo"]
        destaque_mais_barata(
            [
                f'<span class="marca">{melhor["marca"]}</span> · '
                f'{melhor["proposta"]} — '
                f'<span class="preco">{numero(melhor["energia"])} €/kWh</span>'
                + (f" e {numero(termo)} €/dia de termo fixo" if pd.notna(termo) else "")
            ],
            gas=True,
        )

    mostrar_tabela_gn(tabela)
    st.altair_chart(
        grafico_pontos(
            tabela, "energia", "Preço de energia mais baixo", COR_GN, "€/kWh"
        ),
        width="stretch",
    )
    descarregar_tabela(tabela, "precos_gas_natural.csv", "csv_gn")


# --------------------------------------------------------------- simulador


def podio(resultado: pd.DataFrame) -> None:
    lugares = ["Mais barata", "2.º lugar", "3.º lugar"]
    mais_cara = resultado["total"].max()
    for indice, coluna in enumerate(st.columns(3)):
        if indice >= len(resultado):
            break
        linha = resultado.iloc[indice]
        poupanca = mais_cara - linha["total"]
        with coluna:
            st.markdown(
                f"""
<div class="podio {'vencedora' if indice == 0 else ''}">
  <div class="lugar">{lugares[indice]}</div>
  <div class="marca">{linha['marca']}</div>
  <div class="nome">{linha['proposta']}</div>
  <div class="valor">{euros(linha['total'])}
    <span class="unidade">no período</span></div>
  <div class="unidade">{euros(linha['media_mensal'])} por mês</div>
  <div class="poupanca">poupa {euros(poupanca)} face à mais cara</div>
</div>
""",
                unsafe_allow_html=True,
            )


def mostrar_resultado_simulacao(resultado: pd.DataFrame, cor: str) -> None:
    colunas = [
        "marca",
        "proposta",
        "total",
        "media_mensal",
        "custo_energia",
        "custo_potencia",
        "iva",
        "link_oferta",
    ]
    config = {
        "marca": st.column_config.TextColumn("Comercializador", width="medium"),
        "proposta": st.column_config.TextColumn("Proposta", width="large"),
        "total": st.column_config.NumberColumn("Total €", format="%.2f"),
        "media_mensal": st.column_config.NumberColumn("Por mês €", format="%.2f"),
        "custo_energia": st.column_config.NumberColumn("Energia €", format="%.2f"),
        "custo_potencia": st.column_config.NumberColumn("Potência €", format="%.2f"),
        "iva": st.column_config.NumberColumn("IVA €", format="%.2f"),
        "link_oferta": st.column_config.LinkColumn(
            "Oferta", display_text="abrir", width="small"
        ),
    }
    st.dataframe(
        resultado[colunas],
        column_config=config,
        hide_index=True,
        width="stretch",
        height=min(45 + 35 * len(resultado), 560),
    )
    st.altair_chart(
        grafico_barras(
            resultado,
            "total",
            "As ofertas mais baratas",
            cor,
            "€ no período",
            casas=2,
        ),
        width="stretch",
    )


def simulador_eletricidade(catalogo: dados.Catalogo) -> None:
    potencias = catalogo.potencias()
    coluna1, coluna2, coluna3 = st.columns(3)
    with coluna1:
        potencia = st.selectbox(
            "Potência contratada (kVA)",
            potencias,
            index=potencias.index(6.9) if 6.9 in potencias else 0,
            format_func=dados.rotulo_potencia,
            key="pot_sim",
        )
    with coluna2:
        contagens = catalogo.contagens(potencia)
        contagem = st.selectbox(
            "Ciclo de contagem",
            contagens,
            format_func=lambda c: dados.NOMES_CICLO[c],
            key="cic_sim",
        )
    with coluna3:
        meses = st.number_input(
            "Período a simular (meses)",
            min_value=1,
            max_value=24,
            value=1,
            step=1,
            key="mes_sim",
        )

    st.markdown("**Consumo no período**")
    nomes = dados.PERIODOS[contagem]
    predefinidos = {1: [300.0], 2: [180.0, 120.0], 3: [90.0, 130.0, 80.0]}[contagem]
    consumos = []
    for coluna, nome, valor in zip(st.columns(len(nomes)), nomes, predefinidos):
        with coluna:
            consumos.append(
                st.number_input(
                    f"{nome} (kWh)",
                    min_value=0.0,
                    value=float(valor) * meses,
                    step=10.0,
                    key=f"kwh_{contagem}_{nome}",
                )
            )

    with st.expander("Impostos e encargos"):
        coluna1, coluna2, coluna3, coluna4 = st.columns(4)
        iva = coluna1.number_input(
            "IVA (%)", 0.0, 30.0, dados.IVA_NORMAL, 0.5, key="iva_ele"
        )
        reduzido = coluna2.checkbox(
            f"IVA a {dados.IVA_REDUZIDO:.0f}% na potência até "
            f"{dados.rotulo_potencia(dados.POTENCIA_IVA_REDUZIDO)} kVA",
            value=True,
            key="ivared_ele",
        )
        cav = coluna3.number_input(
            "Contribuição audiovisual (€/mês)",
            0.0,
            20.0,
            dados.CAV_MENSAL,
            0.05,
            key="cav_ele",
        )
        dgeg = coluna4.number_input(
            "Taxa DGEG (€/mês)", 0.0, 20.0, dados.DGEG_MENSAL, 0.01, key="dgeg_ele"
        )

    filtros = filtros_comuns(catalogo, "ele", "simele")
    so_melhor = st.checkbox(
        "Mostrar só a oferta mais barata de cada comercializador",
        value=True,
        key="mb_simele",
    )
    dias = int(round(DIAS_POR_MES * meses))
    tabela = catalogo.tabela_ele(potencia, contagem, **filtros)
    resultado = dados.simular_ele(
        tabela,
        potencia=potencia,
        contagem=contagem,
        dias=dias,
        consumos=consumos,
        iva=iva,
        iva_reduzido_potencia=reduzido,
        cav=cav,
        dgeg=dgeg,
        meses=float(meses),
    )
    if so_melhor:
        resultado = dados.melhor_por_comercializador(resultado, "total")
    if resultado.empty:
        st.warning("Não há ofertas com estes filtros. Alargue os critérios.")
        return

    st.caption(
        f"{len(resultado)} ofertas simuladas para {dias} dias "
        f"({meses} {'meses' if meses > 1 else 'mês'}) e {sum(consumos):.0f} kWh."
    )
    podio(resultado)
    st.write("")
    mostrar_resultado_simulacao(resultado, COR_ELE)
    descarregar_tabela(resultado, "simulacao_eletricidade.csv", "csv_simele")


def simulador_gas(catalogo: dados.Catalogo) -> None:
    escaloes = catalogo.escaloes()
    coluna1, coluna2, coluna3 = st.columns(3)
    with coluna1:
        escalao = st.selectbox(
            "Escalão de consumo",
            escaloes,
            format_func=lambda e: dados.ESCALOES_GN.get(e, f"Escalão {e}"),
            key="esc_sim",
        )
    with coluna2:
        meses = st.number_input(
            "Período a simular (meses)",
            min_value=1,
            max_value=24,
            value=1,
            step=1,
            key="mes_simgn",
        )
    with coluna3:
        kwh = st.number_input(
            "Consumo no período (kWh)",
            min_value=0.0,
            value=150.0 * meses,
            step=10.0,
            key="kwh_gn",
        )

    with st.expander("Impostos e encargos"):
        coluna1, coluna2, coluna3 = st.columns(3)
        iva = coluna1.number_input(
            "IVA (%)", 0.0, 30.0, dados.IVA_NORMAL, 0.5, key="iva_gn"
        )
        reduzido = coluna2.checkbox(
            f"IVA a {dados.IVA_REDUZIDO:.0f}% no termo fixo do escalão 1",
            value=True,
            key="ivared_gn",
        )
        encargos = coluna3.number_input(
            "Outros encargos (€/mês)", 0.0, 20.0, 0.0, 0.01, key="enc_gn"
        )

    filtros = filtros_comuns(catalogo, "gn", "simgn")
    so_melhor = st.checkbox(
        "Mostrar só a oferta mais barata de cada comercializador",
        value=True,
        key="mb_simgn",
    )
    dias = int(round(DIAS_POR_MES * meses))
    tabela = catalogo.tabela_gn(escalao, **filtros)
    resultado = dados.simular_gn(
        tabela,
        escalao=escalao,
        dias=dias,
        kwh=kwh,
        iva=iva,
        iva_reduzido_termo_fixo=reduzido,
        encargos=encargos,
        meses=float(meses),
    )
    if so_melhor:
        resultado = dados.melhor_por_comercializador(resultado, "total")
    if resultado.empty:
        st.warning("Não há ofertas com estes filtros. Alargue os critérios.")
        return

    st.caption(f"{len(resultado)} ofertas simuladas para {dias} dias e {kwh:.0f} kWh.")
    podio(resultado)
    st.write("")
    mostrar_resultado_simulacao(resultado, COR_GN)
    descarregar_tabela(resultado, "simulacao_gas_natural.csv", "csv_simgn")


def separador_simulador(catalogo: dados.Catalogo) -> None:
    st.subheader("Simulador de fatura")
    aba_ele, aba_gn = st.tabs(["⚡ Eletricidade", "🔥 Gás natural"])
    with aba_ele:
        simulador_eletricidade(catalogo)
    with aba_gn:
        simulador_gas(catalogo)
    st.info(
        "Os valores são uma estimativa a partir dos preços publicados pela ERSE. "
        "A fatura final pode variar com descontos, serviços adicionais e acertos "
        "de leitura.",
        icon="ℹ️",
    )


# --------------------------------------------------------------- sobre


def detalhe_proposta(catalogo: dados.Catalogo) -> None:
    propostas = catalogo.condicoes.sort_values("proposta")
    etiquetas = {
        codigo: f"{dados.nome_comercializador(linha['com_codigo'])} · "
        f"{linha['proposta']}"
        for codigo, linha in propostas.iterrows()
    }
    escolhida = st.selectbox(
        "Proposta",
        list(etiquetas.keys()),
        format_func=lambda c: etiquetas[c],
        key="prop_detalhe",
    )
    linha = catalogo.condicoes.loc[escolhida]
    st.markdown(f"### {linha['proposta']}")
    st.write(linha["descricao"] or "-")
    detalhes = {
        "Comercializador": dados.nome_comercializador(linha["com_codigo"]),
        "Segmento": linha["segmento_nome"],
        "Fornecimento": linha["fornecimento"],
        "Duração do contrato": f"{linha['duracao']} meses",
        "Fidelização": linha["fidelizacao"],
        "Faturação": linha["faturacao"],
        "Pagamento": linha["pagamento"],
        "Atualização de preços": linha["atualizacao_precos"],
        "Telefone": linha["telefone"],
    }
    st.table(
        pd.DataFrame(
            {"Condição": list(detalhes.keys()), "Detalhe": list(detalhes.values())}
        ).set_index("Condição")
    )
    for etiqueta, campo in (
        ("Página da oferta", "link_oferta"),
        ("Ficha padronizada", "link_ficha"),
        ("Contacto", "contacto_web"),
    ):
        valor = str(linha[campo]).strip()
        if valor and valor.lower() not in ("na", "-", "nan"):
            st.markdown(f"- [{etiqueta}]({valor})")


def separador_sobre(catalogo: dados.Catalogo, info: dict) -> None:
    st.subheader("Sobre os dados")
    marcas = set(catalogo.comercializadores("ele")) | set(
        catalogo.comercializadores("gn")
    )
    coluna1, coluna2, coluna3 = st.columns(3)
    coluna1.metric("Propostas com eletricidade", catalogo.ele["codigo"].nunique())
    coluna2.metric("Propostas com gás natural", catalogo.gn["codigo"].nunique())
    coluna3.metric("Comercializadores", len(marcas))
    st.markdown(
        f"""
**Origem** [{erse.SITE}]({erse.SITE}) · secção *Ofertas comerciais (CSV)*

| | |
|---|---|
| Ficheiro descarregado | `{info.get('origem', '-')}` |
| Preços publicados em | {info.get('publicado') or 'desconhecido'} |
| Dados obtidos em | {info.get('descarregado', '-')} |
| Pasta local | `{PASTA_DADOS}` |

Do ZIP saem dois ficheiros: o `{erse.NOME_PRECOS}`, com os preços de cada
proposta, e o `{erse.NOME_CONDICOES}`, com as condições comerciais.
"""
    )
    with st.expander("Ver as condições comerciais de uma proposta"):
        detalhe_proposta(catalogo)


# --------------------------------------------------------------- barra lateral


def barra_lateral(info: dict) -> None:
    with st.sidebar:
        st.markdown("## ⚡ Comparador")
        st.caption("Dados do simulador de preços da ERSE")
        st.success(
            f"Preços de **{info.get('publicado') or 'data desconhecida'}**\n\n"
            f"Obtidos em {info.get('descarregado', '-')}",
            icon="✅",
        )
        if st.button("🔄 Atualizar dados agora", width="stretch"):
            descarregar()
            st.rerun()
        st.link_button("Abrir o site da ERSE", erse.SITE, width="stretch")
        with st.expander("Colocar os ficheiros à mão"):
            st.caption(
                "Se a descarga automática falhar, guarde aqui o ZIP do site.\n\n"
                f"Pasta: `{PASTA_DADOS}`"
            )
            enviado = st.file_uploader(
                "Ficheiro ZIP", type=["zip"], key="envio_zip_lateral"
            )
            if enviado is not None and guardar_zip_enviado(enviado.getvalue()):
                st.rerun()
        st.markdown(
            f'<div class="rodape">Fonte: ERSE · {_dt.date.today():%d/%m/%Y}<br>'
            "Aplicação sem qualquer ligação a comercializadores.</div>",
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------- principal


def obter_dados() -> tuple[object | None, str]:
    """Garante que ha dados, descarregando se for preciso. Devolve (catalogo, erro)."""
    if erse.ficheiros_locais(str(PASTA_DADOS)) is None:
        descarregar()
    elif not erse.dados_frescos(str(PASTA_DADOS)) and not st.session_state.get(
        "tentou_atualizar"
    ):
        # Uma tentativa por sessao, e so quando os ficheiros ja estao velhos.
        # Num servidor isto evita ir a ERSE a cada visitante que chega.
        st.session_state["tentou_atualizar"] = True
        descarregar(mostrar_erro=False)

    if erse.ficheiros_locais(str(PASTA_DADOS)) is None:
        return None, ""
    try:
        return carregar_catalogo(), ""
    except (ValueError, OSError, KeyError) as erro:
        return None, f"Os ficheiros existem mas não foi possível lê-los.\n\n{erro}"


def principal() -> None:
    st.session_state.setdefault("erro_descarga", "")

    catalogo, erro_leitura = obter_dados()
    info = st.session_state.get("info") or erse.ler_info(str(PASTA_DADOS))

    if catalogo is None:
        st.markdown(
            f'<div class="cabecalho"><h1>⚡ {TITULO}</h1><p>{SUBTITULO}</p></div>',
            unsafe_allow_html=True,
        )
        painel_erro(
            erro_leitura
            or st.session_state.get("erro_descarga")
            or "Ainda não há dados guardados nesta aplicação."
        )
        return

    barra_lateral(info)
    cabecalho(info)

    if st.session_state.get("erro_descarga"):
        st.warning(
            "Não foi possível atualizar os dados agora, está a ver a última "
            f"versão guardada.\n\n{st.session_state['erro_descarga']}",
            icon="⚠️",
        )

    aba_ele, aba_gn, aba_sim, aba_sobre = st.tabs(
        ["⚡ Eletricidade", "🔥 Gás natural", "🧮 Simulador", "📄 Dados"]
    )
    with aba_ele:
        separador_eletricidade(catalogo)
    with aba_gn:
        separador_gas(catalogo)
    with aba_sim:
        separador_simulador(catalogo)
    with aba_sobre:
        separador_sobre(catalogo, info)


principal()
