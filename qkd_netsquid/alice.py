### ALICE - EMISOR BB84 ###
import socket
import json
import errno
import time
import signal
import sys
# Import de parámetros de Alice
import config_alice as config
# Parámetros y funciones de otros .py:
from alice_savekey import clave_final_alice_con_id
from db_utils import (
    actualizar_ronda_qber,
    actualizar_ronda_reconciliacion,
    actualizar_configuracion_postprocesado,
    actualizar_configuracion_qber_threshold,
    cerrar_rondas_pendientes,
)
from bb84_utils import (
    generar_bits,
    generar_bases,
    filtrar_ids_recibidos,
    aplicar_sifting_alice,
    calcular_qber_muestra,
    quitar_indices_test,
    paridad_bits,
    sha256_bits,
    aplicar_pa,
    generar_toeplitz_seed,
    clave_como_texto,
)
from messages import (
    msg_enviar_qubits,
    msg_sifting_ok,
    msg_qber_result_ok,
    msg_qber_result_abort,
    msg_reconciliation_parity_response,
    msg_reconciliation_result_ok,
    msg_reconciliation_fail,
)


# PARÁMETROS RONDAS, inicializadas:
CURRENT_ID_CONFIGURACION = None # número de sesión
CURRENT_CLAVE_ACUMULADA = []


### INTERRUPCIONES ###
def instalar_manejadores_senales():
    signal.signal(signal.SIGINT, signal_handler) # cntrl+C
    signal.signal(signal.SIGTERM, signal_handler) # kill

# Usuario pulsa Cntrl+C o hace un kill
def signal_handler(signum, frame):
    print(f"\n[ALICE] Señal de parada recibida ({signum}). Cerrando de forma ordenada...")
    cerrar_pendientes_seguro(motivo=f"signal_{signum}")
    sys.exit(130)

# Cierra rondas pendientes:
def cerrar_pendientes_seguro(motivo="interrupcion"):
    global CURRENT_ID_CONFIGURACION, CURRENT_CLAVE_ACUMULADA

    if CURRENT_ID_CONFIGURACION is None:
        print(f"[ALICE] Cierre seguro ({motivo}): no hay id_configuracion activo.")
        return

    try:
        bits_actuales = len(CURRENT_CLAVE_ACUMULADA)
        afectadas = cerrar_rondas_pendientes(CURRENT_ID_CONFIGURACION, bits_actuales) # función del db_utils
        print(
            f"[ALICE] Cierre seguro ({motivo}): "
            f"rondas pendientes cerradas={afectadas}, bits_acumulados={bits_actuales}"
        )
    except Exception as e:
        print(f"[ALICE] Error en cierre seguro de rondas pendientes: {e}")



### MENSAJES TCP ###
def enviar_mensaje(conn, msg):
    # Manda JSON con su tamaño primero
    data = json.dumps(msg).encode('utf-8')
    conn.sendall(len(data).to_bytes(4, byteorder='big'))
    conn.sendall(data)

def recibir_mensaje(conn):
    # Lee JSON sabiendo su tamaño
    length = int.from_bytes(conn.recv(4), byteorder='big')
    data = b''
    while len(data) < length:
        data += conn.recv(length - len(data))
    return json.loads(data.decode('utf-8'))


### CANAL CUÁNTICO FUNCIONES ###
# (1) Enviar qubits al servidor netsquid
def enviar_al_servidor(bits, bases):
    # CONEXIÓN:
    # Abrimos conexión al servidor netsquid:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(config.SOCKET_TIMEOUT)
    # Reintentos de conexión:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            sock.connect((config.SERVIDOR_IP, config.SERVIDOR_PUERTO))
            break
        except (ConnectionRefusedError, ConnectionResetError) as e:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (2 ** attempt)
                print(f"[ALICE] Conexión rechazada, reintentando en {wait_time}s... (intento {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                sock.close()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(config.SOCKET_TIMEOUT)
            else:
                raise

    # Enviamos MENSAJE al servidor netsquid:
    enviar_mensaje(sock, msg_enviar_qubits(bits, bases))

    # Esperamosa recibir mensaje del servidor:
    respuesta = recibir_mensaje(sock)
    sock.close()
    return respuesta


### POST-PROCESAMIENTO CLÁSICO ###
# (2,3) Recibir bases de Bob y comparar (SIFTING)
def escuchar_bob(alice_bits, alice_bases):
    # Abrir servidor para que Bob se conecte
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        servidor.bind((config.ALICE_IP, config.ALICE_PUERTO_SIFTING))
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            print(f"[ALICE] ERROR: Puerto {config.ALICE_PUERTO_SIFTING} en uso. Esperando...")
            time.sleep(1)
            try:
                servidor.bind((config.ALICE_IP, config.ALICE_PUERTO_SIFTING))
            except:
                print(f"[ALICE] ERROR: Puerto {config.ALICE_PUERTO_SIFTING} aún en uso. Abortando.")
                servidor.close()
                return None
        else:
            print(f"[ALICE] ERROR al abrir canal clasico: {e}")
            servidor.close()
            return None
    servidor.listen(1)


    print(f"(1) SIFTING")
    print(f"Esperando que Bob envie sus bases por puerto SIFTING {config.ALICE_PUERTO_SIFTING}...")

    # Alice recibe BASES, ID de BOB de los qubits que ha recibido:
    conn, _ = servidor.accept()

    msg = recibir_mensaje(conn)
    bases_bob = msg['bases']
    ids_recibidos = msg.get('ids_recibidos', list(range(len(alice_bases))))
    ids_recibidos = filtrar_ids_recibidos(ids_recibidos, len(alice_bases))

    # MENSAJE:
    verbose_sifting = getattr(config, "VERBOSE_ALICE", False)
    if verbose_sifting:
        print(f"[ALICE] Bob ha enviado sus bases: {bases_bob}")
        print(f"[ALICE] Bob ha recibido {len(ids_recibidos)} qubits: {ids_recibidos}")
    else:
        print(f"[ALICE] Bob ha enviado sus bases: {len(bases_bob)} bases")
        print(f"[ALICE] Bob ha recibido {len(ids_recibidos)} qubits")

    # COMPARAR BASES (sifting)
    print("\n[ALICE] Comparando bases con Bob...")

    clave, posiciones_ok, ids_perdidos = aplicar_sifting_alice(
        alice_bits=alice_bits,
        alice_bases=alice_bases,
        bases_bob=bases_bob,
        ids_recibidos=ids_recibidos,
        verbose=getattr(config, "VERBOSE_ALICE", False),
    )

    # MENSAJE:
    if ids_perdidos and verbose_sifting:
        print(f"\n[ALICE] Qubits perdidos en canal (descartados): {ids_perdidos}")
    if verbose_sifting:
        print(f"\n[ALICE] Sifting completado: {len(clave)}/{len(alice_bits)} bits validos")
        print(f"[ALICE] Enviando a Bob las posiciones correctas: {posiciones_ok}")


    # Alice envía a BOB posiciones coincidentes:
    enviar_mensaje(conn, msg_sifting_ok(posiciones_ok))

    conn.close()
    time.sleep(1.0)
    servidor.close()

    return clave, posiciones_ok

# (4) ESTIMACIÓN DE PARÁMETROS (QBER) y (5) RECONCILIACIÓN DE ERRORES y (6) CONFIRMACIÓN
def parameter_estimation(alice_bits, posiciones_sifting, clave_sifted_alice, numero_ronda, bits_acumulados_actuales, id_configuracion, tiempo_inicio_ronda=None):
    # Conectamos con Bob:
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        servidor.bind((config.ALICE_IP, config.ALICE_PUERTO_QBER))
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            print(f"[ALICE] ERROR: Puerto {config.ALICE_PUERTO_SIFTING} en uso durante Parameter Estimation. Esperando...")
            time.sleep(1)
            try:
                servidor.bind((config.ALICE_IP, config.ALICE_PUERTO_QBER))
            except:
                print(f"[ALICE] ERROR: Puerto {config.ALICE_PUERTO_QBER} aún en uso. Abortando QBER.")
                servidor.close()
                return None
        else:
            print(f"[ALICE] ERROR al abrir canal clasico para QBER: {e}")
            servidor.close()
            return None
    servidor.listen(1)

    print(f"\nEsperando bits de Bob para Estimación de Parámetros por puerto QBER {config.ALICE_PUERTO_QBER}...")
    conn, _ = servidor.accept()

    # RECIBIMOS MENSAJE de BOB:
    msg = recibir_mensaje(conn)
    posiciones_test = msg['posiciones_test']
    bits_bob_test = msg['bits_test']
    qber_revelados_bits = len(posiciones_test)

    print(f"(2) ESTIMACIÓN DE PARÁMETROS")
    # MENSAJES:
    if getattr(config, "VERBOSE_ALICE", False):
        print(f"[ALICE] Bob revela {len(posiciones_test)} bits en posiciones: {posiciones_test}")
    else:
        print(f"[ALICE] Bob revela {len(posiciones_test)} bits para QBER")

    # Calculamos QBER:
    qber, errores, total_test = calcular_qber_muestra(
        alice_bits=alice_bits,
        posiciones_sifting=posiciones_sifting,
        indices_test=posiciones_test,
        bits_bob_test=bits_bob_test,
        verbose=getattr(config, "VERBOSE_ALICE", False),
    )
    print(f"\n[ALICE] QBER = {errores}/{total_test} = {qber:.2f}%")

    # Verificar THRESHOLD de seguridad:
    umbral_qber = float(config.QBER_ABORT_THRESHOLD)
    # OPC 1: QBER alto -> abortar ronda
    if qber > umbral_qber:
        print(f"[ALICE] ALERTA! QBER ({qber:.2f}%) > {umbral_qber}%")
        print(f"[ALICE] Posible espionaje detectado -> ABORTANDO protocolo")
        
        enviar_mensaje(conn, msg_qber_result_abort(qber))

        conn.close()
        time.sleep(1.0)
        servidor.close()
        # GUARDAMOS ABORTADA: bits_acumulados = total actual (ronda no aporta nada)
        tiempo_ronda_seg = (
            round(time.time() - tiempo_inicio_ronda, 2)
            if tiempo_inicio_ronda is not None
            else None
        )
        try:
            rowcount = actualizar_ronda_qber(
                id_configuracion=id_configuracion,
                numero_ronda=numero_ronda,
                qber_verificacion=qber,
                bits_acumulados=bits_acumulados_actuales,
                bits_validos=0,
                ronda_abortada=1,
                qber_revelados_bits=qber_revelados_bits,
                tiempo_ronda_seg=tiempo_ronda_seg,
            )
            print(f"[ALICE] BD actualizada ronda abortada: rondas afectadas={rowcount}")
        except Exception as _e:
            print(f"[ALICE] Error al guardar QBER (abortada) en BD: {_e}")
        return None

    # OPC 2: QBER aceptable -> continuar
    else:
        print(f"[ALICE] QBER OK ({qber:.2f}% <= {umbral_qber}%) -> Canal seguro")
        enviar_mensaje(conn, msg_qber_result_ok(qber))

    # ELIMINAR BITS REVELADOS durante QBER:
    # posiciones_test = ÍNDICES para cálculo QBER de Bob
    clave_final = quitar_indices_test(clave_sifted_alice, posiciones_test)
    # Resultado FINAL tras el QBER:
    print(f"[ALICE] Bits revelados descartados: {len(posiciones_test)} bits")
    print(f"[ALICE] Bits restantes para reconciliación: {len(clave_final)} bits")


    # (5) CORRECCIÓN DE ERRORES (CASCADE):
    try:
        while True:
            msg_rec = recibir_mensaje(conn)
            tipo = msg_rec.get("tipo") if isinstance(msg_rec, dict) else None
            # OPC 1: Recibe request de paridad
            if tipo == "reconciliation_parity_request":
                indices = msg_rec.get("indices", [])
                # Envía paridad de su clave:
                enviar_mensaje(conn, msg_reconciliation_parity_response(paridad_bits(clave_final, indices)))
                continue

            # (6) CONFIRMACIÓN
            print("\n(3, 4) CORRECCIÓN DE ERRORES y CONFIRMACIÓN")
            # OPC 2: Recibe resultado de reconciliación (hash)
            if tipo == "reconciliation_hash":
                bob_hash = msg_rec.get("hash")
                # Hace hash de su clave:
                alice_hash = sha256_bits(clave_final)

                # OPC 1: HASH IGUALES:
                if bob_hash == alice_hash:
                    print(
                        f"[ALICE] Reconciliación OK: hash coincide "
                        f"(paridades públicas={msg_rec.get('parity_checks', 0)}, "
                        f"correcciones Bob={msg_rec.get('correcciones', 0)}, "
                        f"leakage={msg_rec.get('leakage_bits', 0)} bits)"
                    )
                    try:
                        actualizar_ronda_reconciliacion(
                            id_configuracion=id_configuracion,
                            numero_ronda=numero_ronda,
                            reconciliacion_ok=True,
                            correcciones=msg_rec.get("correcciones", 0),
                            leakage_bits=msg_rec.get("leakage_bits", 0),
                            hash_match=True,
                            bits_post_qber=len(clave_final),
                            bits_post_reconciliacion=len(clave_final),
                        )
                    except Exception as _e:
                        print(f"[ALICE] Error guardando stats de reconciliación OK: {_e}")
                    
                    # Envía mensaje de coincidencia de hash a Bob:
                    enviar_mensaje(conn, msg_reconciliation_result_ok())
                    break

                # OPC 2: HASH DISTINTOS -> reconciliación fallida:
                print("[ALICE] Reconciliación fallida: hash Bob/Alice no coincide")
                # Envía mensaje de NO coincidencia de hash a Bob:
                enviar_mensaje(conn, msg_reconciliation_fail())

                try:
                    actualizar_ronda_reconciliacion(
                        id_configuracion=id_configuracion,
                        numero_ronda=numero_ronda,
                        reconciliacion_ok=False,
                        correcciones=msg_rec.get("correcciones", 0),
                        leakage_bits=msg_rec.get("leakage_bits", 0),
                        hash_match=False,
                        bits_post_qber=len(clave_final),
                        bits_post_reconciliacion=0,
                    )
                except Exception as _e:
                    print(f"[ALICE] Error guardando stats de reconciliación fallida: {_e}")
                
                tiempo_ronda_seg = (
                    round(time.time() - tiempo_inicio_ronda, 2)
                    if tiempo_inicio_ronda is not None
                    else None
                )
                try:
                    rowcount = actualizar_ronda_qber(
                        id_configuracion=id_configuracion,
                        numero_ronda=numero_ronda,
                        qber_verificacion=qber,
                        bits_acumulados=bits_acumulados_actuales,
                        bits_validos=0,
                        ronda_abortada=1,
                        qber_revelados_bits=qber_revelados_bits,
                        tiempo_ronda_seg=tiempo_ronda_seg,
                    )
                    print(f"[ALICE] BD actualizada ronda descartada por reconciliación: rondas afectadas={rowcount}")
                except Exception as _e:
                    print(f"[ALICE] Error al guardar fallo de reconciliación en BD: {_e}")
                conn.close()
                time.sleep(1.0)
                servidor.close()
                return None
            # OPC 3: Error inesperado:
            print(f"[ALICE] Mensaje de reconciliación inesperado: {msg_rec}")
            enviar_mensaje(conn, msg_reconciliation_fail())
            
            conn.close()
            time.sleep(1.0)
            servidor.close()
            return None

    except Exception as e:
        print(f"[ALICE] ERROR durante reconciliación CASCADE: {e}")
        conn.close()
        time.sleep(1.0)
        servidor.close()
        return None

    conn.close()
    time.sleep(1.0)  # Permitir que el puerto se libere
    servidor.close()

    return clave_final, qber, len(clave_final), qber_revelados_bits


# (8) GUARDAR CLAVE FINAL DE ALICE y AMPLIFICACIÓN DE PRIVACIDAD (PA):
def pa_y_guardar_clave(clave_pre_pa_bits, iteration, id_configuracion):
    # Conexión TCP:
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.settimeout(config.SOCKET_TIMEOUT)
    servidor.bind((config.ALICE_IP, config.ALICE_PUERTO_SAVEKEY))
    servidor.listen(1)

    conn = None
    try:
        print("\n[ALICE] Esperando UID/key_id de Bob para guardar MI clave...")
        conn, _ = servidor.accept()
        msg = recibir_mensaje(conn)
        # Error
        if not msg or msg.get("tipo") != "save_key_id":
            print(f"[ALICE] SAVEKEY inválido recibido: {msg}")
            enviar_mensaje(conn, {"status": "error", "detalle": "mensaje save_key_id invalido"})
            return False

        # Recibimos mensaje de Bob:
        # (8.1) Guardamos uuid de Bob:
        key_id = msg.get("key_id")
        print(f"[ALICE] UID/key_id recibida de Bob: {key_id}")

        # (8.2) Empezamos PA:
        print("\n(5) AMPLIFICACIÓN DE PRIVACIDAD")
        final_key_bits = int(msg.get("final_key_bits", getattr(config, "FINAL_KEY_BITS", 256)))
        pre_pa_bits = int(msg.get("pre_pa_bits", getattr(config, "PRE_PA_KEY_BITS", len(clave_pre_pa_bits))))
        pa_method = msg.get("pa_method", getattr(config, "PA_METHOD", "TOEPLITZ"))
        pa_seed = msg.get("pa_seed")

        #OPC 1: HAY PA
        if getattr(config, "PRIVACY_AMPLIFICATION", False):
            # (1) Bob le envía pa_seed none así que Alice crea la SEMILLA:
            if not pa_seed:
                pa_seed = generar_toeplitz_seed(pre_pa_bits, final_key_bits)
                print(
                    f"[ALICE] Semilla pública Toeplitz generada por Alice: {len(pa_seed)} bits"
                )

            # (2) Aplicamos PA a la clave pre-PA:
            clave_final_bits = aplicar_pa(
                clave_pre_pa_bits,
                seed=pa_seed,
                final_key_bits=final_key_bits,
                method=pa_method,
                pre_pa_bits=pre_pa_bits,
            )
            print(
                f"[ALICE] Privacy Amplification {pa_method}: "
                f"{pre_pa_bits} bits pre-PA -> {len(clave_final_bits)} bits finales"
            )

            print(f"\n{'='*50}")
            print("[ALICE] Clave final tras PA:")
        # OPC 2: NO HAY PA
        else:
            clave_final_bits = clave_pre_pa_bits[:final_key_bits]
            print(f"[ALICE] Privacy Amplification desactivada: guardando {len(clave_final_bits)} bits")
            print("[ALICE] Clave final:")

        # CLAVE FINAL:
        print(clave_como_texto(clave_final_bits))
        print(f"{'='*50}\n")

        # (8.3) Guardamos clave de Alice con key_id/UID de Bob:
        ok = clave_final_alice_con_id(
            clave_final_bits,
            key_id,
            iteration=iteration,
            id_configuracion=id_configuracion,
        )

        # (8.4) Actualiza datos y mensaje a Bob:
        print(f"\n{'='*50}")
        if ok:
            try:
                rowcount_stats = actualizar_configuracion_postprocesado(
                    id_configuracion=id_configuracion,
                    pa_metodo=pa_method if getattr(config, "PRIVACY_AMPLIFICATION", False) else "NONE",
                    pa_input_bits=pre_pa_bits if getattr(config, "PRIVACY_AMPLIFICATION", False) else len(clave_final_bits),
                    pa_output_bits=len(clave_final_bits),
                    bits_finales_guardados=len(clave_final_bits),
                )
                print(f"[ALICE] Amplificación de privacidad/reconciliación guardadas: rondas afectadas={rowcount_stats}")
            except Exception as _e:
                print(f"[ALICE] Error guardando amplificación de privacidad/reconciliación: {_e}")
            
             # OPC 1: Alice guarda bien, mensaje a Bob CON INFORMACIÓN DE PA:
            print(f"[ALICE] Mi clave final ha sido guardada con la UID de Bob: {key_id}")
            respuesta_ok = {"status": "ok"}
            if getattr(config, "PRIVACY_AMPLIFICATION", False):
                respuesta_ok.update({
                    "pa_seed": pa_seed,
                    "pa_method": pa_method,
                    "final_key_bits": final_key_bits,
                    "pre_pa_bits": pre_pa_bits,
                })
            enviar_mensaje(conn, respuesta_ok)
            return True
        # OPC 2: Alice no guarda bien, mensaje a Bob de error:
        print(f"[ALICE] ERROR: no se pudo guardar mi clave con key_id={key_id}")
        enviar_mensaje(conn, {"status": "error", "detalle": "alice_no_pudo_guardar_clave"})
        return False

    except socket.timeout:
        print(f"[ALICE] ERROR: timeout esperando UID/key_id de Bob en {config.ALICE_PUERTO_SAVEKEY}")
        return False

    except Exception as e:
        print(f"[ALICE] ERROR en SAVEKEY Alice: {e}")
        try:
            if conn:
                enviar_mensaje(conn, {"status": "error", "detalle": str(e)})
        except Exception:
            pass
        return False

    finally:
        if conn is not None:
            conn.close()
        servidor.close()


### EJECUCIÓN DEL PROTOCOLO ###
def generar_una_clave(sesion_num=1):
    global CURRENT_ID_CONFIGURACION, CURRENT_CLAVE_ACUMULADA

    # Parámetros por sesión, INICIALIZANDO:
    bits_finales = int(getattr(config, "FINAL_KEY_BITS", 256)) 
    bits_objetivo = int(
        getattr(config, "PRE_PA_KEY_BITS", bits_finales)
        if getattr(config, "PRIVACY_AMPLIFICATION", False)
        else bits_finales
    )
    clave_acumulada = []
    CURRENT_CLAVE_ACUMULADA = clave_acumulada
    numero_ronda = 0
    id_configuracion_actual = None

    # Proceso que se repite hasta llegar a los bits totales, POR RONDA:
    while len(clave_acumulada) < bits_objetivo:
        numero_ronda += 1
        t_inicio_ronda_total = time.time()

        bits_actuales = len(clave_acumulada)
        bits_faltantes = bits_objetivo - bits_actuales

        print(f"\n{'='*50}")
        print(f"SESIÓN {sesion_num}/{config.NUM_CLAVES} - RONDA {numero_ronda}")
        print(f"Bits actuales: {bits_actuales}/{bits_objetivo}")
        print(f"Bits faltantes: {bits_faltantes}")
        print(f"{'='*50}")

        ### TRANSMISIÓN CUÁNTICA ###
        print(f"\n== TRANSMISIÓN CUÁNTICA ==")
        # (0) Alice genera bits y bases aleatorias, llama a dos funciones de BB84_UTILS:
        bits = generar_bits(config.NUM_QUBITS)
        bases = generar_bases(config.NUM_QUBITS)

        if getattr(config, "VERBOSE_ALICE", False):
            print(f"[ALICE] Bits generados:  {bits}")
            print(f"[ALICE] Bases generadas: {bases}")
        else:
            print(f"[ALICE] Bits/bases generados: {len(bits)} qubits")

       
        # (1) ENVIAR qubits al servidor cuántico:
        print(f"\nEnviando qubits al servidor...")
        respuesta_servidor = enviar_al_servidor(bits, bases)
        # BIEN: NetSquid recibe las bases y bits:
        if respuesta_servidor and respuesta_servidor.get('status') == 'ok':
            id_configuracion_actual = respuesta_servidor.get('id_configuracion', id_configuracion_actual)
            CURRENT_ID_CONFIGURACION = id_configuracion_actual
            print(f"[ALICE] Qubits enviados correctamente al servidor")

            try:
                qber_abort_threshold = float(config.QBER_ABORT_THRESHOLD)
                rowcount_umbral = actualizar_configuracion_qber_threshold(
                    id_configuracion=id_configuracion_actual,
                    qber_abort_threshold=qber_abort_threshold,
                )
                print(
                    f"[ALICE] Umbral QBER: "
                    f"{qber_abort_threshold}% (rondas afectadas={rowcount_umbral})"
                )
            except Exception as e:
                print(f"[ALICE] Error guardando QBER_ABORT_THRESHOLD en BD: {e}")

        # MAL: se recibe "esperando_alice" o "error"
        else:
            print(f"[ALICE] ERROR al enviar: {respuesta_servidor}")
            cerrar_pendientes_seguro(motivo="error_envio_servidor")
            return


        ### POST-PROCESAMIENTO CLÁSICO ###
        # (2,3) COMPARACIÓN DE BASES, SIFTING CON BOB
        print(f"\n== POST-PROCESAMIENTO CLÁSICO ==")
        result = escuchar_bob(bits, bases)
        if result is None:
            print("\n[ALICE] ERROR en canal clásico. Abortando.")
            cerrar_pendientes_seguro(motivo="error_canal_clasico")
            return
        clave_sifted, posiciones_sifting = result
        if len(clave_sifted) == 0:
            print("\n[ALICE] No hay bits despues del sifting. Nueva ronda...")
            continue

        print(f"[ALICE] Clave tras sifting: {clave_como_texto(clave_sifted)}")


        # (4) ESTIMACIÓN DE PARÁMETROS (QBER) y (5) CORRECCIÓN DE ERRORES y (6) CONFIRMACIÓN
        resultado_pe = parameter_estimation(
            bits, 
            posiciones_sifting, 
            clave_sifted, 
            numero_ronda, 
            len(clave_acumulada), 
            id_configuracion_actual,
            tiempo_inicio_ronda=t_inicio_ronda_total
        )
        if resultado_pe is None:
            print("\n[ALICE] Protocolo abortado por QBER alto. Nueva ronda...")
            continue
        clave_ronda, qber_ronda, bits_validos_ronda, qber_revelados_bits = resultado_pe
        tiempo_ronda_total = round(time.time() - t_inicio_ronda_total, 2)


        # (7) COMPROBAMOS TAMAÑO DE CLAVE Y ACUMULAMOS:
        aporte = clave_ronda[:bits_faltantes]
        clave_acumulada.extend(aporte)
        bits_acumulados_ahora = len(clave_acumulada)
        
        try:
            rowcount = actualizar_ronda_qber(
                id_configuracion=id_configuracion_actual,
                numero_ronda=numero_ronda,
                qber_verificacion=qber_ronda,
                bits_acumulados=bits_acumulados_ahora,
                bits_validos=bits_validos_ronda,
                ronda_abortada=0,
                qber_revelados_bits=qber_revelados_bits,
                tiempo_ronda_seg=tiempo_ronda_total,
            )
        except Exception as _e:
            print(f"[ALICE] Error al guardar QBER/bits en BD: {_e}")

        # Miramos bits usados para rellenar la clave:
        if len(aporte) == bits_validos_ronda:
            print(
                f"[ALICE] Aporta a clave pre-PA: {len(aporte)} bits | "
                f"acumulado: {bits_acumulados_ahora}/{bits_objetivo}"
            )
        # En caso de que el aporte sea menor que los bits válidos de la ronda, ESTAMOS TERMINANDO LA CLAVE:
        else:
            print(
                f"[ALICE] Post-reconciliación: {bits_validos_ronda} bits; "
                f"aporta a clave pre-PA: {len(aporte)} bits | "
                f"Acumulado: {bits_acumulados_ahora}/{bits_objetivo}"
            )
    # Se sigue ejecutando el while hasta que clave_acumulada = bits_objetivo

    print("\n" + "="*50)
    # PRIVACY_AMPLIFICATION = true
    if getattr(config, "PRIVACY_AMPLIFICATION", False):
        print(f"[ALICE] CLAVE RECONCILIADA PRE-PA ({len(clave_acumulada)} bits):")
        print(clave_como_texto(clave_acumulada))
    # PRIVACY_AMPLIFICATION = False 
    else:
        print(f"[ALICE] CLAVE FINAL SEGURA ({len(clave_acumulada)} bits):")
        print(clave_como_texto(clave_acumulada))
    
    print(f"Longitud de bits acumulados: {len(clave_acumulada)} bits")
    print(f"Rondas necesarias: {numero_ronda}")
    print("="*50)

    # MARCAS FINALES:
    # Cerramos RONDAS PEDNIENTES antes marcar como COMPLETADA:
    try:
        afectadas = cerrar_rondas_pendientes(id_configuracion_actual, len(clave_acumulada))
        print(f"[ALICE] Rondas pendientes cerradas como descartadas: {afectadas}")
    except Exception as e:
        print(f"[ALICE] Error cerrando rondas pendientes: {e}\n")
    
    # (8) GUARDAR CLAVE FINAL DE ALICE y AMPLIFICACIÓN DE PRIVACIDAD (PA):
    ok = pa_y_guardar_clave(clave_acumulada, numero_ronda, id_configuracion_actual)
    print(f"[ALICE] Guardado final confirmado: {ok}")
    if not ok:
        print("[ALICE] AVISO: la clave se completó, pero NO se guardó en QKD_keys de Alice.")

    print(f"{'='*50}")
    CURRENT_ID_CONFIGURACION = None
    CURRENT_CLAVE_ACUMULADA = []


### MAIN ###
def main():
    instalar_manejadores_senales() # Activa por si hay interrupciones

    print("="*50)
    print("KAIXO! Soy ALICE, la emisora del protocolo BB84")
    print(f"ALICE - EMISORA BB84 ({config.NUM_CLAVES} CLAVE(S) CONSECUTIVA(S))")
    print("="*50)

    for sesion_num in range(1, config.NUM_CLAVES + 1):
        # Ejecutamos el protocolo:
        generar_una_clave(sesion_num)
        if sesion_num < config.NUM_CLAVES:
            print(f"[ALICE] Esperando 5s para que el servidor cree la nueva sesión...")
            time.sleep(5)


if __name__ == '__main__':
    main()
