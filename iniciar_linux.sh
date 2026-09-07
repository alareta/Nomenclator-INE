#!/usr/bin/env bash
# Lanzador para Linux y macOS. Doble clic (si el gestor de ficheros lo
# permite) o, desde una terminal: ./iniciar_linux.sh
set -euo pipefail

# Situarse en la carpeta donde esta este propio script, sea cual sea
# el sitio desde el que se invoque, y guardar la ruta absoluta para
# anclar a ella el resto de rutas (mas robusto que fiarse solo del cd).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  Nomenclator INE - Herramienta local"
echo "=========================================="
echo

PORT="${PORT:-8080}"

# -- Comprobar si el puerto ya esta en uso -----------------------------------
# Puede pasar si un arranque anterior quedo "zombie" (p.ej. se cerro la
# terminal de golpe en vez de Ctrl+C y el proceso de Python no murio).
PID_OCUPA=""
if command -v lsof >/dev/null 2>&1; then
    PID_OCUPA="$(lsof -ti tcp:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
fi

if [ -n "$PID_OCUPA" ]; then
    NOMBRE_PROCESO="$(ps -p "$PID_OCUPA" -o comm= 2>/dev/null || true)"
    case "$NOMBRE_PROCESO" in
        python*|Python*)
            echo "Detectado un arranque anterior que quedo abierto en el"
            echo "puerto ${PORT}. Liberandolo antes de continuar..."
            kill -9 "$PID_OCUPA" 2>/dev/null || true
            sleep 1
            echo
            ;;
        *)
            echo "============================================"
            echo "ERROR: El puerto ${PORT} esta siendo usado por"
            echo "otro programa (${NOMBRE_PROCESO:-desconocido}, PID ${PID_OCUPA})."
            echo
            echo "Cierra ese programa, o cambia el puerto con:"
            echo "  PORT=8081 ./iniciar_linux.sh"
            echo "============================================"
            echo
            exit 1
            ;;
    esac
fi

# Buscar un interprete de Python 3 disponible.
if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON=python
else
    echo "No se ha encontrado Python 3 instalado en este ordenador."
    echo
    echo "En macOS: instala Python desde https://www.python.org/downloads/"
    echo "          o con Homebrew: brew install python"
    echo "En Linux: instala el paquete python3 con el gestor de tu"
    echo "          distribucion, p.ej. 'sudo apt install python3 python3-venv'."
    exit 1
fi

# Crear el entorno virtual la primera vez que se ejecuta (no se vuelve
# a crear en arranques posteriores, asi que el arranque siguiente es
# mucho mas rapido).
if [ ! -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    echo "Preparando el entorno la primera vez, un momento..."
    if ! "$PYTHON" -m venv "$SCRIPT_DIR/.venv"; then
        echo
        echo "ERROR: No se ha podido crear el entorno virtual."
        echo "Revisa que Python este correctamente instalado e intentalo de nuevo."
        exit 1
    fi
fi

# shellcheck disable=SC1091
source "$SCRIPT_DIR/.venv/bin/activate"

echo "Comprobando dependencias..."
if ! python -m pip install --quiet --upgrade pip || ! python -m pip install --quiet -r "$SCRIPT_DIR/requirements.txt"; then
    echo
    echo "AVISO: No se han podido (re)instalar las dependencias"
    echo "(sin conexion a internet?). Si ya estaban instaladas de una"
    echo "vez anterior, se intentara arrancar igualmente."
    echo
fi

echo
echo "Iniciando el servidor local en http://127.0.0.1:${PORT}"
echo "Se abrira el navegador automaticamente en unos segundos."
echo
echo "No cierres esta terminal mientras uses la herramienta."
echo "Para salir, pulsa Ctrl+C (mejor que cerrar la ventana de golpe:"
echo "asi el puerto queda libre en el siguiente arranque)."
echo

# Abrir el navegador tras una breve pausa, dando tiempo a que el
# servidor Flask este ya escuchando antes de la primera peticion.
(
    sleep 2
    if command -v open >/dev/null 2>&1; then
        open "http://127.0.0.1:${PORT}"          # macOS
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://127.0.0.1:${PORT}"      # Linux
    fi
) &

if [ ! -f "$SCRIPT_DIR/webapp/app.py" ]; then
    echo
    echo "ERROR: No se encuentra $SCRIPT_DIR/webapp/app.py."
    echo "Comprueba que la carpeta webapp esta junto a este script."
    echo
    exit 1
fi

python "$SCRIPT_DIR/webapp/app.py"

echo
echo "El servidor se ha detenido."
