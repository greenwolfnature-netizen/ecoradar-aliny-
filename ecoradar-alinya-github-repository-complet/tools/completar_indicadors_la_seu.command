#!/bin/zsh
set -e

ROOT="/Users/usuario/Documents/Ecoradar"
PYTHON="$ROOT/.venv/bin/python"

cd "$ROOT"
if [[ -z "$COPERNICUS_CLIENT_ID" ]]; then
  read "COPERNICUS_CLIENT_ID?Introdueix el Client ID OAuth de Copernicus: "
fi
if [[ -z "$COPERNICUS_CLIENT_SECRET" ]]; then
  read -s "COPERNICUS_CLIENT_SECRET?Introdueix el Client Secret OAuth de Copernicus: "
  print
fi
export COPERNICUS_CLIENT_ID COPERNICUS_CLIENT_SECRET
"$PYTHON" tools/complete_la_seu_remaining_indicators.py
print "Procés completat. Pots tancar aquesta finestra."
read "?Prem Retorn per sortir."
