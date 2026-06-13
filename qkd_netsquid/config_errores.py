### CONFIGURACIÓN DE PARÁMETROS DE ERROR ###
### PÉRDIDAS ###
distancia = 25.0 #(KM)
atenuacion = 0.2 #(dB/KM)
prob_loss_in = 0.3 
velocidad_fibra = 200000  # (km/s)
# UTILIZADOS EN BOB:
# Qubits que no se detectan:
usar_detector_efficiency = True
detector_efficiency = 0.85  
# Qubits recibidos que se descartan por mala sincronización:
usar_jitter_basico = True
jitter_prob_perdida = 0.02 


### ERRORES DEL CANAL ###
# Depolarización:
usar_depolarizacion = True
despolarizacion = 0.001
# Desfase:
usar_dephase = True
dephase = 0.001
# Modelo ruido por qubits en memoria:
usart1t2_noise = True
T1_ns = 100e6 # tiempo de relajación
T2_ns = 50e6 # tiempo de decoherencia


### ERRORES DE MEDICIÓN ###
# Error de lectura al medir:
usar_measure_faulty = True
prob_error_medicion_0 = 0.02
prob_error_medicion_1 = 0.02
# Desalineación del detector, causa un flip en el qubit:
usar_misalignment = True
misalignment_prob = 0.02
# Detección cuando no llega ningún bit:
usar_dark_counts_reales = True
prob_dark_count_real = 0.003  


### EVE ###
# True = Eve activa
# False = Eve desactivada
eve_activa = True   
eve_percentage_intercepted = 30 # Cuanto porcentaje de qubits intercepta
eve_error_rate = 0.01 # error extra aplicado por Eve

### MENSAJES EN PANTALLA DE EVE ###
# True = saca todas las interceptaciones de Eve
# False = solo escribe el servidor
VERBOSE_EVE = False
