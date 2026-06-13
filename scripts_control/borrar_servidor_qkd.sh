#!/usr/bin/env bash
set -e

echo "============================================================"
echo " LIMPIEZA SERVIDOR QKD"
echo "============================================================"
echo
echo "Este script puede:"
echo "  - Parar y borrar todos los contenedores Docker"
echo "  - Borrar todas las imágenes Docker"
echo "  - Borrar volúmenes y redes Docker"
echo "  - Opcionalmente desinstalar Docker y sus dependencias"
echo "  - Opcionalmente desinstalar Git"
echo

read -p "¿Quieres borrar TODOS los contenedores, imágenes, volúmenes y redes Docker? Escribe SI: " BORRAR_DOCKER_DATOS

if [ "$BORRAR_DOCKER_DATOS" = "SI" ]; then

    echo
    echo "[1/5] Parando contenedores..."
    if command -v docker >/dev/null 2>&1; then
        docker ps -aq | xargs -r docker stop || true
    else
        echo "Docker no está instalado o no está en PATH."
    fi

    echo
    echo "[2/5] Borrando contenedores..."
    if command -v docker >/dev/null 2>&1; then
        docker ps -aq | xargs -r docker rm -f || true
    fi

    echo
    echo "[3/5] Borrando imágenes..."
    if command -v docker >/dev/null 2>&1; then
        docker images -aq | xargs -r docker rmi -f || true
    fi

    echo
    echo "[4/5] Borrando volúmenes..."
    if command -v docker >/dev/null 2>&1; then
        docker volume ls -q | xargs -r docker volume rm -f || true
    fi

    echo
    echo "[5/5] Limpieza general de Docker..."
    if command -v docker >/dev/null 2>&1; then
        docker system prune -a --volumes -f || true
    fi

    echo
    echo "[OK] Contenedores, imágenes, volúmenes y redes Docker eliminados."
else
    echo
    echo "[INFO] No se han borrado contenedores ni imágenes Docker."
fi

echo
read -p "¿Quieres DESINSTALAR Docker y sus paquetes/dependencias? Escribe SI: " DESINSTALAR_DOCKER

if [ "$DESINSTALAR_DOCKER" = "SI" ]; then

    echo
    echo "[DOCKER] Parando servicios..."
    sudo systemctl stop docker 2>/dev/null || true
    sudo systemctl stop containerd 2>/dev/null || true

    echo
    echo "[DOCKER] Desinstalando paquetes Docker..."
    sudo apt purge -y \
        docker-ce \
        docker-ce-cli \
        docker-ce-rootless-extras \
        docker-buildx-plugin \
        docker-compose-plugin \
        docker.io \
        docker-compose \
        docker-compose-v2 \
        containerd.io \
        containerd \
        runc \
        podman-docker \
        2>/dev/null || true

    echo
    echo "[DOCKER] Eliminando dependencias no usadas..."
    sudo apt autoremove -y
    sudo apt autoclean -y

    echo
    echo "[DOCKER] Eliminando datos internos de Docker..."
    sudo rm -rf /var/lib/docker
    sudo rm -rf /var/lib/containerd
    sudo rm -rf /etc/docker
    sudo rm -rf /run/docker
    sudo rm -rf /run/containerd

    echo
    echo "[DOCKER] Eliminando repositorio Docker de APT..."
    sudo rm -f /etc/apt/sources.list.d/docker.list
    sudo rm -f /etc/apt/keyrings/docker.gpg
    sudo rm -f /etc/apt/keyrings/docker.asc

    if getent group docker >/dev/null 2>&1; then
        echo "[DOCKER] Eliminando grupo docker..."
        sudo groupdel docker || true
    fi

    echo
    echo "[DOCKER] Actualizando APT..."
    sudo apt update

    echo
    echo "[OK] Docker y sus dependencias han sido desinstalados."
else
    echo
    echo "[INFO] Docker sigue instalado."
fi

echo
read -p "¿Quieres desinstalar también Git? Escribe SI: " DESINSTALAR_GIT

if [ "$DESINSTALAR_GIT" = "SI" ]; then
    echo
    echo "[GIT] Desinstalando Git..."
    sudo apt purge -y git git-man || true
    sudo apt autoremove -y
    sudo apt autoclean -y
    echo "[OK] Git desinstalado."
else
    echo
    echo "[INFO] Git se mantiene instalado."
fi

echo
echo "============================================================"
echo " LIMPIEZA FINALIZADA"
echo "============================================================"
echo
echo "Comprobaciones recomendadas:"
echo "  docker --version"
echo "  docker compose version"
echo "  git --version"
echo
echo "Si Docker se ha desinstalado correctamente, los comandos de Docker deberían indicar que no existen."