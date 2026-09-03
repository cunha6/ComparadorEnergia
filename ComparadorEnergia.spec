# -*- mode: python ; coding: utf-8 -*-
"""
Receita do PyInstaller para o Comparador de Energia.

Por omissao gera um unico ComparadorEnergia.exe. Se a variavel de ambiente
MODO estiver a "pasta", gera antes uma pasta com o exe la dentro, que arranca
bastante mais depressa.

    pyinstaller --noconfirm ComparadorEnergia.spec
"""

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

UM_SO_FICHEIRO = os.environ.get("MODO", "arquivo").lower() != "pasta"

# O Streamlit corre o app.py como um script, por isso os modulos da aplicacao
# tem de viajar como ficheiros e nao so dentro do arquivo de codigo.
datas = [
    ("app.py", "."),
    ("dados.py", "."),
    ("erse.py", "."),
    (".streamlit/config.toml", ".streamlit"),
]
binaries = []
hiddenimports = [
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.web.cli",
]

# Estes pacotes trazem ficheiros de dados que o PyInstaller nao descobre sozinho.
for pacote in ("streamlit", "altair", "narwhals", "pydeck", "pyarrow"):
    extra_datas, extra_binaries, extra_hidden = collect_all(pacote)
    datas += extra_datas
    binaries += extra_binaries
    hiddenimports += extra_hidden

# O Streamlit le a sua versao, e a das dependencias, pelos metadados instalados.
for pacote in (
    "streamlit",
    "altair",
    "narwhals",
    "pandas",
    "numpy",
    "pyarrow",
    "packaging",
    "protobuf",
    "tornado",
    "pillow",
    "pydeck",
    "watchdog",
    "click",
    "blinker",
    "cachetools",
    "tenacity",
    "toml",
    "typing_extensions",
    "jsonschema",
    "gitpython",
    "requests",
):
    try:
        datas += copy_metadata(pacote)
    except Exception:
        pass

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "scipy",
        "IPython",
        "notebook",
        "pytest",
        "selenium",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if UM_SO_FICHEIRO:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="ComparadorEnergia",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="ComparadorEnergia",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="ComparadorEnergia",
    )
