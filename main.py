"""
Arranque do Comparador de Energia.

Levanta o servidor do Streamlit em segundo plano e abre a aplicacao no
navegador que o utilizador ja usa. Serve tanto para correr com o Python
instalado como dentro do executavel gerado pelo PyInstaller.

    python main.py
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PORTA_PREFERIDA = 8501
ENDERECO = "localhost"


def pasta_base() -> Path:
    """Pasta onde estao o app.py e os modulos, dentro ou fora do executavel."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def porta_livre(inicio: int = PORTA_PREFERIDA) -> int:
    for porta in range(inicio, inicio + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
            teste.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if teste.connect_ex((ENDERECO, porta)) != 0:
                return porta
    return inicio


def calar_pedido_de_email() -> None:
    """Evita a pergunta do email que o Streamlit faz no primeiro arranque."""
    credenciais = Path.home() / ".streamlit" / "credentials.toml"
    if credenciais.exists():
        return
    try:
        credenciais.parent.mkdir(parents=True, exist_ok=True)
        credenciais.write_text('[general]\nemail = ""\n', encoding="utf-8")
    except OSError:
        pass


def configurar(base: Path) -> None:
    """Configuracao por variaveis de ambiente, para nao depender do config.toml."""
    definicoes = {
        # sem barra de ferramentas, sem botao de deploy, sem menu
        "STREAMLIT_CLIENT_TOOLBAR_MODE": "viewer",
        "STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION": "false",
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        "STREAMLIT_SERVER_HEADLESS": "true",
        "STREAMLIT_SERVER_RUN_ON_SAVE": "false",
        "STREAMLIT_SERVER_FILE_WATCHER_TYPE": "none",
        "STREAMLIT_GLOBAL_DEVELOPMENT_MODE": "false",
        "STREAMLIT_THEME_BASE": "light",
        "STREAMLIT_THEME_PRIMARY_COLOR": "#0E7C86",
        "STREAMLIT_THEME_BACKGROUND_COLOR": "#FFFFFF",
        "STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR": "#F6F8FA",
        "STREAMLIT_THEME_TEXT_COLOR": "#10151F",
    }
    for chave, valor in definicoes.items():
        os.environ.setdefault(chave, valor)
    os.environ.setdefault("PYTHONPATH", str(base))
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))


def abrir_navegador(url: str) -> None:
    """Espera que o servidor responda e so depois abre o navegador."""
    for _ in range(120):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as teste:
            if teste.connect_ex((ENDERECO, int(url.rsplit(":", 1)[1]))) == 0:
                break
        time.sleep(0.25)
    try:
        webbrowser.open(url)
    except Exception:  # navegador em falta, o endereco fica na consola
        pass


def executar() -> None:
    base = pasta_base()
    aplicacao = base / "app.py"
    if not aplicacao.exists():
        raise SystemExit(f"Nao encontrei o ficheiro da aplicacao em {aplicacao}")

    calar_pedido_de_email()
    configurar(base)

    porta = porta_livre()
    url = f"http://{ENDERECO}:{porta}"
    threading.Thread(target=abrir_navegador, args=(url,), daemon=True).start()
    print(f"Comparador de Energia a arrancar em {url}")
    print("Feche esta janela para terminar a aplicacao.")

    from streamlit.web import cli as stcli  # importado tarde, arranca mais depressa

    sys.argv = [
        "streamlit",
        "run",
        str(aplicacao),
        "--server.port",
        str(porta),
        "--server.address",
        ENDERECO,
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--client.toolbarMode",
        "viewer",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    executar()
