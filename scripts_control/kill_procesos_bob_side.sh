#!/usr/bin/env bash
set -euo pipefail

# Forzar ejecución con sudo
if [[ "${EUID}" -ne 0 ]]; then
    echo "[QKD] Este script necesita sudo. Relanzando con sudo..."
    SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
    exec sudo -E bash "$SCRIPT_PATH" "$@"
fi

echo "[QKD] Deteniendo procesos Python QKD en Bob side..."

echo "[QKD] Deteniendo Bob..."
docker exec -u root bob pkill -f "bob.py" 2>/dev/null || true

echo "[QKD] Procesos QKD detenidos en Bob side."