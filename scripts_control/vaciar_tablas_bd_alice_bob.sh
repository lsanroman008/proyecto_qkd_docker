#!/usr/bin/env bash
set -e

source "$(dirname "${BASH_SOURCE[0]}")/leer_ips.sh"
USER_REMOTO="${USER_REMOTO:-$USER}"

echo "[QKD] Vaciando bases de datos en Alice ($ALICE_HOST)..."
ssh "${USER_REMOTO}@${ALICE_HOST}" "docker exec -i monitor mysql --skip-ssl -u QKD QKD_netsquid <<'SQL'
SET FOREIGN_KEY_CHECKS=0;
TRUNCATE TABLE BB84_simstats;
TRUNCATE TABLE BB84_rondas;
TRUNCATE TABLE BB84_configuracion;
TRUNCATE TABLE QKD_keys_alice;
TRUNCATE TABLE QKD_keys_bob;
SET FOREIGN_KEY_CHECKS=1;
SQL
docker exec alice mysql --skip-ssl -u QKD QKD_keys_KMS1 -e 'TRUNCATE TABLE QKD_keys;'"

echo "[QKD] Vaciando base de datos en Bob ($BOB_HOST)..."
ssh "${USER_REMOTO}@${BOB_HOST}" "docker exec bob mysql --skip-ssl -u QKD QKD_keys_KMS1 -e 'TRUNCATE TABLE QKD_keys;'"

echo "[QKD] Bases de datos vaciadas."
