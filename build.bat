@echo off
title Gerar o ComparadorEnergia.exe
cd /d "%~dp0"

echo ============================================================
echo  Gerar o executavel ComparadorEnergia.exe
echo  Precisa de ter o Python instalado a partir de python.org
echo ============================================================
echo.
echo  Modo:  %1
echo   sem argumentos  = um unico ficheiro .exe
echo   pasta           = uma pasta, arranca mais depressa
echo.

python --version >nul 2>&1
if errorlevel 1 (
  echo NAO FOI ENCONTRADO O PYTHON.
  echo Instale em https://www.python.org/downloads/windows/
  echo Durante a instalacao marque a caixa "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

echo A instalar as bibliotecas necessarias, se faltarem...
python -m pip install --upgrade --quiet pip
python -m pip install --upgrade --quiet streamlit pandas altair pyinstaller
if errorlevel 1 (
  echo Falhou a instalacao das bibliotecas. Verifique a ligacao a internet.
  pause
  exit /b 1
)

if /i "%1"=="pasta" (set MODO=pasta) else (set MODO=arquivo)

echo.
echo A gerar o executavel, demora alguns minutos...
python -m PyInstaller --noconfirm --clean ComparadorEnergia.spec

if errorlevel 1 (
  echo.
  echo Algo correu mal ao gerar o executavel.
  pause
  exit /b 1
)

echo.
if /i "%MODO%"=="pasta" (
  echo Terminado. A aplicacao esta em:
  echo    %~dp0dist\ComparadorEnergia\ComparadorEnergia.exe
  echo Copie a pasta ComparadorEnergia inteira para o outro computador.
) else (
  echo Terminado. O executavel esta em:
  echo    %~dp0dist\ComparadorEnergia.exe
  echo Pode copiar so esse ficheiro para qualquer computador com Windows.
)
echo.
pause
