### MESSAGES: Constructor de todos los mensajes ###
### Definición de tipos de mensaje a enviar###
TIPO_ENVIAR_QUBITS = "enviar_qubits"
TIPO_MEDIR_QUBITS = "medir_qubits"
TIPO_ENVIAR_BASES_BOB = "enviar_bases_bob"
TIPO_SAVE_KEY_ID = "save_key_id"
TIPO_CLAVE_COMPLETA = "clave_completa"
TIPO_RECONCILIATION_PARITY_REQUEST = "reconciliation_parity_request"
TIPO_RECONCILIATION_PARITY_RESPONSE = "reconciliation_parity_response"
TIPO_RECONCILIATION_HASH = "reconciliation_hash"
TIPO_RECONCILIATION_RESULT = "reconciliation_result"

### Mensaje enviado ALICE -> NETSQUID ####
def msg_enviar_qubits(bits, bases):
    return {
        "tipo": TIPO_ENVIAR_QUBITS,
        "bits": bits,
        "bases": bases,
    }

### Mensaje enviado BOB -> NETSQUID ####
def msg_medir_qubits(bases):
    return {
        "tipo": TIPO_MEDIR_QUBITS,
        "bases": bases,
    }

# SIFTING #
### Mensaje enviado BOB -> ALICE ####
def msg_bases_bob(bases, ids_recibidos):
    return {
        "tipo": TIPO_ENVIAR_BASES_BOB,
        "bases": bases,
        "ids_recibidos": ids_recibidos,
    }

### Mensaje enviado ALICE -> BOB ####
def msg_sifting_ok(posiciones_coincidentes):
    return {
        "status": "ok",
        "posiciones_coincidentes": posiciones_coincidentes,
    }


# ESTIMACIÓN DE PARÁMETROS (QBER) #
### Mensaje enviado BOB -> ALICE ####
def msg_qber_request(indices_test, bits_test):
    return {
        "posiciones_test": indices_test,
        "bits_test": bits_test,
    }

### Mensaje enviado ALICE -> BOB ####
def msg_qber_result_abort(qber):
    return {
        "status": "abort",
        "qber": qber,
    }
### Mensaje enviado ALICE -> BOB ####
def msg_qber_result_ok(qber):
    return {
        "status": "ok",
        "qber": qber,
    }


# CORRECCIÓN DE ERRORES #
### Mensaje enviado BOB -> ALICE ####
def msg_reconciliation_parity_request(indices):
    return {
        "tipo": TIPO_RECONCILIATION_PARITY_REQUEST,
        "indices": indices,
    }
### Mensaje enviado ALICE -> BOB ####
def msg_reconciliation_parity_response(paridad):
    return {
        "tipo": TIPO_RECONCILIATION_PARITY_RESPONSE,
        "paridad": paridad,
    }


# CONFIRMACIÓN #
### Mensaje enviado BOB -> ALICE ####
def msg_reconciliation_hash(key_hash, correcciones=0, parity_checks=0, leakage_bits=0):
    return {
        "tipo": TIPO_RECONCILIATION_HASH,
        "hash": key_hash,
        "correcciones": correcciones,
        "parity_checks": parity_checks,
        "leakage_bits": leakage_bits,
    }

### Mensaje enviado ALICE -> BOB ####
def msg_reconciliation_result_ok():
    return {
        "tipo": TIPO_RECONCILIATION_RESULT,
        "status": "ok",
        "hash_match": True,
    }

### Mensaje enviado ALICE -> BOB ####
def msg_reconciliation_fail():
    return {
        "tipo": TIPO_RECONCILIATION_RESULT,
        "status": "abort",
        "hash_match": False,
    }

# GUARDAR CLAVE Y PA #
### Mensaje enviado BOB -> ALICE ####
def msg_save_key_id(key_id, pa_seed=None, pa_method=None, final_key_bits=None, pre_pa_bits=None):
    msg = {
        "tipo": TIPO_SAVE_KEY_ID,
        "key_id": key_id,
    }
    if pa_seed is not None:
        msg["pa_seed"] = pa_seed
    if pa_method is not None:
        msg["pa_method"] = pa_method
    if final_key_bits is not None:
        msg["final_key_bits"] = final_key_bits
    if pre_pa_bits is not None:
        msg["pre_pa_bits"] = pre_pa_bits
    return msg


### Mensaje enviado ALICE -> BOB ####
def msg_clave_completa(numero_ronda, id_configuracion=None):
    return {
        "tipo": TIPO_CLAVE_COMPLETA,
        "numero_ronda": numero_ronda,
        "id_configuracion": id_configuracion,
    }


