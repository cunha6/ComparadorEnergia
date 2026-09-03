"""
Descarga automatica dos CSV do simulador de precos da ERSE.

Na pagina inicial de https://simuladorprecos.erse.pt/ existe a ligacao
"Ofertas comerciais (CSV)". Essa ligacao nao esta escrita no HTML, e colocada
por JavaScript a partir de /config/Settings.json, na chave "csvPath".

Este modulo:
  1. le o Settings.json e retira dai o endereco do ZIP,
  2. se falhar, procura a ligacao no HTML e nos ficheiros .js da pagina,
  3. descarrega o ZIP e extrai os dois CSV para a pasta de dados,
  4. guarda um pequeno ficheiro info.json com a data da atualizacao.

Se alguma coisa correr mal e lancado ErroERSE, com uma mensagem que explica ao
utilizador como descarregar o ficheiro a mao.

So usa a biblioteca padrao, para o executavel ficar mais leve.
"""

from __future__ import annotations

import datetime as _dt
import io
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SITE = "https://simuladorprecos.erse.pt/"
SETTINGS = SITE + "config/Settings.json"
TRADUCOES = SITE + "config/Translations_PT.json"

# Paginas onde a ligacao para o ZIP pode aparecer, usadas como alternativa.
PAGINAS = [
    SITE,
    SITE + "eletricidade/",
    SITE + "eletricidade-e-gas-natural/",
]

CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9",
}

TEMPO_LIMITE = 45
MAX_JS = 6

# Quantas horas os ficheiros ja descarregados sao considerados atuais. Serve
# para nao ir ao site da ERSE a cada visita quando isto corre num servidor.
HORAS_ENTRE_ATUALIZACOES = 12

# Nomes com que os ficheiros ficam gravados na pasta de dados.
NOME_PRECOS = "Precos_ELEGN.csv"
NOME_CONDICOES = "CondComerciais.csv"
NOME_INFO = "info.json"

MENSAGEM_MANUAL = "Nao foi possivel descarregar os dados automaticamente.\n\nMotivo: {motivo}"


class ErroERSE(Exception):
    """Falha na descarga automatica. A mensagem ja explica o que aconteceu."""


def _mensagem(motivo: str) -> str:
    return MENSAGEM_MANUAL.format(motivo=motivo)


def _abrir(url: str, timeout: int = TEMPO_LIMITE) -> bytes:
    # O endereco do ZIP tem espacos, por isso e preciso codificar o caminho.
    seguro = urllib.parse.quote(url, safe=":/?&=%#+")
    pedido = urllib.request.Request(seguro, headers=CABECALHOS)
    contexto = ssl.create_default_context()
    with urllib.request.urlopen(pedido, timeout=timeout, context=contexto) as resposta:
        return resposta.read()


# --------------------------------------------------------- procurar o ZIP


def _do_settings() -> str | None:
    try:
        conteudo = _abrir(SETTINGS, timeout=20).decode("utf-8", errors="ignore")
        definicoes = json.loads(conteudo)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return None
    endereco = (definicoes.get("csvPath") or "").strip()
    if endereco.lower().endswith(".zip"):
        return urllib.parse.urljoin(SITE, endereco)
    return None


def _zips_no_texto(texto: str, base: str) -> list[str]:
    """Procura ligacoes para ficheiros ZIP dentro de HTML ou de JavaScript."""
    encontrados: list[str] = []
    padrao = r"""["'(]([^"'()<>]+?\.zip)["'()<>]"""
    for bruto in re.findall(padrao, texto, re.I):
        absoluto = urllib.parse.urljoin(base, bruto.replace("\\/", "/").strip())
        if absoluto not in encontrados:
            encontrados.append(absoluto)

    def pontuacao(url: str) -> int:
        minusculas = url.lower()
        palavras = ("csv", "admin/csvs", "oferta", "comercia", "preco")
        return -sum(palavra in minusculas for palavra in palavras)

    return sorted(encontrados, key=pontuacao)


def _js_da_pagina(texto: str, base: str) -> list[str]:
    achados: list[str] = []
    padrao = r"""src=["']([^"']+?\.js[^"']*)["']"""
    for bruto in re.findall(padrao, texto, re.I):
        absoluto = urllib.parse.urljoin(base, bruto)
        if absoluto.startswith("http") and absoluto not in achados:
            achados.append(absoluto)
    return achados[:MAX_JS]


def procurar_zip() -> str:
    """Devolve o endereco do ZIP das ofertas comerciais."""
    endereco = _do_settings()
    if endereco:
        return endereco

    ultimo_erro = "nao foi encontrada a ligacao para o ficheiro ZIP no site"
    paginas_lidas: list[tuple[str, str]] = []

    for pagina in PAGINAS:
        try:
            conteudo = _abrir(pagina).decode("utf-8", errors="ignore")
        except (urllib.error.URLError, OSError, TimeoutError) as erro:
            ultimo_erro = f"o site nao respondeu ({erro})"
            continue
        paginas_lidas.append((pagina, conteudo))
        ligacoes = _zips_no_texto(conteudo, pagina)
        if ligacoes:
            return ligacoes[0]

    # A pagina e construida por JavaScript, a ligacao pode estar nos .js.
    for pagina, conteudo in paginas_lidas:
        for js in _js_da_pagina(conteudo, pagina):
            try:
                codigo = _abrir(js, timeout=30).decode("utf-8", errors="ignore")
            except (urllib.error.URLError, OSError, TimeoutError):
                continue
            ligacoes = _zips_no_texto(codigo, js)
            if ligacoes:
                return ligacoes[0]

    raise ErroERSE(_mensagem(ultimo_erro))


def data_publicacao() -> str:
    """Data indicada pelo site na etiqueta do CSV, por exemplo 2-9-2026."""
    try:
        conteudo = _abrir(TRADUCOES, timeout=20).decode("utf-8", errors="ignore")
        for item in json.loads(conteudo):
            if item.get("key") == "HOME_LINK_CSV_LABEL":
                achado = re.search(r"(\d{1,2}-\d{1,2}-\d{4})", item.get("value") or "")
                if achado:
                    return achado.group(1)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError, TypeError):
        pass
    return ""


def _data_do_nome(url: str) -> str:
    """O nome do ZIP comeca pela data, por exemplo 20260902 164325 CSV.zip."""
    nome = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
    achado = re.match(r"(\d{4})(\d{2})(\d{2})", nome)
    if achado:
        ano, mes, dia = achado.groups()
        return f"{int(dia)}-{int(mes)}-{ano}"
    return ""


# --------------------------------------------------------- descarregar


def descarregar_zip(url: str | None = None) -> bytes:
    url = url or procurar_zip()
    try:
        conteudo = _abrir(url)
    except (urllib.error.URLError, OSError, TimeoutError) as erro:
        raise ErroERSE(_mensagem(f"a descarga falhou ({erro})")) from erro
    if not conteudo or not zipfile.is_zipfile(io.BytesIO(conteudo)):
        raise ErroERSE(_mensagem("o ficheiro descarregado nao e um ZIP valido"))
    return conteudo


def _escolher_membro(nomes: list[str], *palavras: str) -> str | None:
    for nome in nomes:
        curto = os.path.basename(nome).lower()
        if curto.endswith(".csv") and all(p in curto for p in palavras):
            return nome
    return None


def extrair(dados_zip: bytes, pasta_destino: str) -> tuple[str, str]:
    """Extrai os dois CSV do ZIP para a pasta indicada, precos primeiro."""
    if not zipfile.is_zipfile(io.BytesIO(dados_zip)):
        raise ErroERSE(_mensagem("o ficheiro indicado nao e um ZIP valido"))

    os.makedirs(pasta_destino, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(dados_zip)) as arquivo:
        nomes = [n for n in arquivo.namelist() if not n.endswith("/")]
        precos = _escolher_membro(nomes, "prec") or _escolher_membro(nomes, "elegn")
        condicoes = _escolher_membro(nomes, "cond")
        if not precos or not condicoes:
            disponiveis = ", ".join(os.path.basename(n) for n in nomes[:10]) or "nenhum"
            raise ErroERSE(
                _mensagem(
                    "o ZIP nao tem os dois CSV esperados. "
                    f"Encontrei estes ficheiros: {disponiveis}"
                )
            )
        pares = ((precos, NOME_PRECOS), (condicoes, NOME_CONDICOES))
        caminhos = []
        for membro, nome_final in pares:
            destino = os.path.join(pasta_destino, nome_final)
            with arquivo.open(membro) as origem, open(destino, "wb") as saida:
                saida.write(origem.read())
            caminhos.append(destino)
    return caminhos[0], caminhos[1]


def guardar_info(pasta_destino: str, origem: str, publicado: str = "") -> dict:
    info = {
        "origem": origem,
        "publicado": publicado,
        "descarregado": _dt.datetime.now().strftime("%d-%m-%Y %H:%M"),
    }
    try:
        os.makedirs(pasta_destino, exist_ok=True)
        with open(os.path.join(pasta_destino, NOME_INFO), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return info


def ler_info(pasta: str) -> dict:
    try:
        with open(os.path.join(pasta, NOME_INFO), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ficheiros_locais(pasta: str) -> tuple[str, str] | None:
    """Caminhos dos CSV ja guardados, ou None se ainda nao existirem."""
    precos = os.path.join(pasta, NOME_PRECOS)
    condicoes = os.path.join(pasta, NOME_CONDICOES)
    if os.path.exists(precos) and os.path.exists(condicoes):
        return precos, condicoes
    return None


def dados_frescos(pasta: str, horas: float = HORAS_ENTRE_ATUALIZACOES) -> bool:
    """True se os CSV guardados forem recentes que chegue para os reaproveitar."""
    ficheiros = ficheiros_locais(pasta)
    if not ficheiros:
        return False
    try:
        idade = time.time() - max(os.path.getmtime(f) for f in ficheiros)
    except OSError:
        return False
    return idade < horas * 3600


def atualizar(pasta_destino: str) -> dict:
    """Procura, descarrega e extrai. Lanca ErroERSE se alguma etapa falhar."""
    url = procurar_zip()
    conteudo = descarregar_zip(url)
    extrair(conteudo, pasta_destino)
    return guardar_info(pasta_destino, url, data_publicacao() or _data_do_nome(url))


def guardar_zip_manual(dados_zip: bytes, pasta_destino: str) -> dict:
    """Aceita um ZIP que o utilizador descarregou a mao."""
    extrair(dados_zip, pasta_destino)
    return guardar_info(pasta_destino, "ficheiro ZIP colocado pelo utilizador")


def guardar_csv_manual(
    conteudo_precos: bytes, conteudo_condicoes: bytes, pasta_destino: str
) -> dict:
    """Aceita os dois CSV que o utilizador descarregou a mao."""
    os.makedirs(pasta_destino, exist_ok=True)
    pares = ((conteudo_precos, NOME_PRECOS), (conteudo_condicoes, NOME_CONDICOES))
    for conteudo, nome in pares:
        with open(os.path.join(pasta_destino, nome), "wb") as saida:
            saida.write(conteudo)
    return guardar_info(pasta_destino, "ficheiros CSV colocados pelo utilizador")
