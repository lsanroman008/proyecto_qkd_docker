#!/usr/bin/env bash
set -euo pipefail

echo "[QKD] Deteniendo procesos Python QKD en Alice side..."

echo "[QKD] Deteniendo NetSquid..."
docker exec netsquid pkill -f "netSquidControl.py" 2>/dev/null || true

echo "[QKD] Deteniendo Alice..."
docker exec alice pkill -f "alice.py" 2>/dev/null || true

echo "[QKD] Procesos QKD detenidos en Alice side."