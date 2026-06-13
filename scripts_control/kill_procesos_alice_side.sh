#!/usr/bin/env bash
set -euo pipefail

# Forzar ejecución con sudo
if [[ "${EUID}" -ne 0 ]]; then
    echo "[QKD] Este script necesita sudo. Relanzando con sudo..."
    SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
    exec sudo -E bash "$SCRIPT_PATH" "$@"
fi

echo "[QKD] Deteniendo procesos Python QKD en Alice side..."

echo "[QKD] Deteniendo NetSquid..."
docker exec -u root netsquid pkill -f "netSquidControl.py" 2>/dev/null || true

echo "[QKD] Deteniendo Alice..."
docker exec -u root alice pkill -f "alice.py" 2>/dev/null || true

echo "[QKD] Procesos QKD detenidos en Alice side."