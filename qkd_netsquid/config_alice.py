### CONFIGURACIÓN DE PARÁMETROS DE ALICE ###
import qkd_hosts as hosts

### PARÁMETROS DE SESIÓN ###
NUM_QUBITS = 512  # Tiene que coincidir con CONFIG_BOB.py y CONFIG_NETSQUID.py
NUM_CLAVES = 10    # Tiene que coincidir con CONFIG_BOB.py y CONFIG_NETSQUID.py
QBER_ABORT_THRESHOLD = 11.0  # QBER verificación > QBER_ABORT_THRESHOLD descarta la ronda


### SOCKETS ###
# Alice y NetSquid están en la misma máquina y en la misma red Docker.
# Por eso Alice usa el nombre del contenedor netsquid, no la IP física.
SERVIDOR_IP = hosts.NETSQUID_DOCKER_HOST
SERVIDOR_PUERTO = hosts.NETSQUID_PORT

# Alice escucha conexiones de Bob. 0.0.0.0 permite aceptar conexiones externas.
ALICE_IP = "0.0.0.0"
ALICE_PUERTO_SIFTING = hosts.ALICE_PUERTO_SIFTING
ALICE_PUERTO_QBER = hosts.ALICE_PUERTO_QBER
ALICE_PUERTO_SAVEKEY = hosts.ALICE_PUERTO_SAVEKEY

ALICE_PUERTO_CLASICO = ALICE_PUERTO_SIFTING
SOCKET_TIMEOUT = hosts.SOCKET_TIMEOUT


### AMPLIFICACIÓN DE PRIVACIDAD (PA) ###
PRIVACY_AMPLIFICATION = True
PA_METHOD = "TOEPLITZ"
FINAL_KEY_BITS = 256
PRE_PA_KEY_BITS = 512


### BASE DE DATOS ALICE ###
# Base local dentro del contenedor Alice.
ALICE_DB_HOST = "127.0.0.1"
ALICE_DB_PORT = hosts.LOCAL_DB_PORT
ALICE_DB_USER = "QKD"
ALICE_DB_PASSWORD = ""
ALICE_DB_NAME = "QKD_keys_KMS1"


### BASE DE DATOS MONITOR ###
# Alice accede al monitor por nombre Docker porque está en la misma red Docker.
QKD_DB_HOST = hosts.MONITOR_DOCKER_HOST
QKD_DB_PORT = hosts.MONITOR_DB_PORT_INTERNO
QKD_DB_USER = "QKD"
QKD_DB_PASSWORD = ""
QKD_DB_NAME = "QKD_netsquid"

MONITOR_DB_HOST = hosts.MONITOR_DOCKER_HOST
MONITOR_DB_PORT = hosts.MONITOR_DB_PORT_INTERNO
MONITOR_DB_USER = "QKD"
MONITOR_DB_PASSWORD = ""
MONITOR_DB_NAME = "QKD_netsquid"
MONITOR_ALICE_KEYS_TABLE = "QKD_keys_alice"
MIRROR_KEYS_TO_MONITOR = True


### MENSAJES EN PANTALLA ###
VERBOSE_ALICE = False
