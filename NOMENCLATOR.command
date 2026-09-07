#!/bin/bash
# Arranca la app del Nomenclátor en macOS con doble clic desde Finder.
#
# La primera vez, macOS bloqueará la ejecución (Gatekeeper). Hazlo
# ejecutable y quítale la cuarentena una vez desde Terminal:
#   chmod +x NOMENCLATOR.command
#   xattr -d com.apple.quarantine NOMENCLATOR.command
# Alternativamente: clic derecho -> Abrir -> Abrir (o, en macOS Sequoia
# y posteriores, Ajustes del Sistema -> Privacidad y seguridad -> Abrir
# de todos modos).

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

pip3 install -r requirements.txt

cd webapp || {
  echo "No se encuentra la carpeta 'webapp' junto a este script."
  read -p "Pulsa Intro para cerrar..."
  exit 1
}

python3 app.py

echo ""
read -p "La app se ha detenido. Pulsa Intro para cerrar esta ventana..."
