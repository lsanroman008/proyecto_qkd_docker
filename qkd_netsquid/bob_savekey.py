### GUARDAR CLAVE DE BOB EN SU BASE DE DATOS ###
import os
import uuid
import base64
import mysql.connector

try:
    import config_bob as config
except ImportError:
    config = None

# Busca variable de conf y convierte en boolean:
def bool_cfg(name, default=False):
    value = os.getenv(name)
    if value is None:
        value = cfg(name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "si", "sí", "on")


# Buscar variable en config:
def cfg(name, default):
    return getattr(config, name, default) if config is not None else default


# Diccionario con datos de conexión de la base de datos de BOB:
DB_CONFIG_BOB = {
    "host": os.getenv("BOB_DB_HOST", os.getenv("QKD_BOB_DB_HOST", str(cfg("BOB_DB_HOST", "127.0.0.1")))),
    "port": int(os.getenv("BOB_DB_PORT", os.getenv("QKD_BOB_DB_PORT", str(cfg("BOB_DB_PORT", 3306))))),
    "user": os.getenv("BOB_DB_USER", os.getenv("QKD_BOB_DB_USER", str(cfg("BOB_DB_USER", "QKD")))),
    "database": os.getenv("BOB_DB_NAME", os.getenv("QKD_BOB_DB_NAME", str(cfg("BOB_DB_NAME", "QKD_keys_KMS1")))),
    "password": os.getenv("BOB_DB_PASSWORD", os.getenv("QKD_BOB_DB_PASSWORD", str(cfg("BOB_DB_PASSWORD", "")))),
}

#  Diccionario con datos de conexión de la base de datos de MONITOR:
DB_CONFIG_MONITOR = {
    "host": os.getenv("MONITOR_DB_HOST", str(cfg("MONITOR_DB_HOST", "monitor"))),
    "port": int(os.getenv("MONITOR_DB_PORT", str(cfg("MONITOR_DB_PORT", 3306)))),
    "user": os.getenv("MONITOR_DB_USER", str(cfg("MONITOR_DB_USER", "QKD"))),
    "database": os.getenv("MONITOR_DB_NAME", str(cfg("MONITOR_DB_NAME", "QKD_netsquid"))),
    "password": os.getenv("MONITOR_DB_PASSWORD", str(cfg("MONITOR_DB_PASSWORD", ""))),
}

# Tabla del monitor donde se guardarán las claves de Bob:
MONITOR_BOB_KEYS_TABLE = os.getenv(
    "MONITOR_BOB_KEYS_TABLE",
    str(cfg("MONITOR_BOB_KEYS_TABLE", "QKD_keys_bob")),
)

# Ver si BOB copia la clave en el monitor:
# True = copia en el monitor
# False = no copia (solo en su base de datos)
MIRROR_KEYS_TO_MONITOR = bool_cfg("MIRROR_KEYS_TO_MONITOR", True)


### MAIN DEL PASO FINAL ###
def clave_final_bob_db(clave_acumulada, iteration, id_configuracion=None, key_id=None):
    final_key_bits = int(cfg("FINAL_KEY_BITS", 256))
    if len(clave_acumulada) < final_key_bits:
        print(f"[BOB] ERROR: clave acumulada menor de {final_key_bits} bits")
        return None

    key_bits = clave_acumulada[:final_key_bits]
    base64_key = bits_to_base64(key_bits)

    key_id = str(key_id).strip() if key_id else str(uuid.uuid4())
    if not key_id or len(key_id) > 40:
        print(f"[BOB] ERROR: key_id inválido: {key_id}")
        return None

    cnx = None
    try:
        print(f"[BOB] Guardando clave propia con UID generada: {key_id}")
        print(f"[BOB] DB local Bob: {describe_db_config(DB_CONFIG_BOB)}")

        cnx = mysql.connector.connect(**DB_CONFIG_BOB)
        # Actualiza clave en la base de datos:
        insert_clave(cnx, "QKD_keys", key_id, base64_key)
        cnx.commit()

        print(f"[BOB] Clave propia GUARDADA en QKD_keys_KMS1.QKD_keys")
        # Escribe clave de Bob en el monitor:
        clave_bob_a_monitor(key_id, base64_key)
        return key_id

    except Exception as err:
        print(f"[BOB] ERROR guardando clave propia en base Bob: {err}")
        return None

    finally:
        if cnx is not None:
            cnx.close()
        print("[BOB] Conexión a la base de datos de Bob cerrada")



# Conveirte BITS de lista -> texto
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

# Copia clave de Bob en monitor
def clave_bob_a_monitor(key_id, base64_key):
    if not MIRROR_KEYS_TO_MONITOR:
        return True
    cnx = None
    try:
        cnx = mysql.connector.connect(**DB_CONFIG_MONITOR)
        insert_clave(cnx, MONITOR_BOB_KEYS_TABLE, key_id, base64_key)
        cnx.commit()
        print(f"[BOB] Copia monitor GUARDADA en {MONITOR_BOB_KEYS_TABLE}")
        return True
    except Exception as err:
        print(f"[BOB] AVISO: no se pudo copiar clave Bob al monitor: {err}")
        return False
    finally:
        if cnx is not None:
            cnx.close()


