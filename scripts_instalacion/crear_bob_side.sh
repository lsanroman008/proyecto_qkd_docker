#!/usr/bin/env bash
set -e

# Asegurarse de que el usuario está en el grupo docker
if ! groups | grep -qw docker; then
    echo "[QKD] Agregando $USER al grupo docker..."
    sudo usermod -aG docker "$USER"
    echo "[QKD] Hecho. Abre una terminal nueva o ejecuta: newgrp docker, después vuleve a ejecutar este script."
    exit 0
fi

# Ejecutar en la maquina Bob una vez conectado por SSH
# Despliega solo el servicio bob.

QKD_HOME="${QKD_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$QKD_HOME"

mkdir -p db_bob logs
chmod +x entrypoint.qkd.sh scripts_instalacion/*.sh scripts_control/*.sh 2>/dev/null || true

#echo "[QKD] Construyendo servicio Bob..."
#docker compose build bob

echo "[QKD] Levantando servicio Bob..."
docker compose up -d bob

echo "[QKD] Estado de contenedores:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
