#!/usr/bin/env bash
set -e

source "$(dirname "${BASH_SOURCE[0]}")/leer_ips.sh"
USER_REMOTO="${USER_REMOTO:-$USER}"

echo "[QKD] Matando procesos Python QKD en Alice ($ALICE_HOST)..."
ssh "${USER_REMOTO}@${ALICE_HOST}" "
docker exec netsquid pkill -f netSquidControl.py 2>/dev/null || true
docker exec alice pkill -f alice.py 2>/dev/null || true
"

echo "[QKD] Matando procesos Python QKD en Bob ($BOB_HOST)..."
ssh "${USER_REMOTO}@${BOB_HOST}" "
docker exec bob pkill -f bob.py 2>/dev/null || true
"

echo "[QKD] Procesos Python QKD detenidos en Alice y Bob."
