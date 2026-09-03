@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Pipeline - Manutencao Frota

echo.
echo ============================================================
echo   PIPELINE CONSOLIDADA
echo   SIGLA ^> dadosManut ^> Rascunho Email
echo.
echo   TODAS as opcoes geram RASCUNHO no Outlook.
echo   O envio e sempre manual, diretamente pelo Outlook.
echo ============================================================
echo.
echo  Opcoes:
echo    [1] Completa D-1      (abre SIGLA, le trilhos, insere, gera rascunho)
echo    [2] Completa data     (data especifica)
echo    [3] Completa periodo  (data inicio ate data fim)
echo    [4] SIGLA ja na malha (pula login/filtro, le direto, gera rascunho)
echo    [5] Pular SIGLA       (relatorio ja existe, so insere + gera rascunho)
echo    [8] Pular SIGLA periodo (relatorios ja existem, insere periodo + gera rascunho)
echo    [6] Dry-run           (SIGLA ja na malha, le + insere + gera rascunho)
echo    [7] Dry-run completo  (abre SIGLA do zero, le + insere + gera rascunho)
echo    [C] Abrir calibrador SIGLA
echo    [0] Sair
echo.
set /p OPCAO=Escolha:

if "!OPCAO!"=="0" exit /b 0

if "!OPCAO!"=="1" (
    echo.
    echo  ATENCAO: NAO MEXA NO MOUSE durante a varredura do SIGLA.
    echo  O SIGLA sera aberto automaticamente.
    echo.
    pause
    python pipeline.py
    goto FIM
)

if "!OPCAO!"=="2" (
    set /p DATA=Data YYYY-MM-DD ou DD/MM/YYYY:
    echo.
    echo  ATENCAO: NAO MEXA NO MOUSE durante a varredura do SIGLA.
    echo.
    pause
    python pipeline.py --data "!DATA!"
    goto FIM
)

if "!OPCAO!"=="3" (
    set /p DATA_INI=Data inicio YYYY-MM-DD ou DD/MM/YYYY:
    set /p DATA_FIM=Data fim    YYYY-MM-DD ou DD/MM/YYYY:
    echo.
    echo  ATENCAO: NAO MEXA NO MOUSE durante a varredura do SIGLA.
    echo.
    pause
    python pipeline.py --data "!DATA_INI!" --ate "!DATA_FIM!"
    goto FIM
)

if "!OPCAO!"=="4" (
    set /p DATA=Data YYYY-MM-DD, branco para D-1:
    echo.
    echo  ATENCAO: Certifique-se de que a malha do SIGLA esta aberta e visivel.
    echo  NAO MEXA NO MOUSE durante a varredura.
    echo.
    pause
    if "!DATA!"=="" (
        python pipeline.py --from-malha
    ) else (
        python pipeline.py --data "!DATA!" --from-malha
    )
    goto FIM
)

if "!OPCAO!"=="5" (
    set /p DATA=Data YYYY-MM-DD, branco para D-1:
    if "!DATA!"=="" (
        python pipeline.py --pular-sigla
    ) else (
        python pipeline.py --data "!DATA!" --pular-sigla
    )
    goto FIM
)

if "!OPCAO!"=="6" (
    set /p DATA=Data YYYY-MM-DD, branco para D-1:
    echo.
    echo  ATENCAO: Certifique-se de que a malha do SIGLA esta aberta e visivel.
    echo  NAO MEXA NO MOUSE durante a varredura.
    echo.
    pause
    if "!DATA!"=="" (
        python pipeline.py --from-malha --dry-run
    ) else (
        python pipeline.py --data "!DATA!" --from-malha --dry-run
    )
    goto FIM
)

if "!OPCAO!"=="7" (
    set /p DATA=Data YYYY-MM-DD, branco para D-1:
    echo.
    echo  ATENCAO: O SIGLA sera aberto automaticamente.
    echo  NAO MEXA NO MOUSE durante a varredura.
    echo.
    pause
    if "!DATA!"=="" (
        python pipeline.py --dry-run
    ) else (
        python pipeline.py --data "!DATA!" --dry-run
    )
    goto FIM
)

if "!OPCAO!"=="8" (
    set /p DATA_INI=Data inicio YYYY-MM-DD ou DD/MM/YYYY:
    set /p DATA_FIM=Data fim    YYYY-MM-DD ou DD/MM/YYYY:
    python pipeline.py --data "!DATA_INI!" --ate "!DATA_FIM!" --pular-sigla
    goto FIM
)

if /i "!OPCAO!"=="C" (
    cd /d "%~dp0ControleRemoto SIGLA"
    python sigla_calibrador.py
    cd /d "%~dp0"
    goto FIM
)

echo Opcao invalida.

:FIM
echo.
pause
