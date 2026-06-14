#!/usr/bin/env bash
set -e

# Asegurarse de que el usuario está en el grupo docker
if ! groups | grep -qw docker; then
    echo "[QKD] Agregando $USER al grupo docker..."
    sudo usermod -aG docker "$USER"
     echo "[QKD] Hecho. Abre una terminal nueva o ejecuta: newgrp docker, después vuleve a ejecutar este script."
    exit 0
fi

# Ejecutar en la maquina remota Alice una vez conectado por SSH
# Despliega solo los servicios que deben vivir en Alice:
# alice + netsquid + monitor/Grafana/MariaDB.

QKD_HOME="${QKD_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$QKD_HOME"

mkdir -p db_alice db_monitor grafana_data logs
chmod +x entrypoint.qkd.sh start-monitor.sh scripts_instalacion/*.sh scripts_control/*.sh 2>/dev/null || true

echo "[QKD] Construyendo servicios lado Alice..."
docker compose -f docker-compose.build.yaml build alice netsquid monitor

echo "[QKD] Levantando servicios lado Alice..."
docker compose -f docker-compose.build.yaml up -d alice netsquid monitor

echo "[QKD] Estado de contenedores:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo
echo "[QKD] Servicios lado Alice desplegados exitosamente."
