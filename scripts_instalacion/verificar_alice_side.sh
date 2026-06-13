#!/usr/bin/env bash
set -e

QKD_HOME="${QKD_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$QKD_HOME"

docker version >/dev/null 2>&1 && echo "OK: docker" || echo "FAIL: docker"
docker compose version >/dev/null 2>&1 && echo "OK: docker compose" || echo "FAIL: docker compose"

for c in alice netsquid monitor; do
  docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null | grep -q true && echo "OK: $c" || echo "FAIL: $c"
done

docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

echo "[QKD] Tablas Alice local:"
docker exec alice mysql --skip-ssl -u QKD QKD_keys_KMS1 -e "SHOW TABLES;"

echo "[QKD] Tablas monitor:"
docker exec monitor mysql --skip-ssl -u QKD QKD_netsquid -e "SHOW TABLES;"
