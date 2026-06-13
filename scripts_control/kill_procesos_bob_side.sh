#!/usr/bin/env bash
set -euo pipefail

echo "[QKD] Deteniendo procesos Python QKD en Bob side..."

echo "[QKD] Deteniendo Bob..."
docker exec bob pkill -f "bob.py" 2>/dev/null || true

echo "[QKD] Procesos QKD detenidos en Bob side."