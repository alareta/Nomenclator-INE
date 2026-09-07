@echo off
setlocal enabledelayedexpansion
title Nomenclator INE

rem Situarse en la carpeta donde esta este propio .bat (webapp/), sea cual
rem sea el sitio desde el que se haga doble clic o se ejecute.
cd /d "%~dp0"

if "%PORT%"=="" (set "PUERTO=8080") else (set "PUERTO=%PORT%")

echo ==========================================
echo   Nomenclator INE - Herramienta local
echo ==========================================
echo.

rem -- Comprobar si el puerto ya esta en uso -----------------------------------
rem Puede pasar si un arranque anterior quedo "zombie" (p.ej. se cerro la
rem ventana con la X en vez de Ctrl+C y el proceso de Python no murio).
set "PID_OCUPA="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PUERTO% " ^| findstr "LISTENING"') do (
    set "PID_OCUPA=%%a"
)

if defined PID_OCUPA (
    set "ES_PYTHON="
    tasklist /FI "PID eq !PID_OCUPA!" /FI "IMAGENAME eq python.exe" 2>nul | findstr /i "python.exe" >nul && set "ES_PYTHON=1"
    if not defined ES_PYTHON (
        tasklist /FI "PID eq !PID_OCUPA!" /FI "IMAGENAME eq pythonw.exe" 2>nul | findstr /i "pythonw.exe" >nul && set "ES_PYTHON=1"
    )

    if defined ES_PYTHON (
        echo  Detectado un arranque anterior que quedo abierto en el
        echo  puerto %PUERTO%. Liberandolo antes de continuar...
        taskkill /PID !PID_OCUPA! /F >nul 2>&1
        timeout /t 1 >nul
        echo.
    ) else (
        echo  ============================================
        echo  ERROR: El puerto %PUERTO% esta siendo usado por
        echo  otro programa ^(no por esta herramienta^).
        echo.
        echo  Cierra ese programa, o cambia el puerto con:
        echo    set PORT=8081 ^&^& iniciar_windows.bat
        echo.
        echo  Para identificar el programa ejecuta en CMD:
        echo    netstat -ano ^| findstr :%PUERTO%
        echo  ============================================
        echo.
        pause
        exit /b 1
    )
)

rem -- Buscar un interprete de Python 3 disponible -----------------------------
rem Se prueba "python" y se descarta si es el alias-trampa de la Microsoft
rem Store (aparece en el PATH pero no ejecuta nada real). Si falla, se
rem prueba el lanzador "py", mas fiable en instalaciones desde python.org.
set "PYTHON="

where python >nul 2>nul
if %errorlevel%==0 (
    python -c "import sys" >nul 2>nul
    if !errorlevel!==0 set "PYTHON=python"
)

if not defined PYTHON (
    where py >nul 2>nul
    if %errorlevel%==0 set "PYTHON=py -3"
)

if not defined PYTHON (
    echo.
    echo  ============================================
    echo  ERROR: No se ha encontrado Python 3 instalado,
    echo  o el "python" del PATH es el acceso directo de
    echo  la Microsoft Store ^(no cuenta como instalacion
    echo  real^).
    echo.
    echo  Descargalo desde https://www.python.org/downloads/
    echo  Durante la instalacion, marca la casilla
    echo  "Add python.exe to PATH".
    echo  ============================================
    echo.
    pause
    exit /b 1
)

rem -- Crear el entorno virtual la primera vez ---------------------------------
if not exist "%~dp0.venv\Scripts\activate.bat" (
    echo  Preparando el entorno la primera vez, un momento...
    %PYTHON% -m venv "%~dp0.venv"
    if not exist "%~dp0.venv\Scripts\activate.bat" (
        echo.
        echo  ============================================
        echo  ERROR: No se ha podido crear el entorno virtual.
        echo  Revisa que Python este correctamente instalado
        echo  e intentalo de nuevo.
        echo  ============================================
        echo.
        pause
        exit /b 1
    )
)

call "%~dp0.venv\Scripts\activate.bat"

echo  Comprobando dependencias...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "%~dp0requirements.txt"
if not %errorlevel%==0 (
    echo.
    echo  AVISO: No se han podido ^(re^)instalar las dependencias
    echo  ^(sin conexion a internet?^). Si ya estaban instaladas
    echo  de una vez anterior, se intentara arrancar igualmente.
    echo.
)

echo.
echo  Iniciando el servidor local en http://127.0.0.1:%PUERTO%
echo  Se abrira el navegador automaticamente en unos segundos.
echo.
echo  No cierres esta ventana mientras uses la herramienta.
echo  Para salir, pulsa Ctrl+C ^(mejor que la X: asi el puerto
echo  queda libre en el siguiente arranque^).
echo.

set "PORT=%PUERTO%"

rem Abrir el navegador tras una breve pausa, dando tiempo a que el
rem servidor Flask este ya escuchando antes de la primera peticion.
start "" cmd /c "timeout /t 2 >nul && start http://127.0.0.1:%PUERTO%"

if not exist "%~dp0webapp\app.py" (
    echo.
    echo  ============================================
    echo  ERROR: No se encuentra "%~dp0webapp\app.py".
    echo  Comprueba que la carpeta "webapp" esta junto a
    echo  este mismo archivo .bat.
    echo  ============================================
    echo.
    pause
    exit /b 1
)

python "%~dp0webapp\app.py"

echo.
echo  El servidor se ha detenido.
pause
