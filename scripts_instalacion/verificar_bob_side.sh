#!/usr/bin/env bash
set -e

QKD_HOME="${QKD_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$QKD_HOME"

docker version >/dev/null 2>&1 && echo "OK: docker" || echo "FAIL: docker"
docker compose version >/dev/null 2>&1 && echo "OK: docker compose" || echo "FAIL: docker compose"
docker inspect -f '{{.State.Running}}' bob 2>/dev/null | grep -q true && echo "OK: bob" || echo "FAIL: bob"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

echo "[QKD] Tablas Bob local:"
docker exec bob mysql --skip-ssl -u QKD QKD_keys_KMS1 -e "SHOW TABLES;"
