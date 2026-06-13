### NETSQUID - BB84 ###
import socket
import json
import time
import random
from collections import namedtuple

### NETSQUID ###
import netsquid as ns
# Nodes
from netsquid.nodes import Network, Node
# Protocols
from netsquid.protocols.nodeprotocols import DataNodeProtocol
from netsquid.protocols.serviceprotocol import ServiceProtocol
from netsquid.protocols.protocol import Signals
# Componentes
from netsquid.components import Message
from netsquid.components.qchannel import QuantumChannel
from netsquid.components.qmemory import QuantumMemory
from netsquid.components.models.delaymodels import FibreDelayModel
from netsquid.components.models.qerrormodels import FibreLossModel, DepolarNoiseModel, DephaseNoiseModel, T1T2NoiseModel
# Qubits
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits import operators as ops
# Estadísticas
from netsquid.util.simstats import SimStats
from simstats_utils import ejecutar_simulacion_con_simstats

import config_netsquid as config
import config_errores as err
import config_bob
from eve import EavesdropperProtocol
from db_utils import (
    get_db_connection,
    crear_configuracion,
    crear_ronda_pendiente,
    guardar_metricas_cuanticas_ronda,
    guardar_simstats_en_bd,
    marcar_configuracion_completada,
    marcar_configuracion_abortada,
)

### PARÁMETROS PROCESO ###
# Tiempo de espera:
ALICE_WAIT_TIMEOUT_S = getattr(config, "ALICE_WAIT_TIMEOUT_S", 30)
BOB_WAIT_TIMEOUT_S = getattr(config, "BOB_WAIT_TIMEOUT_S", 30)

TARGET_KEY_BITS = config.PRE_PA_KEY_BITS
NUM_QUBITS = config.NUM_QUBITS
NUM_CLAVES = config.NUM_CLAVES



### SERVICIOS (request, response) ###
ReqEnviarQubits = namedtuple("ReqEnviarQubits", ["bits", "bases"])
ResFinalizado = namedtuple("ResFinalizado", ["mensaje"])


### RED ###
NETWORK = Network("bb84_network")
NODE_ALICE = Node("AliceSim", ID=1)
NODE_BOB = Node("BobSim", ID=2)

NETWORK.add_node(NODE_ALICE)
NETWORK.add_node(NODE_BOB)

# MEMORIA CUÁNTICA
alice_memory = QuantumMemory(
    name="alice_memory",
    num_positions=NUM_QUBITS,
    memory_noise_models=T1T2NoiseModel(T1=err.T1_ns, T2=err.T2_ns) if err.usart1t2_noise else None
)
NODE_ALICE.add_subcomponent(alice_memory)

bob_memory = QuantumMemory(
    name="bob_memory",
    num_positions=NUM_QUBITS,
    memory_noise_models=T1T2NoiseModel(T1=err.T1_ns, T2=err.T2_ns) if err.usart1t2_noise else None
)
NODE_BOB.add_subcomponent(bob_memory)


# CANAL CUÁNTICO
# ruido: depolarizacion + dephasing + T1T2 (todos simultaneos)
noise_model = None
if err.usart1t2_noise:
    noise_model = T1T2NoiseModel(T1=err.T1_ns, T2=err.T2_ns)
if err.usar_depolarizacion:
    depolar = DepolarNoiseModel(depolar_rate=err.despolarizacion, time_independent=True)
    noise_model = depolar if noise_model is None else noise_model + depolar
if err.usar_dephase:
    dephase = DephaseNoiseModel(dephase_rate=err.dephase, time_independent=True)
    noise_model = dephase if noise_model is None else noise_model + dephase
if noise_model is None:
    noise_model = DepolarNoiseModel(depolar_rate=0.00001, time_independent=True)


# todos los errores se aplican mas adelante con sim_run
qchannel_A2B = QuantumChannel(
    name="qchannel_A2B",
    length=err.distancia,
    models={
        "delay_model": FibreDelayModel(c=err.velocidad_fibra),
        "quantum_loss_model": FibreLossModel(
            p_loss_init=err.prob_loss_in,
            p_loss_length=err.atenuacion,
        ),
        "quantum_noise_model": noise_model, #depolarizacion o dephasing
    },
)

PORT_A, PORT_B = NETWORK.add_connection(
    NODE_ALICE, NODE_BOB,
    channel_to=qchannel_A2B,
    label="quantum",
)
# NODE_ALICE.ports[PORT_A] -> puerto de salida hacia BobSim
# NODE_BOB.ports[PORT_B] -> puerto de entrada desde AliceSim


### COMUNICACIÓN TCP ###
def recibir_mensaje(conn):
    length_bytes = conn.recv(4)
    if not length_bytes:
        return None
    length = int.from_bytes(length_bytes, byteorder='big')
    
    data = b''
    while len(data) < length:
        chunk = conn.recv(length - len(data))
        if not chunk:
            return None
        data += chunk
    
    return json.loads(data.decode('utf-8'))

def enviar_mensaje(conn, mensaje):
    data = json.dumps(mensaje).encode('utf-8')
    conn.sendall(len(data).to_bytes(4, byteorder='big'))
    conn.sendall(data)


### ALICE ###
class AliceService(ServiceProtocol):
    def __init__(self, node, port_name, eve_proc, memory):
        super().__init__(node=node, name="AliceService")
        # Puerto de salida:
        self.port = self.node.ports[port_name]
        # Guarda protocolo Eve, funciones de EVE.PY:
        self.eve_proc = eve_proc
        # Guarda memoria cuántica de Alice:
        self.memory = memory

        # PRIMERA función: Cuando el servidor le dice enviar qubits:
        self.register_request(ReqEnviarQubits, self.handle_mandar_qubits)
        # Cuando termina de enviar qubits:
        self.register_response(ResFinalizado)

    def handle_mandar_qubits(self, req):
        # Los parámetros bits y bases son los recibidos por Alice:
        for i, (bit, base) in enumerate(zip(req.bits, req.bases)):
            # Creamos un qubit:
            qubit = self.crear_qubit(bit, base)
            
            # Guardar en memoria de Alice:
            self.memory.put(qubit, positions=i)
            # Retirar de memoria para enviar:
            qubit_to_send = self.memory.pop(positions=i)[0]

            ## EVE.py: comprobamos que existe y que esta interceptando ##
            if self.eve_proc is not None and self.eve_proc.percentage_intercepted > 0:
                # Intercepta y cambia los qubits a enviar, función del EVE.PY:
                qubit_to_send = self.eve_proc.medir_recodificar_qubit(i, qubit_to_send, base)

            # (contenido, indice de qubit de ronda)
            msg = Message(items=[qubit_to_send], header=i)
            # Envía el mensaje por el puerto de salida:
            self.port.tx_output(msg) # tx_output: envia mensaje

        self.send_response(ResFinalizado("Envio completado"))

    def crear_qubit(self, bit, base):
        # Por defecto se crea en |0>:
        qubit = qapi.create_qubits(1)[0]
        if base == "Z" and bit == 1: 
            qapi.operate(qubit, ops.X) # |0> -> |1>
        elif base == "X":
            qapi.operate(qubit, ops.H) # |0> -> |+>, |1> -> |->
            if bit == 1:
                qapi.operate(qubit, ops.Z) # |+> -> |->
        return qubit


### BOB ###
class BobReceiver(DataNodeProtocol):
    def __init__(self, node, port_name, bases_bob, bases_alice, total, memory):
        super().__init__(node=node, port_name=port_name, name="BobReceiver")
        # PARÁMETROS DE INICIALIZACIÓN:
        # Bases que elige Bob para medir:
        self.bases_bob = bases_bob 
        # Bases originales de Alice para comparar en el sifting:
        self.bases_alice = bases_alice
        # Cuántos bits espera recibir:
        self.total = total
        # Memoria:
        self.memory = memory
        # Lista de lo que mide:
        self.resultados = []

        # CONTADORES para detector:
        self.qubits_llegados_canal = 0
        self.qubits_detectados = 0
        self.qubits_no_detectados = 0
        # CONTADORES errores físicos:
        self.errores_measure_faulty = 0
        self.errores_misalignment = 0
        self.dark_counts_generados = 0
        self.qubits_perdidos_jitter = 0

    # Se ejecuta después del protocolo Alice: Después de envíar los qubits a Bob (interceptados o no)
    # PROCESS_DATA: coge mensaje, analiza y ejecutamos algo
    def process_data(self, message):
        # Verificar que el mensaje tiene un qubit y un ID válido:
        qid = self.check_qid(message)
        if qid is None:
            return
        if qid < 0 or qid >= len(self.bases_bob):
            return

        # Comprobar que el mensaje tiene un QUBIT:
        qubit = message.items[0] if message.items else None
        if qubit is None:
            return
        # qubit ha llegado CORRECTAMENTE:
        self.qubits_llegados_canal += 1

        ## ERRRORES AL RECIBIR DE BOB:
        # JITTER: bit pérdido
        if getattr(err, "usar_jitter_basico", False):
            jitter_prob = float(getattr(err, "jitter_prob_perdida", 0.0))
             # Genera número aleatorio entre 0 y 1, si es menor que la prob el qubit se descarta:
            jitter_prob = max(0.0, min(1.0, jitter_prob))
            if random.random() < jitter_prob:
                self.qubits_perdidos_jitter += 1
                return

         # EFICIENCIA DEL DETECTOR: no detecta
        if getattr(err, "usar_detector_efficiency", False):
            efficiency = float(getattr(err, "detector_efficiency", 1.0))
             # Genera número aleatorio entre 0 y 1, si es mayor que la prob el qubit no se detecta:
            efficiency = max(0.0, min(1.0, efficiency))
            if random.random() > efficiency:
                self.qubits_no_detectados += 1
                return


        self.qubits_detectados += 1

        # Guardar en memoria de Bob
        self.memory.put(qubit, positions=qid)
        # Retirar de memoria para medir
        qubit_to_measure = self.memory.pop(positions=qid)[0]
        
        ## MEDIR QUBIT según BASE BOB:
        base_bob = self.bases_bob[qid]
        if base_bob == "X":
            qapi.operate(qubit_to_measure, ops.H)
        bit_medido = int(qapi.measure(qubit_to_measure, observable=ops.Z)[0])
        
        
        ## ERRRORES AL MEDIR DE BOB:
        # ERROR AL MEDIR: mide el contrario
        if getattr(err, "usar_measure_faulty", False):
            p_error = (
                float(getattr(err, "prob_error_medicion_1", 0.0))
                if bit_medido == 1
                else float(getattr(err, "prob_error_medicion_0", 0.0))
            )
            # Garantiza que p_error esté entre 0 y 1:
            p_error = max(0.0, min(1.0, p_error))
            if random.random() < p_error:
                bit_medido = 1 - bit_medido
                self.errores_measure_faulty += 1
        # ERROR ALINEACIÓN: desalineación como probabilidad de flip
        if getattr(err, "usar_misalignment", False):
            p_misalignment = float(getattr(err, "misalignment_prob", 0.0))
            p_misalignment = max(0.0, min(1.0, p_misalignment))
            if random.random() < p_misalignment:
                bit_medido = 1 - bit_medido
                self.errores_misalignment += 1


        bases_coinciden = (self.bases_alice[qid] == base_bob)

        self.resultados.append({
            "qubit_id": qid,
            "bit_medido": bit_medido,
            "bases_coinciden": bases_coinciden,
        })

        # Comprueba que Bob ha medido todos los qubits:
        if len(self.resultados) >= self.total:
            self.send_signal(Signals.FINISHED) # PROTOCOLO COMPLETADO


    # COMPRUEBA el ID del mensaje recibido de Alice por tx_output:
    def check_qid(self, message):
        # Reconoce el header = i mandado:
        if hasattr(message, "header"):
            try:
                return message.header
            except Exception:
                pass
        # Otra forma de comprobar:
        try:
            return message.meta.get("header")
        except Exception:
            return None

    ### FUNCIONES NETSQUID en BOB ###
    # Función que se ejecuta fuera de los protocolos:
    def aplicar_dark_counts_reales(self):
        if not getattr(err, "usar_dark_counts_reales", False):
            return

        p_dark = float(getattr(err, "prob_dark_count_real", 0.0))
        p_dark = max(0.0, min(1.0, p_dark))
        if p_dark <= 0:
            return

        qids_con_resultado = {res["qubit_id"] for res in self.resultados}

        for qid in range(self.total):
            if qid in qids_con_resultado:
                continue

            if random.random() < p_dark:
                base_bob = self.bases_bob[qid]
                bit_falso = random.randint(0, 1)
                bases_coinciden = (self.bases_alice[qid] == base_bob)

                self.resultados.append({
                    "qubit_id": qid,
                    "bit_medido": bit_falso,
                    "bases_coinciden": bases_coinciden,
                    "origen": "dark_count_real",
                })
                self.dark_counts_generados += 1

        # Mantener orden por posición para facilitar depuración.
        self.resultados.sort(key=lambda r: r["qubit_id"])

    ### POST_PROCESS_DATA: Necesario por NetSquid, no hace nada ###
    def post_process_data(self, message):
        pass


### FUNCIONES DE ESTADÍSTICAS ###
# Estadísticas por ronda:
def ronda_stats(ronda_num, alice_prot, bob_prot, eve_protocol, bits_alice, bases_alice, bases_bob):
    # RESULTADO QBER DEL CANAL:
    qber_canal, bits_sifted = calcular_qber_canal_cuantico(bob_prot.resultados, bits_alice, bases_alice, bases_bob)
    # REPORT DE EVE
    eve_stats = eve_protocol.get_statistics() if eve_protocol else {}

    qubits_enviados = len(bases_alice)
    # Con detector efficiency distinguimos:
    #   qubits_recibidos  -> llegaron a Bob después del canal.
    #   qubits_detectados -> pasaron la eficiencia del detector y se midieron.
    #   qubits_no_detectados -> llegaron a Bob, pero el detector no los detectó.
    qubits_recibidos = getattr(bob_prot, "qubits_llegados_canal", len(bob_prot.resultados))
    qubits_detectados = getattr(bob_prot, "qubits_detectados", len(bob_prot.resultados))
    qubits_no_detectados = getattr(bob_prot, "qubits_no_detectados", 0)

    eve_interceptados_count = eve_stats.get('total_intercepted', 0)
    
    # Porcentaje sobre qubits_enviados (no recibidos) para que coincida con eve_percentage_intercepted
    if qubits_enviados > 0:
        eve_interceptados_porcentaje = (eve_interceptados_count / qubits_enviados) * 100
    else:
        eve_interceptados_porcentaje = 0.0
    
    return {
        'ronda': ronda_num,
        'qubits_enviados': qubits_enviados,
        # qubits_recibidos son los que llegan tras el canal.
        # qubits_detectados son los que realmente Bob puede medir.
        'qubits_recibidos': qubits_recibidos,
        'qubits_perdidos': qubits_enviados - qubits_recibidos,
        'qubits_detectados': qubits_detectados,
        'qubits_no_detectados': qubits_no_detectados,
        'errores_measure_faulty': getattr(bob_prot, "errores_measure_faulty", 0),
        'errores_misalignment': getattr(bob_prot, "errores_misalignment", 0),
        'dark_counts_generados': getattr(bob_prot, "dark_counts_generados", 0),
        'qubits_perdidos_jitter': getattr(bob_prot, "qubits_perdidos_jitter", 0),
        'bits_sifted': bits_sifted,
        'qber_canal_cuantico': qber_canal,
        'eve_interceptados': eve_interceptados_porcentaje,
    }

# Cálcula el qber del cnal cuántico:
def calcular_qber_canal_cuantico(resultados, bits_alice, bases_alice, bases_bob):
    if not resultados:
        return 0.0, 0
    errores = 0
    coincidencias = 0
    for res in resultados:
        qid = res["qubit_id"]
        if bases_alice[qid] == bases_bob[qid]:
            coincidencias += 1
            # Comparar bit enviado vs bit medido
            if bits_alice[qid] != res["bit_medido"]:
                errores += 1
    qber = (errores / coincidencias * 100) if coincidencias > 0 else 0.0
    return qber, coincidencias



### BASE DE DATOS ###
# CONEXIÓN A DB:
def conectar_bd():
    try:
        return get_db_connection()
    except Exception as e:
        print(f"[BD] Error de conexión: {e}")
        return None

# CREA BB84_configuracion:
def crear_configuracion_en_bd(conn):
    # Comprueba conexión válida:
    if not conn:
        return None
    try:
        # Creamos una fila de configuración en BB84_configuracion:
        id_configuracion = crear_configuracion(
            err_config=err,
            qber_sample_ratio=config_bob.QBER_SAMPLE_RATIO,
            bits_objetivo=TARGET_KEY_BITS,
            conn=conn,
        )

        # Devuelve la fila en la que se va a escribir:
        print(f"[BD] Configuración #{id_configuracion} registrada en BB84_configuracion")
        return id_configuracion
    except Exception as e:
        print(f"[BD] Error al crear configuración: {e}")
        return None


# CREA LINEA PROVISIONAL en BB84_rondas:
def crear_ronda_pendiente_en_bd(conn, id_configuracion, numero_ronda, qubits_enviados):
    if not conn or id_configuracion is None:
        return False
    try:
        # llamamos al db_utils:
        rowcount = crear_ronda_pendiente(
            id_configuracion=id_configuracion,
            numero_ronda=numero_ronda,
            qubits_enviados=qubits_enviados,
            conn=conn,
        )
        print(f"[BD] Ronda provisional creada: config={id_configuracion}, ronda={numero_ronda}, rondas afectadas={rowcount}")
        return True
    except Exception as e:
        print(f"[BD] Error creando ronda provisional: {e}")
        return False


# GUARDAMOS información de la ronda en BB84_rondas:
def guardar_ronda_en_bd(conn, id_configuracion, numero_ronda, ronda_data):
    if not conn or id_configuracion is None:
        return
    try:
        rowcount = guardar_metricas_cuanticas_ronda(
            id_configuracion=id_configuracion,
            numero_ronda=numero_ronda,
            ronda_data=ronda_data,
            conn=conn,
        )
        print(
            f"[BD] Config #{id_configuracion} - Ronda {numero_ronda} actualizada en BB84_rondas: "
            f"QBER_canal={round(ronda_data['qber_canal_cuantico'], 2)}%, "
            f"Eve={round(ronda_data['eve_interceptados'], 2)}%, rondas afectadas={rowcount}"
        )
    except Exception as e:
        print(f"[BD] Error al guardar ronda: {e}")



### SERVIDOR NETSQUID ###
def iniciar_servidor(servidor_socket, db_conn, sesion_num):
    ### Ejecuta UNA SESIÓN completa (hasta TARGET_KEY_BITS sifted) ###
    print(f"\n{'='*50}")
    print(f"SESIÓN {sesion_num}/{NUM_CLAVES} - Iniciando generación de clave")
    print(f"Escuchando en {config.SERVIDOR_IP}:{config.SERVIDOR_PUERTO}")
    print(f"{'='*50}")

    # Recogemos el tiempo de inicio:
    tiempo_inicio_generacion = time.time()

    # Creamos una fila de configuración en BB84_configuracion, devuelve fila:
    id_configuracion = crear_configuracion_en_bd(db_conn)
    # Si devuelve None, ERROR:
    if id_configuracion is None:
        raise RuntimeError(
            "No se pudo crear BB84_configuracion. "
        )

    print(f"[SERVIDOR] Configuración #{id_configuracion}")
    print(f"{'='*50}")

    numero_ronda = 0
    try:
        while True: # Bucle infinito
            numero_ronda += 1
            ns.sim_reset() # resetea simulador netsquid en cada ronda

            print(f"\n{'='*50}")
            print(f"SESIÓN/CLAVE {sesion_num}/{NUM_CLAVES} - RONDA {numero_ronda}")
            print(f"{'='*50}")



            ################
            # (1) RECIBIR DE ALICE
            print("[SERVIDOR] Esperando Alice...")
            servidor_socket.settimeout(ALICE_WAIT_TIMEOUT_S)
            conn_a = None
            # Inicia conexión con Alice:
            try:
                conn_a, addr = servidor_socket.accept()
            # opción 1: ERROR Alice no se conecta en el tiempo límite:
            except socket.timeout:
                print(f"[SERVIDOR] Sin nueva conexion de Alice en {ALICE_WAIT_TIMEOUT_S}s.")

                # Cálcula cuánto tiempo ha pasado:
                tiempo_total_servidor = time.time() - tiempo_inicio_generacion
                # Cuántas rondas se han rellenado:
                rondas_reales = max(numero_ronda - 1, 0)

                # Marcamos en la base de datos como ABORTADA:
                try:
                    rowcount = marcar_configuracion_abortada(
                        id_configuracion=id_configuracion,
                        tiempo_total_sesion=tiempo_total_servidor,
                        total_rondas=rondas_reales,
                        conn=db_conn,
                    )
                    # Actualiza cuando es abortada:
                    print(
                        f"[SERVIDOR] BB84_configuracion #{id_configuracion} marcada como abortada "
                        f"por inactividad de Alice ({round(tiempo_total_servidor, 2)}s, "
                        f"{rondas_reales} rondas, rondas afectadas={rowcount})"
                    )
                except Exception as e:
                    print(f"[SERVIDOR] Error al marcar configuración abortada por inactividad: {e}")

                # En mitad de una sesión:
                if numero_ronda == 1:
                    print("[SERVIDOR] Alice no ha iniciado esta sesión. No se crearán más sesiones vacías.")
                    return "sin_alice"
                print("[SERVIDOR] Alice desapareció durante una sesión ya iniciada. Cerrando sesión como abortada.")
                return "timeout_alice"

            # opción 2: ERROR de conexión con Alice:
            except Exception as conn_error:
                print(f"[SERVIDOR] Error aceptando conexión de Alice: {conn_error}")
                raise
            
            #opción 3: conexión con Alice bien:
            msg_a = recibir_mensaje(conn_a)
            
            ## COMPROBAMOS SEGÚN EL TIPO DE MENSAJE RECIBIDO ## 
            # TIPO 1: clave_completa
            # Manejar mensaje de clave completa
            if msg_a and msg_a.get('tipo') == 'clave_completa':
                tiempo_total_servidor = time.time() - tiempo_inicio_generacion
                numero_rondas_final = int(msg_a.get("numero_ronda", numero_ronda - 1))

                print(f"\n[SERVIDOR] Cliente reporta clave completa en ronda {numero_rondas_final}")
                print(f"[SERVIDOR] Tiempo total de sesión: {tiempo_total_servidor:.2f}s")
                # Actualizar BB84_configuracion con tiempo total, rondas y estado
                try:
                    rowcount = marcar_configuracion_completada(
                        id_configuracion=id_configuracion,
                        tiempo_total_sesion=tiempo_total_servidor,
                        total_rondas=numero_rondas_final,
                        conn=db_conn,
                    )
                    print(f"[SERVIDOR] BB84_configuracion #{id_configuracion} marcada como completada ({round(tiempo_total_servidor,2)}s, {numero_ronda-1} rondas, rondas afectadas={rowcount})")
                except Exception as e:
                    print(f"[SERVIDOR] Error al actualizar configuración: {e}")

                print(f"[SERVIDOR] Cerrando servidor (Configuración #{id_configuracion} completada)")
                enviar_mensaje(conn_a, {'status': 'ok', 'tipo': 'sesion_completada'})
                conn_a.close()
                return "completada"
            
            # TIPO 2: NO es enviar_qubits o viene vacío
            if not msg_a or msg_a.get('tipo') != 'enviar_qubits':
                tipo_recibido = msg_a.get('tipo') if isinstance(msg_a, dict) else None

                # BOB puede adelantarse a ALICE
                # No se debe consumir numero_ronda ni crear ronda en BD
                if tipo_recibido == 'medir_qubits':
                    print("[SERVIDOR] Bob se ha adelantado: aún no hay qubits nuevos de Alice.")
                    enviar_mensaje(conn_a, {
                        'status': 'esperando_alice',
                        'detalle': 'Servidor esperando enviar_qubits de Alice antes de medir'
                    })
                    conn_a.close()
                    numero_ronda -= 1
                    time.sleep(0.5)
                    continue
                print(f"[SERVIDOR] ERROR: msg_a inválido: {msg_a}")
                enviar_mensaje(conn_a, {'status': 'error'})
                conn_a.close()
                numero_ronda -= 1
                continue

            # TIPO 3: enviar_qubits
            ## PRIMER MENSAJE (de ALICE): tipo enviar_qubits ## 
            bits = msg_a["bits"]
            bases_alice = msg_a["bases"]
            # Comparamos que coincidan en tamaño:
            if len(bits) != len(bases_alice):
                enviar_mensaje(conn_a, {'status': 'error', 'detalle': 'Numero de bits no coincide con numero de bases'})
                conn_a.close()
                continue

            print(f"[SERVIDOR] Alice envia {len(bits)} qubits")

             # Creamos fila privisional BB84_RONDAS: devuelve True si INSERT funciona, sino False
            if not crear_ronda_pendiente_en_bd(db_conn, id_configuracion, numero_ronda, len(bits)):
                enviar_mensaje(conn_a, {
                    'status': 'error',
                    'detalle': 'No se pudo crear ronda provisional en BB84_rondas',
                    'id_configuracion': id_configuracion,
                    'numero_ronda': numero_ronda,
                })
                conn_a.close()
                continue

            # Si se inserta la fila provisional: OK a Alice
            enviar_mensaje(conn_a, {
                'status': 'ok',
                'mensaje': f'{len(bits)} qubits recibidos',
                'id_configuracion': id_configuracion,
                'numero_ronda': numero_ronda,
            })
            conn_a.close()

            # (COMO YA TENEMOS LOS BITS DE ALICE PODEMOS INICIALIZAR A EVE)
            # Creamos instancia Eve, aquí se ejecuta su innit (eve.py), PREPARAMOS:
            eve_protocol = EavesdropperProtocol(
                percentage_intercepted=err.eve_percentage_intercepted if err.eve_activa else 0,
                key_size=len(bits),
                verbose=getattr(err, "VERBOSE_EVE", getattr(err, "VERBOSE_EVE", False)),
            )



            ################
            # (2) RECIBIR DE BOB
            print("[SERVIDOR] Esperando Bob...")
            servidor_socket.settimeout(BOB_WAIT_TIMEOUT_S)
            conn_b = None
            # Inicia conexión con Bob:
            try:
                conn_b, addr = servidor_socket.accept()
            # opción 1: ERROR Bob no se conecta en el tiempo límite:
            except socket.timeout:
                print(f"[SERVIDOR] Sin nueva conexión de Bob en {BOB_WAIT_TIMEOUT_S}s.")

                tiempo_total_servidor = time.time() - tiempo_inicio_generacion
                rondas_reales = max(numero_ronda - 1, 0)

                try:
                    rowcount = marcar_configuracion_abortada(
                        id_configuracion=id_configuracion,
                        tiempo_total_sesion=tiempo_total_servidor,
                        total_rondas=rondas_reales,
                        conn=db_conn,
                    )
                    print(
                        f"[SERVIDOR] BB84_configuracion #{id_configuracion} marcada como abortada "
                        f"por inactividad de Bob ({round(tiempo_total_servidor, 2)}s, "
                        f"{rondas_reales} rondas, rondas afectadas={rowcount})"
                    )
                except Exception as e:
                    print(f"[SERVIDOR] Error al marcar configuración abortada por inactividad de Bob: {e}")
                return "timeout_bob"

            # opción 2: ERROR de conexión con Bob:
            except Exception as conn_error:
                print(f"[SERVIDOR] Error aceptando conexión de Bob: {conn_error}")
                raise
            #opción 3: conexión con Bob bien:
            msg_b = recibir_mensaje(conn_b)
            if not msg_b or msg_b.get('tipo') != 'medir_qubits':
                print(f"[SERVIDOR] ERROR: msg_b inválido: {msg_b}")
                enviar_mensaje(conn_b, {'status': 'error'})
                conn_b.close()
                continue
            # Recibe las bases correctamente y las guarda:
            bases_bob = msg_b["bases"]
            print(f"[SERVIDOR] Bob solicita medir con {len(bases_bob)} bases")



            ################
            # Ya tenemos los qubits de Alice y las bases de Bob:
            # (3) CREAR Y EJECUTAR AMBOS PROTOCOLOS CON UNA SOLA sim_run()
            print(f"[SERVIDOR] Iniciando simulación NetSquid (Ronda {numero_ronda})...")

            # Creamos protocolos:
            alice_prot = AliceService(NODE_ALICE, PORT_A, eve_protocol, alice_memory)
            bob_prot = BobReceiver(NODE_BOB, PORT_B, bases_bob, bases_alice, len(bits), bob_memory)
            
            print(f"[SERVIDOR] Iniciando protocolos de Alice y Bob...\n")
            alice_prot.start()
            bob_prot.start()

            # Alice prepara la función de enviar qubits por el canal cuántico a Bob:
            alice_prot.put(ReqEnviarQubits(bits, bases_alice))
            
            # PROTOCOLO EMPIEZA: con sim_run() en simstats_utils.py
            try:
                simstats_data = ejecutar_simulacion_con_simstats(ns, SimStats)
                # PRIMERO: va al AliceService y busca lo que estaba en su .put = ReqEnviarQubits
                # DESPUES: Alice mandará mensaje a Bob que hará que el protocolo se ejcute
            except Exception as sim_error:
                print(f"[SERVIDOR] ERROR en ns.sim_run(): {sim_error}")
                import traceback
                traceback.print_exc()
                raise

            # Generar dark counts reales en posiciones donde no hubo detección real.
            bob_prot.aplicar_dark_counts_reales()

            print(
                f"\n[SERVIDOR] Esperando resultados de Bob... "
                f"(llegaron por canal={getattr(bob_prot, 'qubits_llegados_canal', len(bob_prot.resultados))}, "
                f"detectados={len(bob_prot.resultados)}, "
                f"no_detectados={getattr(bob_prot, 'qubits_no_detectados', 0)})"
            )
            


            ################
            # (4) PROCESAR RESULTADOS Y RESPONDER A BOB
            resultados_para_bob = []
            if getattr(config_bob, "VERBOSE_BOB", False):
                print("[SERVIDOR] Iniciando SIFTING por el canal clásico")
            if not bob_prot.resultados:
                print(f"[SERVIDOR] ADVERTENCIA: Bob no midió ningún qubit en esta ronda")
            
            # Medición hecha después de BobReceiver:
            for res in bob_prot.resultados:
                qid = res["qubit_id"]
                bit_m = res["bit_medido"]
    
                # Por cada qubit medido:
                resultados_para_bob.append({
                    "qubit_id": qid, # posición del qubit
                    "bit_medido": bit_m, # lo que Bob ha medido
                })

            # ENVÍA MENSAJE a Bob:
            enviar_mensaje(conn_b, {
                "status": "ok",
                "id_configuracion": id_configuracion,
                "numero_ronda": numero_ronda,
                "resultados": resultados_para_bob
            })
            conn_b.close()


            ################
            # (5) ESTADÍSTICAS, BASE DE DATOS Y TERMINAR RONDA
            # Mostrar reporte de Eve al final de cada ronda:
            if err.eve_activa and eve_protocol.percentage_intercepted > 0 and getattr(err, "VERBOSE_EVE", False):
                eve_protocol.report()

            # Recopilar estadísticas de la ronda:
            ronda_data = ronda_stats(numero_ronda, alice_prot, bob_prot, 
                                        eve_protocol, bits, bases_alice, bases_bob)

            # Guardar en BD:
            print(f"\n[SERVIDOR] Guardando estadísticas de Ronda {numero_ronda} en MySQL...")
            print(f"{'='*50}")
            guardar_ronda_en_bd(db_conn, id_configuracion, numero_ronda, ronda_data)
            guardar_simstats_en_bd(
                db_conn,
                id_configuracion,
                numero_ronda,
                simstats_data
            )
            
            print(f"[SERVIDOR] QBER canal cuántico (NetSquid): {ronda_data['qber_canal_cuantico']:.2f}%")
            print(f"[SERVIDOR] Qubits perdidos en canal: {ronda_data['qubits_perdidos']}")
            print(f"[SERVIDOR] Qubits recibidos por canal: {ronda_data['qubits_recibidos']}")
            print(f"[SERVIDOR] Qubits detectados por Bob: {ronda_data.get('qubits_detectados', ronda_data['qubits_recibidos'])}")
            print(f"[SERVIDOR] Qubits no detectados por Bob: {ronda_data.get('qubits_no_detectados', 0)}")
            if err.eve_activa:
                print(f"[SERVIDOR] Eve interceptó: {ronda_data['eve_interceptados']:.2f}%")

            print(f"[SERVIDOR] Ronda {numero_ronda} COMPLETADA")
            print(f"{'='*50}\n")
            # Pequeño delay para permitir que el socket servidor se resetee entre rondas
            time.sleep(0.2)

    except Exception as e:
        import traceback
        print(f"[SERVIDOR] Error en sesión {sesion_num}: {e}")
        traceback.print_exc()
        raise
    except KeyboardInterrupt:
        print("\n[SERVIDOR] Interrumpido por usuario")
        raise


### MAIN ###
if __name__ == "__main__":
    # Conexión TCP:
    srv_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv_socket.bind((config.SERVIDOR_IP, config.SERVIDOR_PUERTO))
    srv_socket.listen(5)

    print("=" * 50)
    print(f"SERVIDOR BB84 - CANAL CUÁNTICO ({NUM_CLAVES} CLAVE(S) CONSECUTIVA(S) ")
    print(f"(ACUMULANDO HASTA {TARGET_KEY_BITS} bits)")
    print("=" * 50)

    # Conexión a la base de datos:
    db_conn = conectar_bd()

    try:
        # Se repite hasta que se consigan todas las claves:
        for sesion_num in range(1, NUM_CLAVES + 1):
            # INICIAMOS SESIÓN:
            estado_sesion = iniciar_servidor(srv_socket, db_conn, sesion_num)

            if estado_sesion == "timeout_bob":
                print(f"\n[SERVIDOR] Sesión {sesion_num}/{NUM_CLAVES} ABORTADA por inactividad de Bob.")
                break

            if estado_sesion == "sin_alice":
                print(f"\n[SERVIDOR] Sesión {sesion_num}/{NUM_CLAVES} sin Alice. Deteniendo servidor para no crear sesiones vacías.")
                break

            if estado_sesion == "timeout_alice":
                print(f"\n[SERVIDOR] Sesión {sesion_num}/{NUM_CLAVES} ABORTADA por inactividad de Alice.")
                break

            print(f"\n[SERVIDOR] Sesión {sesion_num}/{NUM_CLAVES} COMPLETADA")
    # Caso interrupcion teclado:
    except KeyboardInterrupt:
        print("\n[SERVIDOR] Interrumpido por usuario")
    # Caso de error:
    except Exception as e:
        import traceback
        print(f"[SERVIDOR] Error fatal: {e}")
        traceback.print_exc()
    # Aunque haya errores, cerramos conexiones:
    finally:
        if db_conn:
            db_conn.close()
        srv_socket.close()
        print("[SERVIDOR] Protocolo completado")