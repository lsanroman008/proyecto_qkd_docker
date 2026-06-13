### GUARDAR CLAVE DE ALICE EN SU BASE DE DATOS ###
import os
import base64
import mysql.connector
# Configuración de Alice:
try:
    import config_alice as config
except ImportError:
    config = None


# Busca variable de conf y convierte en boolean:
def bool_cfg(name, default=False):
    value = os.getenv(name)
    # Busca en el config:
    if value is None:
        value = cfg(name, default)
    # Cambia a boolean:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "si", "sí", "on")

# Buscar variable en config:
def cfg(name, default):
    return getattr(config, name, default) if config is not None else default


# Diccionario con datos de conexión de la base de datos de ALICE:
DB_CONFIG_ALICE = {
    "host": os.getenv("ALICE_DB_HOST", os.getenv("DB_HOST", str(cfg("ALICE_DB_HOST", "127.0.0.1")))),
    "port": int(os.getenv("ALICE_DB_PORT", os.getenv("DB_PORT", str(cfg("ALICE_DB_PORT", 3306))))),
    "user": os.getenv("ALICE_DB_USER", os.getenv("DB_USER", str(cfg("ALICE_DB_USER", "QKD")))),
    "database": os.getenv("ALICE_DB_NAME", os.getenv("DB_NAME", str(cfg("ALICE_DB_NAME", "QKD_keys_KMS1")))),
    "password": os.getenv("ALICE_DB_PASSWORD", os.getenv("DB_PASSWORD", str(cfg("ALICE_DB_PASSWORD", "")))),
}

#  Diccionario con datos de conexión de la base de datos de MONITOR:
DB_CONFIG_MONITOR = {
    "host": os.getenv("MONITOR_DB_HOST", str(cfg("MONITOR_DB_HOST", "monitor"))),
    "port": int(os.getenv("MONITOR_DB_PORT", str(cfg("MONITOR_DB_PORT", 3306)))),
    "user": os.getenv("MONITOR_DB_USER", str(cfg("MONITOR_DB_USER", "QKD"))),
    "database": os.getenv("MONITOR_DB_NAME", str(cfg("MONITOR_DB_NAME", "QKD_netsquid"))),
    "password": os.getenv("MONITOR_DB_PASSWORD", str(cfg("MONITOR_DB_PASSWORD", ""))),
}

# Tabla del monitor donde se guardarán las claves de Alice:
MONITOR_ALICE_KEYS_TABLE = os.getenv(
    "MONITOR_ALICE_KEYS_TABLE",
    str(cfg("MONITOR_ALICE_KEYS_TABLE", "QKD_keys_alice")),
)
# Ver si ALICE copia la clave en el monitor:
# True = copia en el monitor
# False = no copia (solo en su base de datos)
MIRROR_KEYS_TO_MONITOR = bool_cfg("MIRROR_KEYS_TO_MONITOR", True)


### MAIN DEL PASO FINAL ###
def clave_final_alice_con_id(key_bits, key_id, iteration, id_configuracion=None):
    key_id = normalizar_key_id(key_id)
    base64_key = bits_to_base64(key_bits)

    cnx = None
    try:
        print(f"[ALICE] Guardando clave propia con UID recibida de Bob: {key_id}")
        print(f"[ALICE] DB local Alice: {describe_db_config(DB_CONFIG_ALICE)}")

        cnx = mysql.connector.connect(**DB_CONFIG_ALICE)
        # Actualiza clave en la base de datos:
        insert_clave(cnx, "QKD_keys", key_id, base64_key)
        cnx.commit()
        print(f"[ALICE] Clave propia GUARDADA en QKD_keys_KMS1.QKD_keys")

        # Escribe clave de Alice en el monitor:
        clave_alice_a_monitor(key_id, base64_key)

        # Devolvemos ok si todo sale bien:
        return True

    except Exception as err:
        print(f"[ALICE] ERROR guardando clave propia en base Alice: {err}")
        return False

    finally:
        if cnx is not None:
            cnx.close()
        print("[ALICE] Conexión BD Alice cerrada")


## FUNCIONES ##
# Valida UUID recibida de Bob:
def normalizar_key_id(key_id) -> str:
    # Si viene como bytes, decodifica a string:
    if isinstance(key_id, bytes):
        key_id = key_id.decode("utf-8")
    # Comprueba que sea string y que no esté vacio:
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("key_id inválido recibido desde Bob")
    key_id = key_id.strip()
    if len(key_id) > 40:
        raise ValueError(f"key_id demasiado largo para QKD_keys.key_id VARCHAR(40): {len(key_id)}")
    return key_id

# Convierte BITS de lista -> texto
def bits_to_base64(key_bits) -> str:
    key_str = "".join(map(str, key_bits)) if isinstance(key_bits, list) else str(key_bits)
    if not key_str:
        raise ValueError("clave vacía")
    if any(ch not in "01" for ch in key_str):
        raise ValueError("la clave debe contener solo bits 0/1")
    # String binario a bytes:
    binary_bytes = int(key_str, 2).to_bytes((len(key_str) + 7) // 8, byteorder="big")
    # Bytes -> base64 -> string:
    return base64.b64encode(binary_bytes).decode("utf-8")


def describe_db_config(db_config) -> str:
    return (
        f"host={db_config.get('host')} "
        f"port={db_config.get('port')} "
        f"user={db_config.get('user')} "
        f"database={db_config.get('database')}"
    )

# Actualiza clave en la base de datos:
def insert_clave(cnx, table_name, key_id, base64_key):
    table_name = valid_table_name(table_name)
    cursor = cnx.cursor()
    try:
        cursor.execute(
            f"""
            INSERT INTO {table_name} (key_id, key_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                key_value = VALUES(key_value)
            """,
            (key_id, base64_key),
        )
    finally:
        cursor.close()

# Comprueba nombre de la tabla:
def valid_table_name(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"Nombre de tabla no seguro: {name}")
    return name

# Copia clave de Alice en monitor
def clave_alice_a_monitor(key_id, base64_key):
    if not MIRROR_KEYS_TO_MONITOR:
        return True
    cnx = None
    try:
        cnx = mysql.connector.connect(**DB_CONFIG_MONITOR)
        insert_clave(cnx, MONITOR_ALICE_KEYS_TABLE, key_id, base64_key)
        cnx.commit()
        print(f"[ALICE] Copia monitor GUARDADA en {MONITOR_ALICE_KEYS_TABLE}")
        return True
    except Exception as err:
        print(f"[ALICE] AVISO: no se pudo copiar clave Alice al monitor: {err}")
        return False
    finally:
        if cnx is not None:
            cnx.close()

