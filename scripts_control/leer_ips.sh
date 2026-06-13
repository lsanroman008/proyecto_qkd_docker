#!/usr/bin/env bash
# Carga ALICE_HOST y BOB_HOST desde qkd_netsquid/qkd_hosts.py
# Usar con: source "$(dirname "${BASH_SOURCE[0]}")/leer_ips.sh"
QKD_HOME="${QKD_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ALICE_HOST=$(python3 -c "import sys; sys.path.insert(0,'$QKD_HOME/qkd_netsquid'); from qkd_hosts import ALICE_HOST; print(ALICE_HOST)")
BOB_HOST=$(python3 -c "import sys; sys.path.insert(0,'$QKD_HOME/qkd_netsquid'); from qkd_hosts import BOB_HOST; print(BOB_HOST)")
export ALICE_HOST BOB_HOST
