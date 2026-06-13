### SIMSTATS_UTILS ###
## EJECUTAMOS EL PROTOCOLO ##
# ns_module = netsquid, simstatsclass = para estadisticas
def ejecutar_simulacion_con_simstats(ns_module, SimStatsClass):
    # Creamos instancia para coger parámetros de simulación:
    sim_stats = SimStatsClass()

    # Grabamos estadísticas:
    with sim_stats.record():
        # EJECUTAMOS SIMULACIÓN:
        ns_module.sim_run()
    return {
        # Tiempo dentro de la simulación:
        "simstats_sim_time_ns": safe_call(ns_module, "sim_time"),
    }


# Llamar a función:
def safe_call(obj, name):
    try:
        fn = getattr(obj, name, None)
        # Comprueba que sim_time se puede ejecutar:
        if callable(fn):
            return fn()
     # Error, pasa:
    except Exception:
        pass
    return None

