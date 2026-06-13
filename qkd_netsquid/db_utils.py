### BASE DE DATOS_UTILS ###
# Para dar acceso a la todas las funciones relacionadas con la base de datos
import os
from typing import Any, Optional
import mysql.connector

### IMPORTAR ARCHIVO CONF NETSQUID ###
try:
    import config_netsquid as _config_netsquid
except ImportError:
    _config_netsquid = None
### IMPORTAR ARCHIVO CONF ALICE ###
try:
    import config_alice as _config_alice
except ImportError:
    _config_alice = None


def conf_variable(name, default):
    for module in (_config_netsquid, _config_alice):
        # Comprueba si ese modulo tiene la variable name:
        if module is not None and hasattr(module, name):
            # Si la tiene, devuelve el valor:
            return getattr(module, name)
    # Si no la tiene devuelve por defecto:
    return default


DB_CONFIG = {
    "host": os.getenv("QKD_DB_HOST", os.getenv("MONITOR_DB_HOST", os.getenv("DB_HOST", str(conf_variable("QKD_DB_HOST", "monitor"))))),
    "port": int(os.getenv("QKD_DB_PORT", os.getenv("MONITOR_DB_PORT", os.getenv("DB_PORT", str(conf_variable("QKD_DB_PORT", 3306)))))),
    "user": os.getenv("QKD_DB_USER", os.getenv("MONITOR_DB_USER", os.getenv("DB_USER", str(conf_variable("QKD_DB_USER", "QKD"))))),
    "database": os.getenv("QKD_DB_NAME", os.getenv("MONITOR_DB_NAME", os.getenv("DB_NAME", str(conf_variable("QKD_DB_NAME", "QKD_netsquid"))))),
    "password": os.getenv("QKD_DB_PASSWORD", os.getenv("MONITOR_DB_PASSWORD", os.getenv("DB_PASSWORD", str(conf_variable("QKD_DB_PASSWORD", ""))))),
}


# FUNCIÓN IMPORTANTE: abre conexión, crea cursor, ejecuta query, cierra 
def execute(query: str, params: tuple = (), *, conn=None, fetchone: bool = False):
    # (query a ejecutar - valores de %s - los siguientes parámetros obligatorios - conexión opcional - True devuelve fila, False rowcount)
    own_conn = conn is None
    cnx = conn or get_db_connection()
    cursor = None
    try:
        cursor = cnx.cursor()
        # Ejecuta el query:
        cursor.execute(query, params)
        # Devuelve una fila con True:
        if fetchone:
            return cursor.fetchone()
        #Actualizar BD:
        if own_conn:
            cnx.commit()
        # Número de filas afectadas (rowcount) 0 = ninguna, 1 = una, 2 = más de una (error)
        return cursor.rowcount 
    # Cerramos:
    finally:
        if cursor is not None:
            cursor.close()
        if own_conn and cnx is not None:
            cnx.close()


### FUNCIONES DB ###
# Devuelve la conexión a Netsquid, a crear_configuracion:
def get_db_connection(autocommit: bool = True):
    # Abre conexión con parámetros definidos en DB_CONFIG
    conn = mysql.connector.connect(**DB_CONFIG)
    # Para guardar los parámetros automaticamente:
    conn.autocommit = autocommit
    # Devuelve la conexión abierta:
    return conn

# CREAR FILA EN BB84_CONFIGURACION y DEVUELVE id_configuracion
# Son parámetros que están definidos como constantes ya
def crear_configuracion(err_config, qber_sample_ratio: float, bits_objetivo: int, conn=None) -> Optional[int]:
    own_conn = conn is None
    cnx = conn or get_db_connection()
    cursor = None

    # Inserta nueva fila:
    query = """
        INSERT INTO BB84_configuracion (
            bits_objetivo,
            distancia_km, atenuacion_db_km, velocidad_fibra_km_s, prob_loss_in,
            usar_depolarizacion, despolarizacion,
            usar_dephase, dephase,
            usart1t2_noise, T1_ns, T2_ns,
            eve_activa, eve_percentage_intercepted, eve_error_rate,
            bits_verificados_pct,
            usar_measure_faulty, prob_error_medicion_0, prob_error_medicion_1,
            usar_detector_efficiency, detector_efficiency,
            usar_misalignment, misalignment_prob,
            usar_dark_counts_reales, prob_dark_count_real,
            usar_jitter_basico, jitter_prob_perdida
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    # Errores cogidos de config_errores:
    #los int() -> pasan de boolean a 1/0
    values = (
        bits_objetivo,

        err_config.distancia,
        err_config.atenuacion,
        err_config.velocidad_fibra,
        err_config.prob_loss_in,

        int(err_config.usar_depolarizacion),
        err_config.despolarizacion,
        int(err_config.usar_dephase),
        err_config.dephase,
        int(err_config.usart1t2_noise),
        err_config.T1_ns,
        err_config.T2_ns,
        int(err_config.eve_activa),
        err_config.eve_percentage_intercepted,
        err_config.eve_error_rate,
        int(round(qber_sample_ratio * 100)),

        int(getattr(err_config, "usar_measure_faulty", False)),
        getattr(err_config, "prob_error_medicion_0", 0.0),
        getattr(err_config, "prob_error_medicion_1", 0.0),

        int(getattr(err_config, "usar_detector_efficiency", False)),
        getattr(err_config, "detector_efficiency", 1.0),

        int(getattr(err_config, "usar_misalignment", False)),
        getattr(err_config, "misalignment_prob", 0.0),

        int(getattr(err_config, "usar_dark_counts_reales", False)),
        getattr(err_config, "prob_dark_count_real", 0.0),

        int(getattr(err_config, "usar_jitter_basico", False)),
        getattr(err_config, "jitter_prob_perdida", 0.0),
    )

    # INSERT:
    try:
        cursor = cnx.cursor()
        cursor.execute(query, values)
        if own_conn:
            cnx.commit()
        return cursor.lastrowid # devuelve id de la fila insertada: id_configuration
    
    # Se cierra conexión:
    finally:
        if cursor is not None:
            cursor.close()
        if own_conn and cnx is not None:
            cnx.close()

# ABORTADA BB84_configuracion: Se crea una sesión pero Alice no se conecta o se interrumpe: (-> int, devuelve un entero rowcount)
def marcar_configuracion_abortada(id_configuracion: int, total_rondas: int = 0, tiempo_total_sesion: float | None = None, conn=None) -> int:
    if tiempo_total_sesion is None:
        query = """
            UPDATE BB84_configuracion
            SET estado = 'abortada',
                total_rondas = %s
            WHERE id_configuracion = %s
              AND estado = 'en_progreso'
        """
        params = (total_rondas, id_configuracion)
    else:
        query = """
            UPDATE BB84_configuracion
            SET estado = 'abortada',
                tiempo_total_sesion = %s,
                total_rondas = %s
            WHERE id_configuracion = %s
              AND estado = 'en_progreso'
        """
        params = (round(tiempo_total_sesion, 2), total_rondas, id_configuracion)

    return execute(query, params, conn=conn)

# FILA PROVISONAL de BB84_RONDAS: 
def crear_ronda_pendiente(id_configuracion: int, numero_ronda: int, qubits_enviados: int, conn=None) -> int:
    query = """
        INSERT INTO BB84_rondas
            (id_configuracion, numero_ronda, qubits_enviados, ronda_abortada)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            qubits_enviados = VALUES(qubits_enviados)
    """
    # ronda_abortada: 0 = completa, 1 = abortada, 2 = pendiente
    # se pone ronda_aboratada = 2
    return execute(query, (id_configuracion, numero_ronda, qubits_enviados, 2), conn=conn)

# ABORTAR RONDAS PENDIENTES: por interrupción o error
def cerrar_rondas_pendientes(id_configuracion: int, bits_acumulados: int, conn=None) -> int:
    if id_configuracion is None:
        return 0
    query = """
        UPDATE BB84_rondas
        SET
            ronda_abortada = 1,
            bits_validos = 0,
            bits_acumulados = %s
        WHERE id_configuracion = %s
          AND (
               ronda_abortada = 2
               OR qber_verificacion IS NULL
               OR bits_validos IS NULL
               OR bits_acumulados IS NULL
          )
    """
    return execute(query, (bits_acumulados, id_configuracion), conn=conn)


# ACTUALIZAR RONDA CON RESULTADOS DE QBER: ronda abortada o no
def actualizar_ronda_qber(
    id_configuracion: int,
    numero_ronda: int,
    qber_verificacion: float,
    bits_acumulados: int,
    bits_validos: int,
    ronda_abortada: int,
    qber_revelados_bits: int | None = None,
    tiempo_ronda_seg: float | None = None,
    conn=None,
) -> int:
    query = """
        UPDATE BB84_rondas
        SET tiempo_ronda_seg = COALESCE(%s, tiempo_ronda_seg),
            qber_verificacion = %s,
            qber_revelados_bits = %s,
            bits_acumulados = %s,
            bits_validos = %s,
            ronda_abortada = %s
        WHERE id_configuracion = %s
            AND numero_ronda = %s
    """
    return execute(
        query,
        (
            tiempo_ronda_seg,
            round(qber_verificacion, 2),
            qber_revelados_bits,
            bits_acumulados,
            bits_validos,
            ronda_abortada,
            id_configuracion,
            numero_ronda,
        ),
        conn=conn,
    )


# ACTUALIZAR RONDA CON RECONCILIACION Y CONFIRMACIÓN:
def actualizar_ronda_reconciliacion(
    id_configuracion: int,
    numero_ronda: int,
    reconciliacion_ok: bool,
    correcciones: int = 0,
    leakage_bits: int = 0,
    hash_match: bool = False,
    bits_post_qber: int | None = None,
    bits_post_reconciliacion: int | None = None,
    conn=None,
) -> int:

    query = """
        UPDATE BB84_rondas
        SET reconciliacion_ok = %s,
            reconciliacion_correcciones = %s,
            reconciliacion_leakage_bits = %s,
            reconciliacion_hash_match = %s,
            bits_post_qber = %s,
            bits_post_reconciliacion = %s
        WHERE id_configuracion = %s
          AND numero_ronda = %s
    """
    return execute(
        query,
        (
            1 if reconciliacion_ok else 0,
            int(correcciones or 0),
            int(leakage_bits or 0),
            1 if hash_match else 0,
            bits_post_qber,
            bits_post_reconciliacion,
            id_configuracion,
            numero_ronda,
        ),
        conn=conn,
    )

# ACTUALIZAR UMBRAL QBER USADO POR ALICE EN LA SESIÓN
def actualizar_configuracion_qber_threshold(
    id_configuracion: int,
    qber_abort_threshold: float,
    conn=None,
) -> int:
    if id_configuracion is None:
        return 0

    query = """
        UPDATE BB84_configuracion
        SET qber_abort_threshold = %s
        WHERE id_configuracion = %s
    """

    return execute(
        query,
        (
            round(float(qber_abort_threshold), 2),
            id_configuracion,
        ),
        conn=conn,
    )

# ACTUALIZAMOS cuando se ha llegado a la clave final:
def marcar_configuracion_completada(id_configuracion: int, tiempo_total_sesion: float, total_rondas: int, conn=None) -> int:
    query = """
        UPDATE BB84_configuracion
        SET estado = 'completada',
            tiempo_total_sesion = %s,
            total_rondas = %s
        WHERE id_configuracion = %s
    """
    return execute(query, (round(tiempo_total_sesion, 2), total_rondas, id_configuracion), conn=conn)


# ACTUALIZA sesión COMPLETA terminada:
def actualizar_configuracion_postprocesado(
    id_configuracion: int,
    pa_metodo: str | None,
    pa_input_bits: int | None,
    pa_output_bits: int | None,
    bits_finales_guardados: int | None,
    conn=None,
) -> int:

    if id_configuracion is None:
        return 0

    pa_reduction_bits = None
    if pa_input_bits is not None and pa_output_bits is not None:
        pa_reduction_bits = int(pa_input_bits) - int(pa_output_bits)

    query = """
        UPDATE BB84_configuracion c
        SET
            c.pa_metodo = %s,
            c.pa_input_bits = %s,
            c.pa_output_bits = %s,
            c.pa_reduction_bits = %s,
            c.reconciliacion_total_correcciones = (
                SELECT COALESCE(SUM(r.reconciliacion_correcciones), 0)
                FROM BB84_rondas r
                WHERE r.id_configuracion = c.id_configuracion
            ),
            c.reconciliacion_total_leakage_bits = (
                SELECT COALESCE(SUM(r.reconciliacion_leakage_bits), 0)
                FROM BB84_rondas r
                WHERE r.id_configuracion = c.id_configuracion
            ),
            c.rondas_abortadas_reconciliacion = (
                SELECT COUNT(*)
                FROM BB84_rondas r
                WHERE r.id_configuracion = c.id_configuracion
                  AND r.reconciliacion_ok = 0
            ),
            c.bits_finales_guardados = %s
        WHERE c.id_configuracion = %s
    """
    return execute(
        query,
        (
            pa_metodo,
            pa_input_bits,
            pa_output_bits,
            pa_reduction_bits,
            bits_finales_guardados,
            id_configuracion,
        ),
        conn=conn,
    )


# Guarda parámetros de ronda:
def guardar_simstats_en_bd(db_conn, id_configuracion, numero_ronda, simstats_data):
    if not db_conn or not simstats_data:
        return False

    query = """
        INSERT INTO BB84_simstats
        (
            id_configuracion,
            numero_ronda,
            simstats_sim_time_ns
        )
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            simstats_sim_time_ns = VALUES(simstats_sim_time_ns)
    """

    values = (
        id_configuracion,
        numero_ronda,
        simstats_data.get("simstats_sim_time_ns"),
    )

    try:
        cursor = db_conn.cursor()
        cursor.execute(query, values)
        db_conn.commit()
        cursor.close()

        return True

    except Exception as e:
        print(f"[SIMSTATS] Error guardando SimStats: {e}")
        return False

# Guarda métricas cuanticas de ronda:
def guardar_metricas_cuanticas_ronda(
    id_configuracion: int,
    numero_ronda: int,
    ronda_data: dict[str, Any],
    conn=None
) -> int:

    qubits_enviados = ronda_data["qubits_enviados"]
    qubits_recibidos = ronda_data["qubits_recibidos"]
    qubits_perdidos = ronda_data["qubits_perdidos"]

    tasa_perdida = (
        round(qubits_perdidos / qubits_enviados * 100, 2)
        if qubits_enviados > 0
        else 0.0
    )

    query = """
        INSERT INTO BB84_rondas
        (
            id_configuracion,
            numero_ronda,
            qubits_enviados,
            qubits_recibidos,
            qubits_perdidos,
            tasa_perdida_pct,
            bits_sifted,
            qber_canal_cuantico,
            eve_interceptados_pct,
            ronda_abortada,

            qubits_detectados,
            qubits_no_detectados,
            errores_measure_faulty,
            errores_misalignment,
            dark_counts_generados,
            qubits_perdidos_jitter
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            qubits_enviados = VALUES(qubits_enviados),
            qubits_recibidos = VALUES(qubits_recibidos),
            qubits_perdidos = VALUES(qubits_perdidos),
            tasa_perdida_pct = VALUES(tasa_perdida_pct),
            bits_sifted = VALUES(bits_sifted),
            qber_canal_cuantico = VALUES(qber_canal_cuantico),
            eve_interceptados_pct = VALUES(eve_interceptados_pct),

            qubits_detectados = VALUES(qubits_detectados),
            qubits_no_detectados = VALUES(qubits_no_detectados),
            errores_measure_faulty = VALUES(errores_measure_faulty),
            errores_misalignment = VALUES(errores_misalignment),
            dark_counts_generados = VALUES(dark_counts_generados),
            qubits_perdidos_jitter = VALUES(qubits_perdidos_jitter)
    """

    values = (
        id_configuracion,
        numero_ronda,
        qubits_enviados,
        qubits_recibidos,
        qubits_perdidos,
        tasa_perdida,
        ronda_data["bits_sifted"],
        round(ronda_data["qber_canal_cuantico"], 2),
        round(ronda_data["eve_interceptados"], 2),
        2,

        ronda_data.get("qubits_detectados", qubits_recibidos),
        ronda_data.get("qubits_no_detectados", 0),
        ronda_data.get("errores_measure_faulty", 0),
        ronda_data.get("errores_misalignment", 0),
        ronda_data.get("dark_counts_generados", 0),
        ronda_data.get("qubits_perdidos_jitter", 0),
    )

    return execute(query, values, conn=conn)
