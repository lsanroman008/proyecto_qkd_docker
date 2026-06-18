### CONFIGURACIÓN DE PARÁMETROS DE ERROR ###
### (1) PARÁMETROS FÍSICOS DEL CANAL ###
distancia = 25.0  # (KM)
atenuacion = 0.2  # (dB/KM)
velocidad_fibra = 200000  # (km/s)
prob_loss_in = 0.3

### (2) RUIDO DEL CANAL CUÁNTICO ###
# Depolarización:
usar_depolarizacion = True
despolarizacion = 0.001
# Desfase:
usar_dephase = True
dephase = 0.001
# Modelo ruido por qubits en memoria:
usart1t2_noise = True
T1_ns = 100e6  # tiempo de relajación
T2_ns = 50e6  # tiempo de decoherencia

### (3) IMPERFECCIONES FÍSICAS ###
# Desalineación del detector, causa un flip en el qubit:
usar_misalignment = True
misalignment_prob = 0.02
# Qubits recibidos que se descartan por mala sincronización:
usar_jitter_basico = True
jitter_prob_perdida = 0.02

### (4) ERRORES DEL DETECTOR Y DE MEDICIÓN ###
# Qubits que no se detectan:
usar_detector_efficiency = True
detector_efficiency = 0.85
# Detección cuando no llega ningún bit:
usar_dark_counts_reales = True
prob_dark_count_real = 0.003
# Error de lectura al medir:
usar_measure_faulty = True
prob_error_medicion_0 = 0.02
prob_error_medicion_1 = 0.02

### (5) EVE ###
# True = Eve activa
# False = Eve desactivada
eve_activa = True
eve_percentage_intercepted = 30  # Cuánto porcentaje de qubits intercepta
eve_error_rate = 0.01  # error extra aplicado por Eve

### MENSAJES EN PANTALLA DE EVE ###
# True = saca todas las interceptaciones de Eve
# False = solo escribe el servidor
VERBOSE_EVE = False
