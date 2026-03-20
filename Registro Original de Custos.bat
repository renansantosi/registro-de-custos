@echo off
cd /d "%~dp0"
title Registro Original de Custos

echo ================================================
echo   Registro Original de Custos
echo ================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale o Python em python.org
    pause
    exit /b 1
)

echo Instalando dependencias...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [AVISO] Falha ao instalar dependencias. Tentando continuar...
)
echo Dependencias OK.
echo.

if not exist "uploads" mkdir uploads

echo Iniciando servidor em http://localhost:5000
echo Pressione Ctrl+C para encerrar.
echo.
python app.py
pause
