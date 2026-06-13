#!/usr/bin/env bash
set -euo pipefail

echo "[QKD] Vaciando datos locales de Alice side..."

echo "[QKD] Vaciando base de datos del monitor, excepto QKD_keys_bob..."

docker exec -i monitor mysql --skip-ssl -u QKD QKD_netsquid <<'SQL'
SET FOREIGN_KEY_CHECKS=0;
TRUNCATE TABLE BB84_simstats;
TRUNCATE TABLE BB84_rondas;
TRUNCATE TABLE BB84_configuracion;
TRUNCATE TABLE QKD_keys_alice;
TRUNCATE TABLE QKD_keys_bob;
SET FOREIGN_KEY_CHECKS=1;
SQL

echo "[QKD] Vaciando clave local de Alice..."

docker exec alice mysql --skip-ssl -u QKD QKD_keys_KMS1 -e "TRUNCATE TABLE QKD_keys;"

echo "[QKD] Alice side limpiado correctamente."