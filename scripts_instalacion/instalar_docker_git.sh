# Ejecutar en la maquina remota Alice y Bob una vez conectado por SSH
sudo apt update

#instalar docker y docker-compose
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Agregar el usuario que invocó la instalación al grupo docker para usar docker sin sudo
TARGET_USER="${SUDO_USER:-$USER}"
sudo usermod -aG docker "$TARGET_USER"
echo "[QKD] El usuario $TARGET_USER fue añadido al grupo docker. Cierra sesión y vuelve a entrar para aplicar el cambio."

# instalar git para clonar el repositorio proyecto_qkd_docker
sudo apt install -y git

# Verificar la instalación de Docker y Docker Compose

docker --version
docker compose version

# permisos de ejecución para los scripts de instalación y control
PROYECTO="$HOME/proyecto_qkd_docker"

if [ -d "$PROYECTO" ]; then
  find "$PROYECTO" -type f -name "*.sh" -exec chmod +x {} \;
fi