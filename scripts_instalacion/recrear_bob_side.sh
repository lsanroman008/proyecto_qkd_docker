#!/usr/bin/env bash
set -e

# Asegurarse de que el usuario está en el grupo docker
if ! groups | grep -qw docker; then
    echo "[QKD] Agregando $USER al grupo docker..."
    sudo usermod -aG docker "$USER"
  echo "[QKD] Hecho. Abre una terminal nueva o ejecuta: newgrp docker, después vuleve a ejecutar este script."
    exit 0
fi

# Reinicia el contenedor Bob sin borrar datos persistentes.
# Ejecutar en la maquina remota Bob una vez conectado por SSH
QKD_HOME="${QKD_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$QKD_HOME"

docker compose stop bob || true
docker compose rm -f bob || true
docker compose up -d --force-recreate bob
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
