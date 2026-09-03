@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Validacao da Malha SIGLA - Menu
cd /d "%~dp0"

rem Descobre qual comando do Python existe nesta maquina.
set "PY="
python --version >nul 2>&1 && set "PY=python"
if not defined PY py --version >nul 2>&1 && set "PY=py"
if not defined PY (
    echo.
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale o Python, depois rode este menu de novo e use a opcao 5.
    echo.
    pause
    exit /b 1
)

rem Le a pasta de extracoes configurada, para mostrar na tela.
set "FONTE=(nao foi possivel ler config\caminhos.json)"
for /f "usebackq delims=" %%p in (`%PY% -c "import json;print(json.load(open('config/caminhos.json',encoding='utf-8'))['pasta_extracoes'])" 2^>nul`) do set "FONTE=%%p"

:menu
cls
echo ==================================================
echo  Validacao da Malha SIGLA
echo ==================================================
echo  execucao.xls: nesta pasta
echo  Raspagem OCR: %FONTE%
echo --------------------------------------------------
echo  RELATORIO execucao.xls, malha em texto, rapido
echo   1) Validar o dia de hoje
echo   2) Validar outro dia
echo.
echo  RASPAGEM DA MALHA, extracao por OCR, lenta
echo   3) Validar a extracao mais recente
echo   4) Validar um dia especifico
echo.
echo  OUTROS
echo   5) Validar um arquivo pelo caminho
echo   6) Autoteste do ambiente (dados ficticios)
echo   7) Instalar dependencias Python
echo   8) Abrir a pasta de relatorios
echo   0) Sair
echo --------------------------------------------------
set /p op="Escolha uma opcao: "

if "%op%"=="1" goto exec_hoje
if "%op%"=="2" goto exec_dia
if "%op%"=="3" goto recente
if "%op%"=="4" goto dia
if "%op%"=="5" goto arquivo
if "%op%"=="6" goto autoteste
if "%op%"=="7" goto instalar
if "%op%"=="8" goto abrir
if "%op%"=="0" goto fim
goto menu

:exec_hoje
cls
echo ==================================================
echo  Relatorio execucao, dia de hoje
echo ==================================================
if not exist execucao.xls (
    echo.
    echo [AVISO] execucao.xls nao encontrado nesta pasta.
    echo Gere o relatorio no SIGLA cobrindo de 3 dias antes do dia
    echo alvo ate o fim da malha, e salve aqui como execucao.xls.
    echo.
    pause
    goto menu
)
echo.
%PY% main.py --arquivo execucao.xls
echo.
pause
goto menu

:exec_dia
cls
echo ==================================================
echo  Relatorio execucao, outro dia
echo ==================================================
if not exist execucao.xls (
    echo.
    echo [AVISO] execucao.xls nao encontrado nesta pasta.
    echo.
    pause
    goto menu
)
echo.
set "alvo="
set /p alvo="Dia alvo no formato DD/MM/AAAA (vazio para voltar): "
if "%alvo%"=="" goto menu
echo.
%PY% main.py --arquivo execucao.xls --dia %alvo%
echo.
pause
goto menu

:recente
cls
echo ==================================================
echo  Extracao mais recente
echo ==================================================
echo  Procurando em:
echo    %FONTE%
echo --------------------------------------------------
echo.
%PY% main.py
echo.
pause
goto menu

:dia
cls
echo ==================================================
echo  Dia especifico
echo ==================================================
echo.
echo Ultimos dias extraidos:
echo.
set /a n=0
for /f "delims=" %%d in ('dir /b /ad /o-d "ControleRemoto SIGLA\saida" 2^>nul') do (
    set /a n+=1
    if !n! leq 15 echo    %%d
)
echo.
echo    (%n% dias no total, mostrando os 15 mais recentes)
echo.
set "dia="
set /p dia="Digite o dia no formato DD-MM-AAAA (vazio para voltar): "
if "%dia%"=="" goto menu
if not exist "ControleRemoto SIGLA\saida\%dia%" (
    echo.
    echo [AVISO] Nao existe a pasta "ControleRemoto SIGLA\saida\%dia%".
    echo.
    pause
    goto menu
)
echo.
%PY% main.py --pasta "ControleRemoto SIGLA\saida\%dia%"
echo.
pause
goto menu

:arquivo
cls
echo ==================================================
echo  Arquivo especifico
echo ==================================================
echo.
echo Cole o caminho completo do arquivo, ou arraste o
echo arquivo para esta janela e tecle Enter.
echo.
set "arq="
set /p arq="Arquivo (vazio para voltar): "
if "%arq%"=="" goto menu
set arq=%arq:"=%
if not exist "%arq%" (
    echo.
    echo [AVISO] Arquivo nao encontrado: %arq%
    echo.
    pause
    goto menu
)
echo.
%PY% main.py --arquivo "%arq%"
echo.
pause
goto menu

:autoteste
cls
echo ==================================================
echo  Autoteste do ambiente
echo ==================================================
echo.
echo ATENCAO: esta opcao NAO usa a malha real.
echo.
echo Ela roda contra uma extracao ficticia de 19 linhas
echo que fica em exemplo\, com resultado fixo e conhecido.
echo Serve so para provar que o Python e as regras estao
echo funcionando nesta maquina. A data 21/05/2026 que
echo aparece e inventada, faz parte do arquivo de teste.
echo.
echo Para validar a malha de verdade, use a opcao 1.
echo.
echo --------------------------------------------------
echo  Esperado:
echo    18 servicos validos, 1 sem dados suficientes
echo    Garagens: regra ativa, 295 siglas no catalogo
echo    17 servicos comerciais, 1 blocos internos
echo    6 anomalia(s) em 5 de 8 trilhos
echo    Locais sem zona cadastrada: XPT
echo --------------------------------------------------
echo  Resultado:
echo.
%PY% main.py --pasta exemplo --sem-abrir
echo.
pause
goto menu

:instalar
cls
echo ==================================================
echo  Dependencias
echo ==================================================
echo.
%PY% -m pip install --upgrade pip
%PY% -m pip install pandas openpyxl xlrd
echo.
pause
goto menu

:abrir
if not exist saida mkdir saida
start "" saida
goto menu

:fim
exit /b 0
