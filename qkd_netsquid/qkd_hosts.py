### CONFIGURACIÓN DE DESPLIEGUE EN 2 MÁQUINAS ###
# IPs físicas de las máquinas
ALICE_HOST = "10.98.1.200"
BOB_HOST = "10.98.1.82"

# NetSquid y el monitor están en la máquina Alice:
NETSQUID_HOST = ALICE_HOST
MONITOR_HOST = ALICE_HOST

# Nombres internos Docker usados SOLO dentro de la máquina Alice:
NETSQUID_DOCKER_HOST = "netsquid"
MONITOR_DOCKER_HOST = "monitor"

# Puertos del protocolo:
NETSQUID_PORT = 5000
ALICE_PUERTO_SIFTING = 6000
ALICE_PUERTO_QBER = 6001
ALICE_PUERTO_SAVEKEY = 6002

# Puertos de base de datos:
LOCAL_DB_PORT = 3306
MONITOR_DB_PORT_INTERNO = 3306      # dentro del contenedor/red Docker
MONITOR_DB_PORT_EXTERNO = 3307      # desde Bob hacia la máquina Alice

# Timeout de sockets:
SOCKET_TIMEOUT = 360
