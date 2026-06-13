### EVE - EAVESDROPPER BB84 ###
import random
import numpy as np

import config_errores as err

### NETSQUID ###
import netsquid as ns
# Qubits
from netsquid.qubits import qubitapi as qapi
from netsquid.qubits import operators as ops
# Components
from netsquid.components import Message
# Modelos de ruido
from netsquid.components.models.qerrormodels import T1T2NoiseModel


class EavesdropperProtocol:
    def __init__(self, percentage_intercepted=0, key_size=20, verbose=True):
        self.percentage_intercepted = percentage_intercepted
        self.key_size = key_size
        self.verbose = verbose

        # Determinar CUÁNTOS qubits va a interceptar:
        if percentage_intercepted == 0:
            self.num_intercepted = 0
        else:
            # +99 para que la division redondee hacia arriba
            self.num_intercepted = max(1, int(np.ceil(key_size * percentage_intercepted / 100)))

        # Si Eve intercepta CUALES:
        if self.num_intercepted > 0:
            self.intercepted_indices = set(
                np.random.choice(np.arange(key_size), size=self.num_intercepted, replace=False)
            )
        # Si Eve NO intercepta, no se coge ninguno:
        else:
            self.intercepted_indices = set()

        # Va uno a uno (idx) y se asigna una BASE aleatoria:
        self.eve_bases = {
            idx: random.choice(['Z', 'X'])
            for idx in self.intercepted_indices
        }

        # Tasa de ERROR de Eve:
        self.eve_error_rate = err.eve_error_rate
        # Almacenar RESULTADOS de medidas de Eve:
        self.eve_measurements = {}

        # MENSAJES salen siempre:
        if self.verbose:
            if self.num_intercepted > 0:
                print(f"[EVE] Configurada para interceptar el {percentage_intercepted}%")
                indices = [int(x) for x in sorted(self.intercepted_indices)]
                print(f"[EVE] Qubits interceptados: {indices}")
            else:
                print(f"[EVE] DESACTIVADA (0%)")

    ## PROCESO COMPLETO DE INTERCEPCIÓN DE EVE ##
    def medir_recodificar_qubit(self, qubit_id, qubit, alice_base):
        # Comprueba si el qubit está en la lista de interceptados
        if qubit_id not in self.intercepted_indices:
            return qubit

        # Medir el qubit en base aleatoria de Eve (colapsa el estado)
        eve_base = self.eve_bases[qubit_id]
        eve_bit = self.medir_qubit(qubit, eve_base)

        # Guardar información de diagnóstico
        self.eve_measurements[qubit_id] = {
            'eve_base': eve_base,
            'eve_bit': eve_bit,

            'alice_base': alice_base,
            'bases_match': eve_base == alice_base
        }

        # Eve reenvía el bit que ha medido, en la misma base que ha usado para medir.
        new_qubit = self.recodificar_qubit(eve_bit, eve_base)

        # COMENTARIOS:
        if self.verbose:
            match_str = "OK" if eve_base == alice_base else "ERROR"
            print(
                f"[EVE] Qubit {int(qubit_id)}: midió {eve_bit} en base {eve_base} "
                f"-> {match_str} -> Reenvía {eve_bit} en base {eve_base}"
        )

        return new_qubit

    # Mide qubit:
    def medir_qubit(self, qubit, base):
        if base == 'X':
            qapi.operate(qubit, ops.H)  # Convertir de X a Z antes de medir
        measured_bit = int(qapi.measure(qubit, observable=ops.Z)[0])
        return measured_bit


    # Recodifica el qubit para reenviarlo a Bob:
    def recodificar_qubit(self, bit, base):
        qubit = qapi.create_qubits(1)[0]

        if base == 'Z':
            if bit == 1:
                qapi.operate(qubit, ops.X)
        else:
            qapi.operate(qubit, ops.H)
            if bit == 1:
                qapi.operate(qubit, ops.Z)

        # Aplicar ruido T1T2 si Eve introduce su propio ruido
        if err.usart1t2_noise:
            noise_processor = T1T2NoiseModel(T1=err.T1_ns, T2=err.T2_ns)
            noise_processor.apply_noise(qubit, t=ns.sim_time())

        # Aplicar error aleatorio extra de Eve con probabilidad eve_error_rate:
        if random.random() < self.eve_error_rate:
            qapi.operate(qubit, ops.X)

        return qubit


    ### FINAL ###
    # Reporte de estadísticas de Eve al final de cada ronda:
    def report(self):
        if not self.verbose:
            return

        stats = self.get_statistics()
        print(f"\n{'='*50}")
        print("[EVE REPORTE]")
        print(f"Qubits interceptados: {stats['total_intercepted']}")
        print(f"Base correcta: {stats['base_correcta']}")
        print(f"Base incorrecta: {stats['base_erronea']}")
        print(f"Tasa de error por bases incorrectas: {stats['error_rate']:.1f}%")
        print(f"{'='*50}")


    # Cálculos de Eve
    def get_statistics(self):
        if not self.eve_measurements:
            return {
                'total_intercepted': 0,
                'base_correcta': 0,
                'base_erronea': 0,
                'error_rate': 0.0
            }

        base_correcta = sum(
            1 for m in self.eve_measurements.values() if m['bases_match']
        )
        base_erronea = len(self.eve_measurements) - base_correcta
        error_rate = base_erronea / len(self.eve_measurements) if self.eve_measurements else 0

        return {
            'total_intercepted': len(self.eve_measurements),
            'base_correcta': base_correcta,
            'base_erronea': base_erronea,
            'error_rate': error_rate * 100
        }
