### BOB - RECEPTOR BB84 ###
import socket
import json
#import random
import time
#import math
import uuid
# Import de parámetros de Bob
import config_bob as config
# Parámetros y funciones de otros .py:
from bob_savekey import clave_final_bob_db
from bb84_utils import (
    generar_bases,
    seleccionar_muestra_qber,
    quitar_indices_test,
    cascade_reconcile_bob,
    sha256_bits,
    aplicar_pa,
    clave_como_texto,
)
from messages import (
    msg_medir_qubits,
    msg_bases_bob,
    msg_qber_request,
    msg_reconciliation_parity_request,
    msg_reconciliation_hash,
    msg_save_key_id,
    msg_clave_completa,
)

### MENSAJES TCP ###
def enviar_mensaje(conn, msg):
    data = json.dumps(msg).encode('utf-8')
    conn.sendall(len(data).to_bytes(4, byteorder='big'))
    conn.sendall(data)

def recibir_mensaje(conn):
    length = int.from_bytes(conn.recv(4), byteorder='big')
    data = b''
    while len(data) < length:
        data += conn.recv(length - len(data))
    if not data:
        return None
    try:
        return json.loads(data.decode('utf-8'))
    except json.JSONDecodeError:
        return None


### CANAL CUÁNTICO FUNCIONES ###
# (2) Enviar bases al servidor netsquid para medir qubits
def medir_en_servidor(bases):
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
                wait_time = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s, 4s, 8s, 16s, 32s
                print(f"[BOB] Conexión rechazada, reintentando en {wait_time}s... (intento {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                sock.close()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(config.SOCKET_TIMEOUT)
            else:
                raise

    # Enviamos MENSAJE al servidor netsquid:
    enviar_mensaje(sock, msg_medir_qubits(bases))
    respuesta = recibir_mensaje(sock)
    sock.close()

    if not respuesta:
        return None
    if respuesta.get('status') == 'esperando_alice':
        return respuesta

    if respuesta.get('status') != 'ok':
        print(f"[BOB] Respuesta inesperada del servidor: {respuesta}")
        return None

    resultados = respuesta.get('resultados')
    if not isinstance(resultados, list):
        print(f"[BOB] Respuesta malformada del servidor: {respuesta}")
        return None

    # Devuelve la respuesta completa para conservar id_configuracion y numero_ronda.
    return respuesta


### POST-PROCESAMIENTO CLÁSICO FUNCIONES ###
# (4) SIFTING: Enviar bases e IDs recibidos a Alice y recibir posiciones correctas
def enviar_bases_a_alice(bases, ids_recibidos):
    time.sleep(3)  # Dar más tiempo a que Alice abra servidor
    # Abre conexión TCP con Alice:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(config.SOCKET_TIMEOUT)
    sock.connect((config.ALICE_IP, config.ALICE_PUERTO_SIFTING))

    # MENSAJES: Información de envío de Bob
    verbose_sifting = getattr(config, "VERBOSE_BOB", False)
    if verbose_sifting:
        print(f"[BOB] Enviando mis bases a Alice por puerto SIFTING {config.ALICE_PUERTO_SIFTING}: {bases}")
        print(f"[BOB] Enviando IDs recibidos a Alice: {ids_recibidos}")
    else:
        print(f"[BOB] Enviando mis bases a Alice por puerto SIFTING {config.ALICE_PUERTO_SIFTING}: {len(bases)} bases")
    # Envía bases e id a Alice:
    enviar_mensaje(sock, msg_bases_bob(bases, ids_recibidos))

    # (4.1) Recibe posiciones correctas de Alice:
    if verbose_sifting:
        print(f"\n[BOB] Esperando respuesta de Alice con posiciones...")
    
    respuesta = recibir_mensaje(sock)
    if verbose_sifting:
        print(f"[BOB] Respuesta recibida: {respuesta}")
    if not respuesta or respuesta.get('status') != 'ok':
        print(f"[BOB] ERROR: Respuesta inválida de Alice")
        sock.close()
        return None

    posiciones_coincidentes = respuesta['posiciones_coincidentes']
    if verbose_sifting:
        print(f"[BOB] Posiciones coincidentes: {posiciones_coincidentes}")

    # BB84: en sifting solo se publican bases/posiciones; Bob no revela la clave sifted.
    sock.close()
    return posiciones_coincidentes


# (5) ESTIMACIÓN DE PARÁMETROS (QBER)
def estimacion_parametros(posiciones_validas, bits_por_id):
    print(f"\n(2) ESTIMACIÓN DE PARÁMETROS")
    if not posiciones_validas:
        print("[BOB] ERROR: No hay posiciones validas para estimar QBER")
        return None

    # Seleccionar muestra aleatoria de INDICES
    indices_test, posiciones_test = seleccionar_muestra_qber(
        posiciones_validas,
        config.QBER_SAMPLE_RATIO,
    )
    num_test = len(indices_test)
    bits_test = [bits_por_id[posiciones_validas[i]] for i in indices_test]

    print(f"[BOB] Revelando {num_test} bits aleatorios a Alice")
    if getattr(config, "VERBOSE_BOB", False):
        print(f"[BOB] Indices sifted: {indices_test}")
        print(f"[BOB] Posiciones originales: {posiciones_test}")
        print(f"[BOB] Bits revelados: {bits_test}")

    # Conectamos con Alice por TCP:
    time.sleep(2)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(config.SOCKET_TIMEOUT)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            sock.connect((config.ALICE_IP, config.ALICE_PUERTO_QBER))
            break
        except (ConnectionRefusedError, ConnectionResetError) as e:
            if attempt < max_retries - 1:
                wait_time = 0.5 * (attempt + 1)
                print(f"[BOB] QBER puerto {config.ALICE_PUERTO_QBER}: Alice aún no lista, reintentando en {wait_time}s... (intento {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                sock.close()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(config.SOCKET_TIMEOUT)
            else:
                raise
    # ENVIAMOS INDICES DE TEST, BITS DE TEST Y POSICIONES VALIDAS A ALICE:
    enviar_mensaje(sock, msg_qber_request(indices_test, bits_test))

    # (5.1) ESPERAMOS RESPUESTA del resultado QBER de Alice
    respuesta = recibir_mensaje(sock) 
    print("\n[BOB] Esperando resultado QBER de Alice...")
    # OPC1: abortada
    if respuesta.get('status') == 'abort':
        qber = respuesta.get('qber', 0) 
        print(f"[BOB] ALERTA! Alice aborta protocolo")
        print(f"[BOB] QBER demasiado alto: {qber:.2f}%")
        print(f"[BOB] Posible espionaje -> ABORTANDO")
        sock.close()
        return None
    # OPC 2: QBER aceptable, continuar con la ronda
    else:
        qber = respuesta.get('qber', 0) 
        print(f"[BOB] QBER medido: {qber:.2f}% -> Canal seguro")

    # Bob crea la clave sifted con las posiciones_validas que Alice ha aceptado:
    clave_sifted_bob = [bits_por_id[pos] for pos in posiciones_validas]
    # Quita los bits revelados en la muestra de test:
    clave_final = quitar_indices_test(clave_sifted_bob, indices_test)
    # Resultado FINAL tras el QBER:
    print(
        f"[BOB] QBER muestra descartada: {len(indices_test)} bits; "
        f"post-QBER para reconciliación: {len(clave_final)} bits"
    )


    # (6) CORRECCIÓN DE ERRORES (CASCADE): Bob define esta función hasta que reciba mensaje de paridad
    print(f"\n(3, 4) CORRECCIÓN DE ERRORES y CONFIRMACIÓN")
    def pedir_paridad_alice(indices):
        # SEGUNDA FUNCIÓN QUE SE EJECUTA, primero se define
        # Manda a Alice request:
        enviar_mensaje(sock, msg_reconciliation_parity_request(indices))
        # Recibe paridad de la clave de Alice para esos índices:
        respuesta_paridad = recibir_mensaje(sock)
        if not respuesta_paridad or "paridad" not in respuesta_paridad:
            raise RuntimeError(f"Respuesta de paridad inválida: {respuesta_paridad}")
        # Devuele la respuesta de Alice a la función de cascade_reconcile_bob:
        return int(respuesta_paridad["paridad"])

    # PRIMERA FUNCIÓN QUE SE EJECUTA
    clave_reconciliada, cascade_stats = cascade_reconcile_bob(
        clave_final,
        qber_pct=qber,
        # EJECUTA los envíos de mensaje a Alice de arriba:
        pedir_paridad_alice=pedir_paridad_alice, 
        rondas=getattr(config, "CASCADE_PASSES", 5),
        verbose=getattr(config, "VERBOSE_BOB", False),
    )


    # (7) CONFIRMACIÓN
    # Envía hasha a Alice:
    enviar_mensaje(
        sock,
        msg_reconciliation_hash(
            sha256_bits(clave_reconciliada),
            correcciones=cascade_stats.get("correcciones", 0),
            parity_checks=cascade_stats.get("parity_checks", 0),
            leakage_bits=cascade_stats.get("leakage_bits", 0),
        ),
    )
    # Recibe respuesta de confirmación de Alice:
    respuesta_hash = recibir_mensaje(sock)
    sock.close()
    if not respuesta_hash or respuesta_hash.get("status") != "ok":
        print(f"[BOB] Reconciliación fallida: {respuesta_hash}")
        return None
    print(
        f"[BOB] Reconciliación OK: "
        f"correcciones Bob={cascade_stats.get('correcciones', 0)}, "
        f"paridades públicas={cascade_stats.get('parity_checks', 0)}, "
        f"leakage={cascade_stats.get('leakage_bits', 0)} bits"
    )

    return clave_reconciliada


# (9.1) GUARDAR KEY y AMPLIFICACIÓN DE PRIVACIDAD:
def enviar_key_id_a_alice(key_id, pa_seed=None, pa_method=None, final_key_bits=None, pre_pa_bits=None):
    time.sleep(2)  

    # Conexión TCP:
    max_retries = 12
    last_error = None
    for attempt in range(max_retries):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(config.SOCKET_TIMEOUT)
        try:
            print(f"[BOB] Enviando UID/key_id a Alice: {key_id}")
            sock.connect((config.ALICE_IP, config.ALICE_PUERTO_SAVEKEY))
            # Envía el uuid a Alice:
            enviar_mensaje(
                sock,
                msg_save_key_id(
                    key_id,
                    pa_seed=pa_seed,
                    pa_method=pa_method,
                    final_key_bits=final_key_bits,
                    pre_pa_bits=pre_pa_bits,
                ),
            )
            # Recibimos mensaje de Alice:
            resp = recibir_mensaje(sock)

            if not resp:
                print("[BOB] SAVEKEY: Alice no devolvió respuesta válida")
                return None

            print(f"[BOB] Bits pre-PA recibidos de Alice: {resp.get('pre_pa_bits')} bits")
            # Devolvemos (a la función principal) mensaje recibido de Alice:
            return resp if resp.get("status") == "ok" else None
        # Error de conexión:
        except (ConnectionRefusedError, ConnectionResetError, socket.timeout) as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 0.5 * (attempt + 1)
                print(
                    f"[BOB] SAVEKEY: Alice aún no lista o no responde, "
                    f"reintentando en {wait_time}s... (intento {attempt+1}/{max_retries})"
                )
                time.sleep(wait_time)
            else:
                print(f"[BOB] ERROR enviando UID/key_id a Alice: {e}")
                return False

        finally:
            sock.close()

    print(f"[BOB] ERROR SAVEKEY: {last_error}")
    return False

# (11) NOTIFICAR AL SERVIDOR QUE LA CLAVE SE HA COMPLETADO
def notificar_servidor_clave_completa(numero_ronda, id_configuracion):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(config.SOCKET_TIMEOUT)
        sock.connect((config.SERVIDOR_IP, config.SERVIDOR_PUERTO))

        enviar_mensaje(sock, msg_clave_completa(numero_ronda, id_configuracion))
        recibir_mensaje(sock)

        sock.close()
        print("[BOB] Servidor notificado de fin de sesión tras guardar clave final")
        return True

    except Exception as e:
        print(f"[BOB] Aviso: no se pudo notificar al servidor ({e})")
        return False


### EJECUCIÓN DEL PROTOCOLO ###
def generar_una_clave(sesion_num=1):
    # Parámetros por sesión, INICIALIZANDO:
    bits_finales = int(getattr(config, "FINAL_KEY_BITS", 256)) 
    bits_objetivo = int(
        getattr(config, "PRE_PA_KEY_BITS", bits_finales)
        if getattr(config, "PRIVACY_AMPLIFICATION", False)
        else bits_finales
    )
    clave_acumulada = []
    iteration = 0
    id_configuracion_actual = None

    # Proceso que se repite hasta llegar a los bits totales, POR RONDA:
    while len(clave_acumulada) < bits_objetivo:
        iteration += 1
        bits_actuales = len(clave_acumulada)
        bits_faltantes = bits_objetivo - bits_actuales

        print(f"\n{'='*50}")
        print(f"SESIÓN {sesion_num}/{config.NUM_CLAVES} - RONDA {iteration}")
        print(f"Bits actuales: {bits_actuales}/{bits_objetivo}")
        print(f"Bits faltantes: {bits_faltantes}")
        print(f"{'='*50}")

        # Esperar a que Alice envie qubits al servidor:
        time.sleep(3) 


        ### TRANSMISIÓN CUÁNTICA ###
        print(f"\n== TRANSMISIÓN CUÁNTICA ==")
        # (1) Bob genera bases aleatorias, llama a BB84_UTILS:
        num_qubits = config.NUM_QUBITS
        bases = generar_bases(num_qubits)

        if getattr(config, "VERBOSE_BOB", False):
            print(f"[BOB] Bases generadas: {bases}")
        else:
            print(f"[BOB] Bases generadas: {len(bases)}")


        # (2) MIDE los qubits en el servidor con las bases generadas:
        print(f"\n[BOB] Midiendo qubits en el servidor...")
        respuesta_servidor = medir_en_servidor(bases)
        # Si recibe mensaje TIPO 2 de netsquid:
        if respuesta_servidor and respuesta_servidor.get('status') == 'esperando_alice':
            print("[BOB] Servidor aún espera a Alice. Reintentando esta misma ronda...")
            iteration -= 1
            time.sleep(2)
            continue
        if not respuesta_servidor:
            print("[BOB] ERROR al medir. Nueva ronda...")
            continue


        # (3) RECIBIMOS RESULTADOS (bits medidos con sus bases)
        id_configuracion_actual = respuesta_servidor.get('id_configuracion', id_configuracion_actual)
        # Extraemos los resultados: qubit_id, bit_medido, bases_coinciden
        resultados = respuesta_servidor.get('resultados', [])
        print(f"[BOB] Resultados recibidos del servidor")

        # Extraemos qubits:
        bits_por_id = {
            r['qubit_id']: r['bit_medido']
            for r in resultados
            if r.get('bit_medido') in (0, 1)
        }
        # Lista de qubits medidos en ORDEN:
        ids_medidos = sorted(bits_por_id.keys())
        bits_medidos = [bits_por_id[i] for i in ids_medidos]
        
        # Miramos los qubits perdidos (id que no llegaron):
        ids_perdidos = [i for i in range(num_qubits) if i not in bits_por_id]
        if getattr(config, "VERBOSE_BOB", False):
            print(f"\n[BOB] IDs medidos ({len(ids_medidos)}): {ids_medidos}")
            print(f"[BOB] IDs perdidos ({len(ids_perdidos)}): {ids_perdidos}")
            print(f"[BOB] Bits medidos: {bits_medidos}")
        else:
            print(f"[BOB] IDs medidos: {len(ids_medidos)}")
            print(f"[BOB] IDs perdidos: {len(ids_perdidos)}")
        

        ### POST-PROCESAMIENTO CLÁSICO ###
        # (4) SIFTING CON ALICE
        print(f"\n== POST-PROCESAMIENTO CLÁSICO ==")
        print(f"(1) SIFITNG")
        posiciones_ok = enviar_bases_a_alice(bases, ids_medidos)
        if not posiciones_ok:
            print("[BOB] ERROR en sifting con Alice. Nueva ronda...")
            continue
        # MENSAJE:
        if getattr(config, "VERBOSE_BOB", False):
            print(f"\n[BOB] Alice me ha dicho las posiciones correctas: {posiciones_ok}")

        # (4.1) Construir clave tras sifting descartando posiciones perdidas
        posiciones_ok_medidas = [i for i in posiciones_ok if i in bits_por_id]
        posiciones_ok_perdidas = [i for i in posiciones_ok if i not in bits_por_id]
        if posiciones_ok_perdidas and getattr(config, "VERBOSE_BOB", False):
            print(f"[BOB] Posiciones coincidentes pero perdidas en canal (descartadas): {posiciones_ok_perdidas}")

        # Construye la clave solo con las posiciones correctas:
        clave_sifted = [bits_por_id[i] for i in posiciones_ok_medidas]

        if getattr(config, "VERBOSE_BOB", False):
            print(f"[BOB] Sifting completado: {len(clave_sifted)}/{num_qubits} bits validos")
        if len(clave_sifted) == 0:
            print("[BOB] No hay bits despues del sifting. Nueva ronda...")
            continue

        print(f"[BOB] Clave tras sifting: {clave_como_texto(clave_sifted)}")


        # (5) ESTIMACIÓN DE PARÁMETROS (QBER) y (6) RECONCILIACIÓN DE ERRORES y (7) CONFIRMACIÓN
        clave_ronda = estimacion_parametros(posiciones_ok_medidas, bits_por_id)
        if clave_ronda is None:
            print("\n[BOB] Protocolo abortado por QBER alto. Nueva ronda...")
            continue


        # (8) COMPROBAMOS TAMAÑO DE CLAVE Y ACUMULAMOS:
        aporte = clave_ronda[:bits_faltantes]
        clave_acumulada.extend(aporte)
        # Miramos bits usados para rellenar la clave:
        if len(aporte) == len(clave_ronda):
            print(
                f"[BOB] Aporta a clave pre-PA: {len(aporte)} bits | "
                f"acumulado: {len(clave_acumulada)}/{bits_objetivo}"
            )
        # En caso de que el aporte sea menor que los bits válidos de la ronda, ESTAMOS TERMINANDO LA CLAVE:
        else:
            print(
                f"[BOB] Post-reconciliación: {len(clave_ronda)} bits; "
                f"aporta a clave pre-PA: {len(aporte)} bits | "
                f"acumulado: {len(clave_acumulada)}/{bits_objetivo}"
            )
    # Se sigue ejecutando el while hasta que clave_acumulada = bits_objetivo


    # (9) GUARDAR UUID y AMPLIFICACIÓN DE PRIVACIDAD:
    print("\n" + "="*50)
    # Información para PA:
    pa_seed = None
    pa_method = getattr(config, "PA_METHOD", "TOEPLITZ")
    pre_pa_bits = len(clave_acumulada)

    print(f"[BOB] CLAVE RECONCILIADA PRE-PA: {pre_pa_bits} bits")

    # (9.1) GUARDAR KEY
    key_id = str(uuid.uuid4())
    resp_alice = enviar_key_id_a_alice(
        key_id,
        pa_seed=None,
        pa_method=pa_method,
        final_key_bits=bits_finales,
        pre_pa_bits=pre_pa_bits,
    )
    if not resp_alice:
        print("[BOB] ERROR: Alice no confirmó SAVEKEY; no se guarda la clave de Bob")
        return

    # (9.2) AMPLIFICACIÓN DE PRIVACIDAD (PA) si Alice lo confirma en su respuesta al SAVEKEY:
    # OPC 1: PA activado
    if getattr(config, "PRIVACY_AMPLIFICATION", False):
        pa_seed = resp_alice.get("pa_seed")
        if not pa_seed:
            print("[BOB] ERROR: Alice confirmó SAVEKEY pero no devolvió pa_seed")
            return

        pa_method = resp_alice.get("pa_method", pa_method)
        bits_finales = int(resp_alice.get("final_key_bits", bits_finales))
        pre_pa_bits = int(resp_alice.get("pre_pa_bits", pre_pa_bits))

        clave_final = aplicar_pa(
            clave_acumulada,
            seed=pa_seed,
            final_key_bits=bits_finales,
            method=pa_method,
            pre_pa_bits=pre_pa_bits,
        )
        print(
            f"[BOB] Amplificación de privacidad {pa_method}: "
            f"{pre_pa_bits} bits -> {len(clave_final)} bits finales "
            f"(semilla generada por Alice: {len(pa_seed)} bits)"
        )
    # OPC 2: PA desactivado
    else:
        clave_final = clave_acumulada[:bits_finales]
        print("[BOB] Amplificación de privacidad  desactivada")

    print(f"\n{'='*50}")
    print(f"[BOB] CLAVE FINAL SEGURA ({len(clave_final)} bits):")
    print(clave_como_texto(clave_final))
    print(f"Rondas necesarias: {iteration}")
    print(f"{'='*50}\n")


    # (10) GUARDAR CLAVE EN BASE DE DATOS DE BOB:
    key_id_guardado = clave_final_bob_db(
        clave_final,
        iteration,
        id_configuracion=id_configuracion_actual,
        key_id=key_id,
    )
    if not key_id_guardado:
        print("[BOB] ERROR: no se pudo guardar la clave en BD")
        return
    print(f"\n{'='*50}")
    print(f"[BOB] Guardada clave final en base de datos Bob con id={key_id_guardado}")
    print("[BOB] Alice confirma que lo ha guardado: True")
    print(f"{'='*50}\n")

    # (11) NOTIFICAR AL SERVIDOR QUE LA CLAVE SE HA COMPLETADO
    notificar_servidor_clave_completa(
        numero_ronda=iteration,
        id_configuracion=id_configuracion_actual
    )



### MAIN ###
def main():
    print("="*50)
    print("KAIXO! Soy Bob, el receptor del protocolo BB84")
    print(f"BOB - RECEPTOR BB84 ({config.NUM_CLAVES} CLAVE(S) CONSECUTIVA(S))")
    print("="*50)
    for sesion_num in range(1, config.NUM_CLAVES + 1):
        # Ejecutamos el protocolo:
        generar_una_clave(sesion_num)
        if sesion_num < config.NUM_CLAVES:
            print(f"[BOB] Esperando 8s para sincronizar con el servidor...")
            time.sleep(8)


if __name__ == '__main__':
    main()
