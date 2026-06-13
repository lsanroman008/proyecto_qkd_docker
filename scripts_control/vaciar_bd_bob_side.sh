#!/usr/bin/env bash
set -euo pipefail

echo "[QKD] Vaciando datos locales de Bob side..."

echo "[QKD] Vaciando clave local de Bob..."

docker exec bob mysql --skip-ssl -u QKD QKD_keys_KMS1 -e "TRUNCATE TABLE QKD_keys;"

echo "[QKD] Bob side limpiado correctamente."