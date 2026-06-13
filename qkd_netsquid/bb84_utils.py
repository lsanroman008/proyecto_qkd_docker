### BB84_UTILS ###
# Este módulo no usa sockets, MySQL ni NetSquid.
import hashlib
import math
import random
from typing import Iterable


### CREACIÓN DE QUBITS: BITS Y BASES ###
BASES_BB84 = ("Z", "X")
# Alice genera bits aleatorios:
def generar_bits(num_qubits: int) -> list[int]:
    return [random.randint(0, 1) for _ in range(num_qubits)]
# Alice y Bob generan bases aleatorias:
def generar_bases(num_qubits: int) -> list[str]:
    return [random.choice(BASES_BB84) for _ in range(num_qubits)]


def clave_como_texto(bits: list[int]) -> str:
    return "".join(map(str, bits))


### SIFTING ###
# -> devuelve una lista de int
def filtrar_ids_recibidos(ids_recibidos: Iterable[int], total_qubits: int) -> list[int]:
    return [
        i for i in ids_recibidos
        if isinstance(i, int) and 0 <= i < total_qubits
        # comprobamos número entero: isinstance(i, int)
        # comprobamos rango válido: 0 <= i < total_qubits
    ]

def aplicar_sifting_alice(
    alice_bits: list[int],
    alice_bases: list[str],
    bases_bob: list[str],
    ids_recibidos: list[int],
    verbose: bool = True,
) -> tuple[list[int], list[int], list[int]]:

    posiciones_ok = []
    clave_sifted_alice = []

    for i in ids_recibidos:
        ba = alice_bases[i]
        bb = bases_bob[i]

        if ba == bb:
            if verbose:
                print(f"  Pos {i}: Alice={ba}, Bob={bb} -> COINCIDEN -> bit={alice_bits[i]}")
            
            posiciones_ok.append(i)
            clave_sifted_alice.append(alice_bits[i])
        else:
            if verbose:
                print(f"  Pos {i}: Alice={ba}, Bob={bb} -> NO COINCIDEN -> descartado")

    ids_perdidos = calcular_ids_perdidos(len(alice_bases), ids_recibidos)
    return clave_sifted_alice, posiciones_ok, ids_perdidos

def calcular_ids_perdidos(total_qubits: int, ids_recibidos: Iterable[int]) -> list[int]:
    #Devuelve los IDs enviados por Alice que Bob no recibió:
    recibidos = set(ids_recibidos)
    return [i for i in range(total_qubits) if i not in recibidos]


### ESTIMACIÓN DE PARÁMETROS (QBER) ###
# Función de Bob, SELECCIÓN DE MUESTRA:
def seleccionar_muestra_qber(posiciones_validas: list[int], sample_ratio: float) -> tuple[list[int], list[int]]:
    if not posiciones_validas:
        return [], []

    # Mínimo 1 bit de test, máximo el total de posiciones válidas:
    # sample_ratio = porcentaje que se revelan, QBER_SAMPLE_RATIO
    num_test = max(1, math.ceil(sample_ratio * len(posiciones_validas)))
    # Comprobamos que no sea mayor que el total de posiciones válidas:
    num_test = min(num_test, len(posiciones_validas))

    # Elegimos aleatoriamente INDICES
    indices_test = sorted(random.sample(range(len(posiciones_validas)), num_test))
    posiciones_test = [posiciones_validas[i] for i in indices_test]
    return indices_test, posiciones_test

# Función de Alice, CÁLCULO:
def calcular_qber_muestra(
    alice_bits: list[int],
    posiciones_sifting: list[int],
    indices_test: list[int],
    bits_bob_test: list[int],
    verbose: bool = True,
) -> tuple[float, int, int]:
    errores = 0

    for idx, bit_bob in zip(indices_test, bits_bob_test):
        if idx < len(posiciones_sifting):
            pos_original = posiciones_sifting[idx]
            bit_alice = alice_bits[pos_original]
            if bit_alice != bit_bob:
                errores += 1
                if verbose:
                    print(f"Sifted[{idx}] (orig {pos_original}): Alice={bit_alice}, Bob={bit_bob} -> ERROR")
            else:
                if verbose:
                    print(f"Sifted[{idx}] (orig {pos_original}): Alice={bit_alice}, Bob={bit_bob} -> OK")

    total_test = len(indices_test)
    # Si hay bits de test (total_test > 0), calculamos)
    qber = (errores / total_test) * 100 if total_test > 0 else 0.0
    return qber, errores, total_test

# QUITAR BITS REVELADOS en QBER
def quitar_indices_test(bits_sifted: list[int], indices_test: Iterable[int]) -> list[int]:
    test_set = set(indices_test)
    # Se comprueba si el índice del bits_sifted en el que esté está en test_set:
    return [bit for i, bit in enumerate(bits_sifted) if i not in test_set]


### CORRECCIÓN DE ERRORES ###
# CASCADE DE BOB:
def cascade_reconcile_bob(
    bits_bob: list[int],
    qber_pct: float,
    pedir_paridad_alice,
    rondas: int = 5,
    seed_base: str = "Cascade:",
    verbose: bool = False,
) -> tuple[list[int], dict]:

    reconciliada = list(bits_bob)
    total_bits = len(reconciliada)

    stats = {
        "correcciones": 0,
        "parity_checks": 0,
        "leakage_bits": 0,
        "block_tam_inicial": calcular_tamano_bloque_cascade(qber_pct, total_bits),
        "rondas": rondas,
        "block_plan": [],
    }

    if total_bits == 0:
        return reconciliada, stats

    # (3) Función para pedir paridad a Alice:
    def pedir(indices):
        stats["parity_checks"] += 1
        stats["leakage_bits"] += 1
        return pedir_paridad_alice(indices) # devuelve la paridad de Alice para esos índices

    bloque_base = stats["block_tam_inicial"]
    # (4) Define los tamaños de bloques:
    plan_bloques = [
        max(4, bloque_base // 2), # / 2
        bloque_base,
        min(total_bits, bloque_base * 2), # * 2
        max(4, bloque_base // 3), # / 3
        min(total_bits, bloque_base * 4), # * 4
        4,
        8,
        16,
        32,
    ][:max(1, rondas)]
    stats["block_plan"] = plan_bloques

    # pasada = número de vuelta
    # tamano_bloque = tamaño del bloque en esa vuelta
    for pasada, tamano_bloque in enumerate(plan_bloques):
        # (1) Genera lista de índices mezclados:
        permutacion = permutacion_indices(total_bits, f"{seed_base}:{pasada}:{total_bits}:{tamano_bloque}")
        # MENSAJES:
        if verbose:
            print(f"[BOB][CASCADE] Pasada {pasada + 1}/{len(plan_bloques)}, bloque={tamano_bloque}")
        # (2) Dividimos bloques:
        for bloque in bloques_div(permutacion, tamano_bloque):
            if not bloque:
                continue
            # (3) Pedimos paridad a Alice y comparamos:
            if paridad_bits(reconciliada, bloque) == pedir(bloque): # bloque es una lista de índices
                continue

            # (4) Si la paridad no coincide, hay un error en ese bloque. Lo localizamos por bisección:
            idx_error = buscar_error_biseccion(reconciliada, bloque, pedir)
            # Si hay un bit mal:
            if idx_error is not None:
                # Cambiamos el bit erróneo:
                reconciliada[idx_error] = 1 - reconciliada[idx_error]
                stats["correcciones"] += 1
                if verbose:
                    print(f"[BOB][CASCADE] Corrección en índice {idx_error}")

    return reconciliada, stats

# Se calcula el tamaño inicial según el qber:
def calcular_tamano_bloque_cascade(qber_pct: float, total_bits: int) -> int:
    if total_bits <= 0:
        return 1

    # QBER a valor decimal:
    qber = max(float(qber_pct) / 100.0, 0.001)
    bloque = int(round(0.73 / qber))
    bloque = max(4, min(32, bloque))
    return min(bloque, total_bits)


# CASCADE DE BOB:
# (1) Reorganizamos los bits de Bob:
def permutacion_indices(total_bits: int, seed: str) -> list[int]:
    indices = list(range(total_bits))

    rng = random.Random(seed)
    rng.shuffle(indices)
    return indices

# (2) Dividimos los bloques:
def bloques_div(indices: list[int], tamano_bloque: int):
    for i in range(0, len(indices), tamano_bloque):
        yield indices[i:i + tamano_bloque]

# (3) Cálculo de paridad: 
def paridad_bits(bits: list[int], indices: Iterable[int] | None = None) -> int: # devuelve un int
    if indices is None:
        return sum(bits) % 2 # paridad de toda la lista (%2 = el resto al dividir entre 2)

    total = 0
    for idx in indices:
        if idx < 0 or idx >= len(bits):
            raise IndexError(f"Índice fuera de rango en paridad: {idx}")
        total += bits[idx] # suma bit de la posición
    return total % 2

# (4) Buscar error dividiendo el bloque actual:
def buscar_error_biseccion(bits_bob: list[int], bloque: list[int], pedir_paridad_alice) -> int | None:
    actual = list(bloque)

    # Se repite hasta dar con el bit erróneo:
    while len(actual) > 1:
        mitad = max(1, len(actual) // 2)
        izquierda = actual[:mitad]
        derecha = actual[mitad:]

        # Volvemos a comprobar paridad: Bob vs Alice
        if paridad_bits(bits_bob, izquierda) != pedir_paridad_alice(izquierda):
            actual = izquierda
        else:
            actual = derecha

    # Devuelve índice de bite erróneo si lo encuentra, sino None:
    return actual[0] if actual else None


### CONFIRMACIÓN ###
def sha256_bits(bits: list[int]) -> str:
    return hashlib.sha256(clave_como_texto(bits).encode("utf-8")).hexdigest()


### AMPLIFICACIÓN DE PRIVACIDAD ###
# Generación de semilla con bits aleatorios públicos:
def generar_toeplitz_seed(input_bits: int, output_bits: int) -> str:
    # Comprueba parámetros válidos:
    if input_bits <= 0 or output_bits <= 0:
        raise ValueError("input_bits y output_bits deben ser positivos")
    # Genera números aleatorios:
    rng = random.SystemRandom()
    # Genera números aleatorios 0 y 1 = rng.randint(0, 1)
    # Longitud = input + output - 1
    return "".join(str(rng.randint(0, 1)) for _ in range(input_bits + output_bits - 1))

# Aplica PA:
def aplicar_pa(
    key_bits: list[int],
    seed,
    final_key_bits: int = 256,
    method: str = "TOEPLITZ",
    pre_pa_bits: int | None = None,
) -> list[int]:

    method = str(method or "TOEPLITZ").upper().strip() # comprueba nombre método
    material = list(key_bits) # copia de la clave en modo lista

    if pre_pa_bits is not None:
        material = material[:int(pre_pa_bits)]
    # Comprobación de bits:
    if len(material) < final_key_bits:
        raise ValueError(
            f"No hay suficientes bits pre-PA: {len(material)}/{final_key_bits}"
        )

    # OPC 1: Si el método es NONE, solo recorta la clave final:
    if method == "NONE":
        return material[:final_key_bits]
    # OPC 2: Error
    if method != "TOEPLITZ":
        raise ValueError(f"Método de privacy amplification no soportado: {method}")
    # OPC 3: Método TOEPLITZ:
    return toeplitz_hash_bits(material, seed, final_key_bits)

# Método Toeplitz:
def toeplitz_hash_bits(input_key_bits: list[int], seed, output_bits: int) -> list[int]:
    # Convierte clave lista:
    input_key_bits = list(input_key_bits)
    # Guarda cuántos bits tiene la clave de entrada:
    input_bits = len(input_key_bits)
    # Normaliza semilla a lista de bits:
    seed_bits = normalizar_seed_bits(seed)

    # Salida mínimo 1 bit:
    if output_bits <= 0:
        raise ValueError("output_bits debe ser positivo")
    # No puede aumentar tamaño de la clave:
    if input_bits < output_bits:
        raise ValueError(
            f"Privacy amplification requiere input_bits >= output_bits "
            f"(input={input_bits}, output={output_bits})"
        )

    # Comprueba longitud de la semilla esperada:
    exp_seed_len = input_bits + output_bits - 1
    if len(seed_bits) != exp_seed_len:
        raise ValueError(
            f"Longitud de semilla Toeplitz incorrecta: recibida={len(seed_bits)}, esperada={exp_seed_len}"
        )

    # CRACIÓN DE LA MATRIZ:
    salida = []
    # T[i][j] = seed[output_bits - 1 - i + j]

    # Recorre cada bit de salida:
    for i in range(output_bits):
        acc = 0
        # Calcula posición de la semilla para este bit de salida:
        offset = output_bits - 1 - i
        # Recorre cada bit de la clave de entrada:
        for j, bit in enumerate(input_key_bits):
            # Comprueba que el bit sea 0 o 1:
            if bit not in (0, 1):
                raise ValueError("La clave pre-PA debe contener solo bits 0/1")
            
            # AND: bit & seed_bits[offset + j]
            # XOR: acc ^
            acc ^= (bit & seed_bits[offset + j])
        salida.append(acc)

    return salida


def normalizar_seed_bits(seed) -> list[int]:
    # Semilla es un string:
    if isinstance(seed, str):
        seed = seed.strip()
        # Comprueba que solo tenga 0 y 1:
        if any(ch not in "01" for ch in seed):
            raise ValueError("La semilla Toeplitz debe contener solo 0/1")
        
        # Convierte cada caracter '0' o '1' a entero 0 o 1:
        return [int(ch) for ch in seed]

    # Comprueba todos los elementos y devuelve lista:
    if isinstance(seed, list):
        if any(bit not in (0, 1) for bit in seed):
            raise ValueError("La semilla Toeplitz debe contener solo bits 0/1")
        return list(seed)

    raise TypeError("La semilla Toeplitz debe ser str o list[int]")