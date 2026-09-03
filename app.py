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
import re
import unicodedata
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

# Potencia que vem escolhida no simulador. E a mais comum nas casas pequenas e
# a unica com IVA reduzido no termo fixo.
POTENCIA_PREDEFINIDA = 3.45

# Litros de combustivel que vem no campo do Galp COMBINA. E o consumo de quem
# faz um deposito por mes num carro pequeno.
LITROS_PREDEFINIDOS = 40.0

# Compras no supermercado que vem no campo do Galp COMBINA. E sobre este valor
# que incide a percentagem do Continente, e nao sobre a fatura de energia.
COMPRAS_PREDEFINIDAS = 300.0

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

/* seccao do Galp COMBINA, no mesmo registo quente do gas natural */
.combina {
  border: 1px solid #F0D2B4; border-left: 5px solid #B54708; border-radius: 14px;
  background: #FDF7F1; padding: 18px 22px; margin: 4px 0 14px;
}
.combina .titulo {font-size: 0.75rem; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: #5B6472;}
.combina .nivel {font-size: 1.6rem; font-weight: 700; color: #B54708; margin-top: 2px;}
.combina .servicos {margin-top: 10px; display: flex; flex-wrap: wrap; gap: 8px;}
.combina .servico {
  font-size: 0.86rem; padding: 4px 12px; border-radius: 999px;
  background: #fff; border: 1px solid #F0D2B4; color: #10151F;
}
.combina .servico.nao {color: #8A93A0; border-color: #E4E7EC; background: #F6F8FA;}
.combina .beneficios {margin-top: 12px; font-size: 0.95rem; color: #10151F;
  line-height: 1.8;}
.combina .beneficios b {color: #B54708;}
.combina .fonte {margin-top: 10px; font-size: 0.82rem; color: #5B6472;}
.combina .fonte b {color: #10151F;}
.combina .seccao {
  margin-top: 18px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.8px;
  text-transform: uppercase; color: #B54708;
}
.combina .grelha {
  display: grid; gap: 10px; margin-top: 8px;
  grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
}
.combina .celula {
  background: #fff; border: 1px solid #F0D2B4; border-radius: 10px;
  padding: 10px 14px;
}
.combina .celula.destaque {border-color: #B54708; background: #FFF3E8;}
.combina .celula .rotulo {font-size: 0.72rem; letter-spacing: 0.4px;
  text-transform: uppercase; color: #5B6472;}
.combina .celula .valor {font-size: 1.2rem; font-weight: 700; color: #10151F;
  margin-top: 3px; line-height: 1.25;}
.combina .celula.destaque .valor {color: #B54708;}
.combina .celula .nota {font-size: 0.76rem; color: #5B6472; margin-top: 3px;}
.combina .celula[title] {cursor: help;}
.combina .celula[title] .rotulo {border-bottom: 1px dotted #C9A227;
  display: inline-block; padding-bottom: 1px;}
.combina .conta {
  margin-top: 14px; padding: 12px 16px; border-radius: 10px;
  background: #B54708; color: #fff; font-size: 1rem; font-weight: 600;
}
.combina .aviso {margin-top: 12px; font-size: 0.8rem; color: #5B6472;
  line-height: 1.55;}

div[data-testid="stMetricValue"] {font-size: 1.5rem;}
section[data-testid="stSidebar"] {background: #F6F8FA; border-right: 1px solid #E4E7EC;}
.rodape {color: #5B6472; font-size: 0.82rem; margin-top: 30px; line-height: 1.6;}

/* etiquetas dos filtros escolhidos, nos botoes que abrem os menus. A cor vem
   por estilo inline do Streamlit, por isso so se mexe na forma e no peso, que
   e o que as torna visiveis sem apagar a diferenca entre a cor da marca e o
   cinzento do "Nenhum". */
span.stMarkdownBadge {
  font-weight: 700 !important;
  border-radius: 6px !important;
  padding: 3px 9px !important;
  margin: 0 4px 0 0 !important;
  font-size: 0.8rem !important;
  letter-spacing: 0.2px;
  box-shadow: 0 1px 2px rgba(16, 21, 31, 0.12);
}
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


def _chave_caixa(chave: str, opcao) -> str:
    """
    Chave estavel para a caixa de uma opcao.

    Os acentos saem antes do resto, senao cada um virava um underscore e a
    chave ficava ilegivel, do genero "excluir_pre_os_indexados".
    """
    texto = unicodedata.normalize("NFKD", str(opcao))
    sem_acentos = "".join(letra for letra in texto if not unicodedata.combining(letra))
    limpo = re.sub(r"[^a-z0-9]+", "_", sem_acentos.lower()).strip("_")
    return f"{chave}__{limpo}"


def _marcar_caixas(chave: str, opcoes: list, escolhidas) -> None:
    """Callback dos botoes de atalho. Corre antes de as caixas serem criadas."""
    escolhidas = set(escolhidas)
    for opcao in opcoes:
        st.session_state[_chave_caixa(chave, opcao)] = opcao in escolhidas


def rotulo_escolhidas(
    opcoes: list,
    predefinidas: list,
    chave: str,
    formatar=str,
    maximo: int = 20,
    vazio: str = "Nenhum",
) -> str:
    """
    O que esta ligado, para o rotulo do menu.

    Sao etiquetas azuis, como as do multiselect. O botao nao quebra linha, por
    isso as que nao couberem ficam cortadas a direita: quem quiser ve-las todas
    abre o menu. O maximo e so uma travagem para o rotulo nao levar texto que
    nunca chega a ser desenhado.
    """
    ligadas = [
        opcao
        for opcao in opcoes
        if st.session_state.get(_chave_caixa(chave, opcao), opcao in predefinidas)
    ]
    if not ligadas:
        return f":gray-badge[{vazio}]"
    # Os parenteses retos partiriam a directiva do badge.
    nomes = [
        formatar(opcao).replace("[", "(").replace("]", ")") for opcao in ligadas[:maximo]
    ]
    etiquetas = " ".join(f":primary-badge[{nome}]" for nome in nomes)
    if len(ligadas) > maximo:
        etiquetas += f" :gray-badge[+{len(ligadas) - maximo}]"
    return etiquetas


def caixas(
    opcoes: list,
    predefinidas: list,
    chave: str,
    colunas: int = 3,
    formatar=str,
) -> list:
    """
    Uma caixa por opcao, em vez de um multiselect.

    Com muitas opcoes escolhidas o multiselect enche-se de etiquetas, cresce em
    altura e deixa de dar para ver o que esta ligado. Com caixas ve-se tudo de
    uma vez e liga-se e desliga-se cada uma no sitio.
    """
    escolhidas = []
    grelha = st.columns(colunas)
    for indice, opcao in enumerate(opcoes):
        # O valor de origem e semeado no estado em vez de ir no value=. Com os
        # dois, o Streamlit avisa em cada execucao que a chave tem um valor por
        # omissao e tambem e escrita pelos atalhos.
        chave_caixa = _chave_caixa(chave, opcao)
        if chave_caixa not in st.session_state:
            st.session_state[chave_caixa] = opcao in predefinidas
        with grelha[indice % colunas]:
            marcada = st.checkbox(formatar(opcao), key=chave_caixa)
        if marcada:
            escolhidas.append(opcao)
    return escolhidas


def atalhos_caixas(opcoes: list, predefinidas: list, chave: str) -> None:
    """Botoes para ligar tudo, desligar tudo ou voltar ao que vem de origem."""
    coluna1, coluna2, coluna3 = st.columns(3)
    coluna1.button(
        "Todos",
        key=f"todos_{chave}",
        on_click=_marcar_caixas,
        args=(chave, opcoes, opcoes),
        width="stretch",
    )
    coluna2.button(
        "Nenhum",
        key=f"nenhum_{chave}",
        on_click=_marcar_caixas,
        args=(chave, opcoes, []),
        width="stretch",
    )
    coluna3.button(
        "Habituais",
        key=f"repor_{chave}",
        on_click=_marcar_caixas,
        args=(chave, opcoes, predefinidas),
        width="stretch",
    )


def menu_caixas(
    rotulo: str,
    opcoes: list,
    predefinidas: list,
    chave: str,
    colunas: int = 1,
    formatar=str,
    atalhos: bool = False,
    ajuda: str | None = None,
    maximo: int = 20,
) -> list:
    """
    Um botao que abre com uma caixa por opcao la dentro.

    O botao mostra os filtros escolhidos, como o multiselect mostrava, mas em
    texto que nao cresce em altura. Quem quiser mexer abre e tem uma caixa por
    opcao, que era o que faltava ao multiselect: com muitas escolhidas as
    etiquetas enchiam a caixa e deixava de dar para navegar.
    """
    escolhidas = rotulo_escolhidas(opcoes, predefinidas, chave, formatar, maximo)
    with st.popover(escolhidas, width="stretch", wrap=False, help=rotulo):
        if ajuda:
            st.caption(ajuda)
        if atalhos:
            atalhos_caixas(opcoes, predefinidas, chave)
        return caixas(opcoes, predefinidas, chave, colunas, formatar)


def menu_escolha(opcoes: list, chave: str, formatar=str, ajuda: str | None = None):
    """
    O mesmo aspeto do menu_caixas, mas para escolha unica.

    Existe para o segmento nao ficar um selectbox no meio de dois menus, com
    outra altura e outra moldura.
    """
    atual = st.session_state.get(chave, opcoes[0])
    etiqueta = f":primary-badge[{formatar(atual)}]"
    with st.popover(etiqueta, width="stretch", wrap=False, help=ajuda):
        return st.radio(
            "Segmento",
            opcoes,
            format_func=formatar,
            key=chave,
            label_visibility="collapsed",
        )


def filtros_comuns(catalogo: dados.Catalogo, energia: str, chave: str) -> dict:
    """Linha de filtros partilhada pelas tabelas e pelo simulador."""
    restricoes = [
        "Apenas ofertas em vigor hoje",
        "Excluir ofertas só para novos clientes",
        "Excluir ofertas com condições de acesso",
    ]
    predefinidas = [
        "Apenas ofertas em vigor hoje",
        "Excluir ofertas só para novos clientes",
        "Excluir ofertas com condições de acesso",
    ]
    if energia == "ele":
        restricoes += ["Excluir preços indexados", "Apenas energia renovável"]
        predefinidas += ["Excluir preços indexados"]

    disponiveis = catalogo.comercializadores(energia)
    principais = [m for m in dados.PRINCIPAIS if m in disponiveis]

    coluna1, coluna2, coluna3 = st.columns([1.2, 2, 2])
    with coluna1:
        st.markdown("**Segmento**")
        segmento = menu_escolha(
            ["Dom", "Ndom", "Todos"],
            f"seg_{chave}",
            formatar=lambda s: dados.SEGMENTOS.get(s, s),
            ajuda="Doméstico, não doméstico ou os dois.",
        )
    with coluna2:
        st.markdown("**Restrições**")
        opcoes = menu_caixas(
            "Restrições",
            restricoes,
            predefinidas,
            f"opc_{chave}",
            ajuda=(
                "«Condições de acesso» são ofertas reservadas a quem pertence a "
                "alguma coisa: associados do ACP, clientes Vodafone ou Santander, "
                "sócios de clubes. Costumam ser das mais baratas da tabela, mas "
                "só valem se o caso se aplicar a si. A Galp COMBINA fica sempre "
                "na tabela: a condição dela é associar o Cartão Continente ao "
                "Mundo Galp, que é grátis e está aberto a qualquer pessoa."
            ),
        )
    with coluna3:
        st.markdown("**Comercializadores**")
        marcas = menu_caixas(
            "Comercializadores",
            disponiveis,
            principais,
            f"com_{chave}",
            colunas=2,
            atalhos=True,
            ajuda="Sem nenhum marcado aparecem todos.",
        )

    filtros = {
        "segmento": segmento,
        "comercializadores": marcas,
        "so_ativas": "Apenas ofertas em vigor hoje" in opcoes,
        "sem_so_novos_clientes": "Excluir ofertas só para novos clientes" in opcoes,
        "sem_restricoes": "Excluir ofertas com condições de acesso" in opcoes,
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
        st.markdown("**Potências contratadas (kVA)**")
        potencias = menu_caixas(
            "Potências",
            disponiveis,
            habituais,
            "pot_tab",
            colunas=3,
            formatar=dados.rotulo_potencia,
            atalhos=True,
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
        "preco_kwh",
        "preco_kwh_total",
        "custo_energia",
        "custo_potencia",
        "encargos",
        "iva",
        "link_oferta",
    ]
    config = {
        "marca": st.column_config.TextColumn("Comercializador", width="medium"),
        "proposta": st.column_config.TextColumn("Proposta", width="large"),
        "total": st.column_config.NumberColumn("Total €", format="%.2f"),
        "media_mensal": st.column_config.NumberColumn("Por mês €", format="%.2f"),
        "preco_kwh": st.column_config.NumberColumn(
            "€/kWh energia",
            format="%.4f",
            help="Só a energia, que é a parcela sobre a qual incidem os descontos.",
        ),
        "preco_kwh_total": st.column_config.NumberColumn(
            "€/kWh total",
            format="%.4f",
            help="A fatura inteira a dividir pelo consumo, incluindo termo fixo, "
            "contribuição audiovisual, taxa DGEG e IVA.",
        ),
        "custo_energia": st.column_config.NumberColumn("Energia €", format="%.2f"),
        "custo_potencia": st.column_config.NumberColumn("Potência €", format="%.2f"),
        "encargos": st.column_config.NumberColumn(
            "Encargos €",
            format="%.2f",
            help="Na eletricidade, a contribuição audiovisual e a taxa DGEG. "
            "No gás, os outros encargos que indicar. São iguais em todas as "
            "propostas e mudam-se em «Impostos e encargos».",
        ),
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


def campos_combina(sufixo: str) -> tuple[bool, float, float]:
    """
    Os campos extra que alimentam o Galp COMBINA.

    A eletricidade e o gas nao se perguntam aqui: saem da modalidade que o
    utilizador escolheu no simulador. O que falta e o NOS, que decide o nivel,
    e os dois valores sobre os quais incidem os beneficios.
    """
    coluna1, coluna2, coluna3 = st.columns([1, 1, 1])
    with coluna1:
        nos = st.checkbox(
            "Tem NOS em casa?",
            value=False,
            key=f"nos_{sufixo}",
            help="Conta como um serviço elegível para o Galp COMBINA.",
        )
    with coluna2:
        compras = st.number_input(
            "Compras no Continente (€/mês)",
            min_value=0.0,
            value=COMPRAS_PREDEFINIDAS,
            step=25.0,
            key=f"com_combina_{sufixo}",
            help=(
                f"O que gasta por mês no supermercado. A percentagem do "
                f"COMBINA incide sobre este valor e volta em saldo no Cartão "
                f"Continente, até {dados.COMBINA_MAX_COMPRAS:.0f} € por mês."
            ),
        )
    with coluna3:
        litros = st.number_input(
            "Combustível (L/mês)",
            min_value=0.0,
            value=LITROS_PREDEFINIDOS,
            step=5.0,
            key=f"lit_{sufixo}",
            help=(
                f"Contam até {dados.COMBINA_MAX_LITROS:.0f} L por mês. "
                f"O programa tem também um limite de "
                f"{dados.COMBINA_MAX_LITROS_ABASTECIMENTO:.0f} L por abastecimento."
            ),
        )
    return nos, float(litros), float(compras)


def _linha_servicos(servicos: dict) -> str:
    partes = []
    for chave, etiqueta in dados.NOMES_SERVICOS_COMBINA.items():
        tem = servicos.get(chave, False)
        classe = "servico" if tem else "servico nao"
        marca = "&#10003;" if tem else "&#10007;"
        partes.append(f'<span class="{classe}">{marca} {etiqueta}</span>')
    return "".join(partes)


def _preco_kwh(valor: float | None) -> str:
    return f"{numero(valor, 3)} €/kWh" if valor is not None else "—"


def _celula(rotulo: str, valor: str, nota: str = "", dica: str = "", forte=False):
    """Uma celula da grelha dentro do cartao COMBINA."""
    classe = "celula destaque" if forte else "celula"
    atributo = f' title="{dica}"' if dica else ""
    linha_nota = f'<div class="nota">{nota}</div>' if nota else ""
    return (
        f'<div class="{classe}"{atributo}>'
        f'<div class="rotulo">{rotulo}</div>'
        f'<div class="valor">{valor}</div>'
        f"{linha_nota}</div>"
    )


def _grelha(*celulas: str) -> str:
    return f'<div class="grelha">{"".join(celulas)}</div>'


def seccao_combina(combina: dict, origem: str = "", e_combina: bool = True) -> None:
    """
    A seccao Galp COMBINA, mostrada antes da comparacao entre operadoras.

    Vai toda num bloco de HTML, dentro do mesmo cartao, porque os componentes
    do Streamlit nao se conseguem por dentro de uma div nossa. As explicacoes
    que noutros sitios sao o help do componente aqui sao o title da celula, que
    o navegador mostra ao passar o rato.

    Todos os valores sao mensais, porque os limites do programa sao mensais.
    Sem servicos elegiveis a seccao nao aparece.
    """
    if not combina["elegivel"]:
        return

    percentagem = numero(combina["continente_percentagem"], 0)
    litros = f"{combina['litros']:,.0f}".replace(",", " ")
    litros_ok = f"{combina['litros_elegiveis']:,.0f}".replace(",", " ")
    kwh = f"{combina['kwh_total']:,.0f}".replace(",", " ")

    if origem and e_combina:
        fonte = f'<div class="fonte">Contas feitas sobre a proposta <b>{origem}</b>.</div>'
    elif origem:
        fonte = (
            f'<div class="fonte">Não há ofertas do Plano COMBINA com estes filtros. '
            f"As contas usam a proposta mais barata da tabela, <b>{origem}</b>, "
            f"só para dar ideia da ordem de grandeza.</div>"
        )
    else:
        fonte = ""

    precos = _grelha(
        _celula(
            "Preço normal",
            _preco_kwh(combina["preco_normal"]),
            "só a energia",
            "O preço da energia, sem termo fixo, contribuição audiovisual, "
            "taxa DGEG nem IVA. É sobre esta parcela que incide a percentagem "
            "do Continente.",
        ),
        _celula(
            "Com o saldo Continente",
            _preco_kwh(combina["preco_continente"]),
            "preço equivalente",
            "O custo da energia menos o saldo que volta no Cartão Continente, "
            "por kWh. É uma equivalência: o saldo gasta-se no supermercado, "
            "não abate na fatura de energia.",
        ),
        _celula(
            "Com Continente e Galp",
            _preco_kwh(combina["preco_equivalente"]),
            "preço equivalente",
            "Junta o saldo do Continente e a poupança em combustível. É uma "
            "métrica de comparação, nenhum dos dois abate na fatura de "
            "energia. Nunca desce abaixo de zero.",
            forte=True,
        ),
    )

    energia = _grelha(
        _celula("Consumo", f"{kwh} kWh", "por mês"),
        _celula(
            "Custo da energia",
            euros(combina["custo_energia"]),
            "por mês",
            "O preço por kWh vezes o consumo, sem termo fixo, encargos nem IVA.",
        ),
        _celula(
            "Fatura de energia",
            euros(combina["fatura_energia"]),
            "por mês",
            "A fatura toda desta proposta, já com termo fixo, encargos e IVA. "
            "É o valor que aparece na tabela das ofertas, mais abaixo.",
        ),
    )

    compras = _grelha(
        _celula("Compras", euros(combina["compras"]), "por mês"),
        _celula(
            "Compras elegíveis",
            euros(combina["compras_elegiveis"]),
            "contam para a percentagem",
            f"O programa conta até {euros(dados.COMBINA_MAX_COMPRAS)} de "
            f"compras por mês.",
        ),
        _celula("Percentagem", f"{percentagem}%", "do COMBINA " + str(combina["nivel"])),
        _celula(
            "Saldo no cartão",
            euros(combina["poupanca_continente"]),
            "por mês",
            f"{percentagem}% sobre as compras elegíveis. Volta em saldo no "
            f"Cartão Continente, não é abatido na fatura de energia.",
        ),
    )

    combustivel = _grelha(
        _celula("Combustível", f"{litros} L", "por mês"),
        _celula(
            "Litros elegíveis",
            f"{litros_ok} L",
            "contam para o desconto",
            f"O programa conta até {dados.COMBINA_MAX_LITROS:.0f} L por mês e "
            f"{dados.COMBINA_MAX_LITROS_ABASTECIMENTO:.0f} L por abastecimento.",
        ),
        _celula(
            "Desconto Galp",
            f"{numero(combina['galp_por_litro'], 2)} €/L",
            "no abastecimento",
        ),
        _celula(
            "Poupança Galp",
            euros(combina["poupanca_galp"]),
            "por mês",
            "Litros elegíveis vezes o desconto por litro.",
        ),
    )

    avisos = []
    if combina["continente_limitado"]:
        avisos.append(
            f"As compras passam os {euros(dados.COMBINA_MAX_COMPRAS)} elegíveis "
            f"por mês, por isso a percentagem foi aplicada só a esse valor."
        )
    if combina["litros_limitado"]:
        avisos.append(
            f"Introduziu {combina['litros']:.0f} L, mas só "
            f"{combina['litros_elegiveis']:.0f} L contam para o desconto."
        )
    avisos.append(
        "Nenhum dos dois benefícios sai da fatura de energia: um volta em saldo "
        "no Cartão Continente e o outro é desconto nos abastecimentos. A fatura "
        "que paga é a de cima. Os preços por kWh que descontam os benefícios "
        "servem para comparar o valor do pacote, não para prever o que vem no "
        "papel da fatura."
    )
    if combina["valor_final_negativo"]:
        avisos.append(
            "Aqui os benefícios ultrapassam a fatura de energia, daí o valor "
            "final aparecer negativo."
        )

    st.markdown(
        f"""
<div class="combina">
  <div class="titulo">Galp COMBINA</div>
  <div class="nivel">COMBINA {combina['nivel']}</div>
  <div class="servicos">{_linha_servicos(combina['servicos'])}</div>
  <div class="beneficios">
    <b>{percentagem}%</b> para o Cartão Continente
    &nbsp;&middot;&nbsp;
    <b>{numero(combina['galp_por_litro'], 2)} €/L</b> de desconto na Galp
  </div>
  {fonte}

  <div class="seccao">Preço da energia por kWh</div>
  {precos}

  <div class="seccao">A tua energia</div>
  {energia}

  <div class="seccao">As tuas compras no Continente</div>
  {compras}

  <div class="seccao">O teu combustível</div>
  {combustivel}

  <div class="seccao">Contas finais</div>
  {_grelha(
      _celula("Fatura de energia", euros(combina["fatura_energia"]), "por mês"),
      _celula("Poupança total", euros(combina["poupanca_total"]), "por mês"),
      _celula("Valor final", euros(combina["valor_final"]), "por mês", forte=True),
  )}
  <div class="conta">
    {euros(combina['fatura_energia'])}
    &minus; {euros(combina['poupanca_continente'])}
    &minus; {euros(combina['poupanca_galp'])}
    = {euros(combina['valor_final'])} por mês
  </div>

  <div class="aviso">{"<br>".join(avisos)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def entradas_ele(
    catalogo: dados.Catalogo, sufixo: str = "", meses: int | None = None
) -> dict:
    """Campos de eletricidade do simulador. Devolve o que simular_ele precisa."""
    potencias = catalogo.potencias()
    colunas = st.columns(2 if meses is not None else 3)
    with colunas[0]:
        potencia = st.selectbox(
            "Potência contratada (kVA)",
            potencias,
            index=(
                potencias.index(POTENCIA_PREDEFINIDA)
                if POTENCIA_PREDEFINIDA in potencias
                else 0
            ),
            format_func=dados.rotulo_potencia,
            key=f"pot_sim{sufixo}",
        )
    with colunas[1]:
        contagens = catalogo.contagens(potencia)
        contagem = st.selectbox(
            "Ciclo de contagem",
            contagens,
            format_func=lambda c: dados.NOMES_CICLO[c],
            key=f"cic_sim{sufixo}",
        )
    if meses is None:
        with colunas[2]:
            meses = st.number_input(
                "Período a simular (meses)",
                min_value=1,
                max_value=24,
                value=1,
                step=1,
                key=f"mes_sim{sufixo}",
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
                    key=f"kwh_{contagem}_{nome}{sufixo}",
                )
            )

    with st.expander("Impostos e encargos"):
        coluna1, coluna2, coluna3, coluna4 = st.columns(4)
        iva = coluna1.number_input(
            "IVA (%)", 0.0, 30.0, dados.IVA_NORMAL, 0.5, key=f"iva_ele{sufixo}"
        )
        reduzido = coluna2.checkbox(
            f"IVA a {dados.IVA_REDUZIDO:.0f}% na potência até "
            f"{dados.rotulo_potencia(dados.POTENCIA_IVA_REDUZIDO)} kVA",
            value=True,
            key=f"ivared_ele{sufixo}",
        )
        cav = coluna3.number_input(
            "Contribuição audiovisual (€/mês)",
            0.0,
            20.0,
            dados.CAV_MENSAL,
            0.05,
            key=f"cav_ele{sufixo}",
        )
        dgeg = coluna4.number_input(
            "Taxa DGEG (€/mês)",
            0.0,
            20.0,
            dados.DGEG_MENSAL,
            0.01,
            key=f"dgeg_ele{sufixo}",
        )

    return {
        "potencia": potencia,
        "contagem": contagem,
        "meses": int(meses),
        "consumos": consumos,
        "iva": iva,
        "iva_reduzido_potencia": reduzido,
        "cav": cav,
        "dgeg": dgeg,
    }


def resultado_ele(
    catalogo: dados.Catalogo, entradas: dict, filtros: dict, so_melhor: bool
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Corre a simulacao de eletricidade com as entradas ja recolhidas.

    Devolve a simulacao completa e a tabela a mostrar. A completa e precisa
    para a seccao COMBINA poder escolher a proposta certa, que muitas vezes nao
    e a mais barata da marca e por isso nao sobrevive ao filtro de uma oferta
    por comercializador.
    """
    meses = entradas["meses"]
    dias = int(round(DIAS_POR_MES * meses))
    tabela = catalogo.tabela_ele(entradas["potencia"], entradas["contagem"], **filtros)
    resultado = dados.simular_ele(
        tabela,
        potencia=entradas["potencia"],
        contagem=entradas["contagem"],
        dias=dias,
        consumos=entradas["consumos"],
        iva=entradas["iva"],
        iva_reduzido_potencia=entradas["iva_reduzido_potencia"],
        cav=entradas["cav"],
        dgeg=entradas["dgeg"],
        meses=float(meses),
    )
    mostrado = (
        dados.melhor_por_comercializador(resultado, "total") if so_melhor else resultado
    )
    return resultado, mostrado


def entradas_gn(
    catalogo: dados.Catalogo, sufixo: str = "", meses: int | None = None
) -> dict:
    """Campos de gas natural do simulador."""
    escaloes = catalogo.escaloes()
    colunas = st.columns(2 if meses is not None else 3)
    with colunas[0]:
        escalao = st.selectbox(
            "Escalão de consumo",
            escaloes,
            format_func=lambda e: dados.ESCALOES_GN.get(e, f"Escalão {e}"),
            key=f"esc_sim{sufixo}",
        )
    if meses is None:
        with colunas[1]:
            meses = st.number_input(
                "Período a simular (meses)",
                min_value=1,
                max_value=24,
                value=1,
                step=1,
                key=f"mes_simgn{sufixo}",
            )
    with colunas[-1]:
        kwh = st.number_input(
            "Consumo no período (kWh)",
            min_value=0.0,
            value=150.0 * meses,
            step=10.0,
            key=f"kwh_gn{sufixo}",
        )

    with st.expander("Impostos e encargos do gás"):
        coluna1, coluna2, coluna3 = st.columns(3)
        iva = coluna1.number_input(
            "IVA (%)", 0.0, 30.0, dados.IVA_NORMAL, 0.5, key=f"iva_gn{sufixo}"
        )
        reduzido = coluna2.checkbox(
            f"IVA a {dados.IVA_REDUZIDO:.0f}% no termo fixo do escalão 1",
            value=True,
            key=f"ivared_gn{sufixo}",
        )
        encargos = coluna3.number_input(
            "Outros encargos (€/mês)", 0.0, 20.0, 0.0, 0.01, key=f"enc_gn{sufixo}"
        )

    return {
        "escalao": escalao,
        "meses": int(meses),
        "kwh": kwh,
        "iva": iva,
        "iva_reduzido_termo_fixo": reduzido,
        "encargos": encargos,
    }


def resultado_gn(
    catalogo: dados.Catalogo, entradas: dict, filtros: dict, so_melhor: bool
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Corre a simulacao de gas natural. Ver resultado_ele para o porque do par."""
    meses = entradas["meses"]
    dias = int(round(DIAS_POR_MES * meses))
    tabela = catalogo.tabela_gn(entradas["escalao"], **filtros)
    resultado = dados.simular_gn(
        tabela,
        escalao=entradas["escalao"],
        dias=dias,
        kwh=entradas["kwh"],
        iva=entradas["iva"],
        iva_reduzido_termo_fixo=entradas["iva_reduzido_termo_fixo"],
        encargos=entradas["encargos"],
        meses=float(meses),
    )
    mostrado = (
        dados.melhor_por_comercializador(resultado, "total") if so_melhor else resultado
    )
    return resultado, mostrado


def _ancora_combina(resultado: pd.DataFrame, nos: bool, meses: int) -> dict:
    """
    A proposta em que a seccao COMBINA se baseia, ja em valores mensais.

    Procura a variante Dual com debito direto que corresponde ao NOS. Se o
    utilizador filtrou a Galp para fora da tabela, usa a oferta mais barata que
    restou e diz que o fez, para os numeros nao parecerem sair do nada.
    """
    vazia = {"fatura": 0.0, "energia": 0.0, "proposta": "", "e_combina": False}
    if resultado.empty:
        return vazia
    linha = dados.oferta_combina(resultado, nos=nos)
    e_combina = linha is not None
    if linha is None:
        linha = resultado.sort_values("total").iloc[0]
    return {
        "fatura": float(linha["media_mensal"]),
        "energia": float(linha["custo_energia"]) / max(meses, 1),
        "proposta": str(linha["proposta"]),
        "e_combina": e_combina,
    }


def simulador_eletricidade(catalogo: dados.Catalogo) -> None:
    entradas = entradas_ele(catalogo)
    nos, litros, compras = campos_combina("simele")
    filtros = filtros_comuns(catalogo, "ele", "simele")
    so_melhor = st.checkbox(
        "Mostrar só a oferta mais barata de cada comercializador",
        value=True,
        key="mb_simele",
    )
    completo, resultado = resultado_ele(catalogo, entradas, filtros, so_melhor)
    if resultado.empty:
        st.warning("Não há ofertas com estes filtros. Alargue os critérios.")
        return

    meses = entradas["meses"]
    consumos = entradas["consumos"]
    dias = int(round(DIAS_POR_MES * meses))
    plural = "meses" if meses > 1 else "mês"
    st.caption(
        f"{len(resultado)} ofertas simuladas para {dias} dias "
        f"({meses} {plural}) e {sum(consumos):.0f} kWh."
    )
    ancora = _ancora_combina(completo, nos, meses)
    seccao_combina(
        dados.simular_combina(
            eletricidade=True,
            nos=nos,
            fatura_ele=ancora["fatura"],
            energia_ele=ancora["energia"],
            kwh_ele=sum(consumos) / meses,
            litros=litros,
            compras=compras,
        ),
        ancora["proposta"],
        ancora["e_combina"],
    )
    podio(resultado)
    st.write("")
    mostrar_resultado_simulacao(resultado, COR_ELE)
    descarregar_tabela(resultado, "simulacao_eletricidade.csv", "csv_simele")


def simulador_gas(catalogo: dados.Catalogo) -> None:
    entradas = entradas_gn(catalogo)
    nos, litros, compras = campos_combina("simgn")
    filtros = filtros_comuns(catalogo, "gn", "simgn")
    so_melhor = st.checkbox(
        "Mostrar só a oferta mais barata de cada comercializador",
        value=True,
        key="mb_simgn",
    )
    completo, resultado = resultado_gn(catalogo, entradas, filtros, so_melhor)
    if resultado.empty:
        st.warning("Não há ofertas com estes filtros. Alargue os critérios.")
        return

    meses = entradas["meses"]
    kwh = entradas["kwh"]
    dias = int(round(DIAS_POR_MES * meses))
    st.caption(f"{len(resultado)} ofertas simuladas para {dias} dias e {kwh:.0f} kWh.")
    ancora = _ancora_combina(completo, nos, meses)
    seccao_combina(
        dados.simular_combina(
            gas=True,
            nos=nos,
            fatura_gas=ancora["fatura"],
            energia_gas=ancora["energia"],
            kwh_gas=kwh / meses,
            litros=litros,
            compras=compras,
        ),
        ancora["proposta"],
        ancora["e_combina"],
    )
    podio(resultado)
    st.write("")
    mostrar_resultado_simulacao(resultado, COR_GN)
    descarregar_tabela(resultado, "simulacao_gas_natural.csv", "csv_simgn")


def mostrar_resultado_dual(tabela: pd.DataFrame) -> None:
    """A tabela das duas energias somadas, uma linha por comercializador."""
    colunas = [
        "marca",
        "total",
        "media_mensal",
        "preco_kwh_ele",
        "preco_kwh_gn",
        "total_ele",
        "total_gn",
        "proposta_ele",
        "proposta_gn",
    ]
    config = {
        "marca": st.column_config.TextColumn("Comercializador", width="medium"),
        "total": st.column_config.NumberColumn("Total € (as duas)", format="%.2f"),
        "media_mensal": st.column_config.NumberColumn("Por mês €", format="%.2f"),
        "preco_kwh_ele": st.column_config.NumberColumn(
            "€/kWh eletricidade",
            format="%.4f",
            help="Só a energia elétrica, sem termo fixo, encargos nem IVA.",
        ),
        "preco_kwh_gn": st.column_config.NumberColumn(
            "€/kWh gás",
            format="%.4f",
            help="Só a energia do gás, sem termo fixo, encargos nem IVA.",
        ),
        "total_ele": st.column_config.NumberColumn("Eletricidade €", format="%.2f"),
        "total_gn": st.column_config.NumberColumn("Gás €", format="%.2f"),
        "proposta_ele": st.column_config.TextColumn(
            "Proposta eletricidade", width="large"
        ),
        "proposta_gn": st.column_config.TextColumn("Proposta gás", width="large"),
    }
    st.dataframe(
        tabela[colunas],
        column_config=config,
        hide_index=True,
        width="stretch",
        height=min(45 + 35 * len(tabela), 560),
    )
    st.altair_chart(
        grafico_barras(
            tabela,
            "total",
            "Os pacotes mais baratos com as duas energias",
            COR_ELE,
            "€ no período",
            casas=2,
        ),
        width="stretch",
    )


def simulador_ele_gas(catalogo: dados.Catalogo) -> None:
    """
    As duas energias ao mesmo tempo.

    Cada uma continua a ser simulada e comparada como nos outros separadores.
    O que se junta aqui e a fatura de energia, que soma as duas, e o Galp
    COMBINA, que com as duas energias ja parte do nivel 2.
    """
    meses = st.number_input(
        "Período a simular (meses)",
        min_value=1,
        max_value=24,
        value=1,
        step=1,
        key="mes_simeg",
        help="O mesmo período para as duas energias.",
    )

    st.markdown("#### ⚡ Eletricidade")
    ent_ele = entradas_ele(catalogo, sufixo="_eg", meses=int(meses))
    st.markdown("#### 🔥 Gás natural")
    ent_gn = entradas_gn(catalogo, sufixo="_eg", meses=int(meses))

    st.markdown("#### Outros serviços")
    nos, litros, compras = campos_combina("simeg")

    # Aqui nao ha o filtro de uma oferta por comercializador: a tabela junta as
    # duas energias e por isso ja e uma linha por comercializador.
    with st.expander("Filtros da eletricidade"):
        filtros_ele = filtros_comuns(catalogo, "ele", "simeleeg")
    with st.expander("Filtros do gás natural"):
        filtros_gn = filtros_comuns(catalogo, "gn", "simgneg")

    completo_ele, res_ele = resultado_ele(catalogo, ent_ele, filtros_ele, False)
    completo_gn, res_gn = resultado_gn(catalogo, ent_gn, filtros_gn, False)
    if res_ele.empty and res_gn.empty:
        st.warning("Não há ofertas com estes filtros. Alargue os critérios.")
        return

    ancora_ele = _ancora_combina(completo_ele, nos, int(meses))
    ancora_gn = _ancora_combina(completo_gn, nos, int(meses))
    fatura_ele = ancora_ele["fatura"]
    fatura_gn = ancora_gn["fatura"]
    st.markdown("**Fatura de energia por mês, somando as duas propostas Galp**")
    coluna1, coluna2, coluna3 = st.columns(3)
    coluna1.metric("Eletricidade", f"{euros(fatura_ele)}/mês")
    coluna2.metric("Gás natural", f"{euros(fatura_gn)}/mês")
    coluna3.metric("Energia", f"{euros(fatura_ele + fatura_gn)}/mês")

    origens = " · ".join(
        o for o in (ancora_ele["proposta"], ancora_gn["proposta"]) if o
    )
    seccao_combina(
        dados.simular_combina(
            eletricidade=not res_ele.empty,
            gas=not res_gn.empty,
            nos=nos,
            fatura_ele=fatura_ele,
            energia_ele=ancora_ele["energia"],
            kwh_ele=sum(ent_ele["consumos"]) / meses,
            fatura_gas=fatura_gn,
            energia_gas=ancora_gn["energia"],
            kwh_gas=ent_gn["kwh"] / meses,
            litros=litros,
            compras=compras,
        ),
        origens,
        ancora_ele["e_combina"] and ancora_gn["e_combina"],
    )

    dual = dados.juntar_ele_gn(completo_ele, completo_gn)
    if dual.empty:
        st.warning(
            "Nenhum comercializador tem as duas energias com estes filtros. "
            "Alargue os critérios para poder comparar pacotes."
        )
        return

    st.markdown("#### ⚡🔥 As duas energias, por comercializador")
    so_ele = set(completo_ele["marca"]) - set(dual["marca"])
    so_gn = set(completo_gn["marca"]) - set(dual["marca"])
    if so_ele or so_gn:
        st.caption(
            f"{len(dual)} comercializadores vendem as duas energias. "
            f"Ficaram de fora {len(so_ele)} que só têm eletricidade e "
            f"{len(so_gn)} que só têm gás, porque não dá para os comparar "
            f"num pacote das duas."
        )
    podio(dual)
    st.write("")
    mostrar_resultado_dual(dual)
    descarregar_tabela(dual, "simulacao_eletricidade_gas.csv", "csv_simeg")


def separador_simulador(catalogo: dados.Catalogo) -> None:
    st.subheader("Simulador de fatura")
    aba_ele, aba_gn, aba_eg = st.tabs(
        ["⚡ Eletricidade", "🔥 Gás natural", "⚡🔥 Eletricidade + Gás natural"]
    )
    with aba_ele:
        simulador_eletricidade(catalogo)
    with aba_gn:
        simulador_gas(catalogo)
    with aba_eg:
        simulador_ele_gas(catalogo)
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
