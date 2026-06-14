-- init_monitor.sql
-- BD global de monitorización QKD/BB84
--
-- Esquema esperado en monitor:
--   QKD_netsquid.BB84_configuracion
--   QKD_netsquid.BB84_rondas
--   QKD_netsquid.BB84_simstats
--   QKD_netsquid.QKD_keys_alice
--   QKD_netsquid.QKD_keys_bob

-- Las claves finales locales viven en Alice/Bob:
--   alice.QKD_keys_KMS1.QKD_keys
--   bob.QKD_keys_KMS1.QKD_keys
-- En monitor solo se guardan copias para Grafana:
--   QKD_netsquid.QKD_keys_alice
--   QKD_netsquid.QKD_keys_bob

CREATE DATABASE IF NOT EXISTS `QKD_netsquid`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Evita que MariaDB resuelva conexiones locales como usuario anónimo.
DROP USER IF EXISTS ''@'localhost';
DROP USER IF EXISTS ''@'%';

CREATE USER IF NOT EXISTS 'QKD'@'localhost' IDENTIFIED BY '';
CREATE USER IF NOT EXISTS 'QKD'@'127.0.0.1' IDENTIFIED BY '';
CREATE USER IF NOT EXISTS 'QKD'@'%' IDENTIFIED BY '';

CREATE USER IF NOT EXISTS 'KMS'@'localhost' IDENTIFIED BY '';
CREATE USER IF NOT EXISTS 'KMS'@'127.0.0.1' IDENTIFIED BY '';
CREATE USER IF NOT EXISTS 'KMS'@'%' IDENTIFIED BY '';

GRANT ALL PRIVILEGES ON `QKD_netsquid`.* TO 'QKD'@'localhost';
GRANT ALL PRIVILEGES ON `QKD_netsquid`.* TO 'QKD'@'127.0.0.1';
GRANT ALL PRIVILEGES ON `QKD_netsquid`.* TO 'QKD'@'%';

GRANT ALL PRIVILEGES ON `QKD_netsquid`.* TO 'KMS'@'localhost';
GRANT ALL PRIVILEGES ON `QKD_netsquid`.* TO 'KMS'@'127.0.0.1';
GRANT ALL PRIVILEGES ON `QKD_netsquid`.* TO 'KMS'@'%';

USE `QKD_netsquid`;

-- CONFIGURACÍON DE LA SESIÓN --
CREATE TABLE IF NOT EXISTS `BB84_configuracion` (
    `id_configuracion` INT NOT NULL AUTO_INCREMENT,
    `timestamp_inicio` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Estado general de la sesión
    `estado` ENUM('en_progreso','completada','abortada') NOT NULL DEFAULT 'en_progreso',
    `bits_objetivo` INT NOT NULL DEFAULT 256,
    `tiempo_total_sesion` FLOAT DEFAULT NULL,
    `total_rondas` INT DEFAULT NULL,

    -- Parámetros físicos del canal
    `distancia_km` FLOAT NOT NULL,
    `atenuacion_db_km` FLOAT NOT NULL,
    `velocidad_fibra_km_s` INT NOT NULL,
    `prob_loss_in` FLOAT NOT NULL,

    -- Ruido cuántico
    `usar_depolarizacion` TINYINT(1) NOT NULL,
    `despolarizacion` FLOAT NOT NULL,
    `usar_dephase` TINYINT(1) NOT NULL,
    `dephase` FLOAT NOT NULL,
    `usart1t2_noise` TINYINT(1) NOT NULL,
    `T1_ns` FLOAT NOT NULL,
    `T2_ns` FLOAT NOT NULL,

    -- Detector / medición
    `usar_measure_faulty` TINYINT(1) NOT NULL DEFAULT 0,
    `prob_error_medicion_0` FLOAT NOT NULL DEFAULT 0.0,
    `prob_error_medicion_1` FLOAT NOT NULL DEFAULT 0.0,
    `usar_detector_efficiency` TINYINT(1) NOT NULL DEFAULT 0,
    `detector_efficiency` FLOAT NOT NULL DEFAULT 1.0,

    -- Desalineación, dark counts reales y jitter
    `usar_misalignment` TINYINT(1) NOT NULL DEFAULT 0,
    `misalignment_prob` FLOAT NOT NULL DEFAULT 0.0,
    `usar_dark_counts_reales` TINYINT(1) NOT NULL DEFAULT 0,
    `prob_dark_count_real` FLOAT NOT NULL DEFAULT 0.0,
    `usar_jitter_basico` TINYINT(1) NOT NULL DEFAULT 0,
    `jitter_prob_perdida` FLOAT NOT NULL DEFAULT 0.0,

    -- EVE
    `eve_activa` TINYINT(1) NOT NULL,
    `eve_percentage_intercepted` INT NOT NULL DEFAULT 0,
    `eve_error_rate` FLOAT NOT NULL DEFAULT 0.0,

    -- (2) ESTIMACIÓN DE PARÁMETROS (QBER) --
    `qber_abort_threshold` FLOAT DEFAULT NULL,
    
    -- (3) CORRECCIÓN DE ERRORES (RECONCILIACIÓN) -- 
    `reconciliacion_total_correcciones` INT DEFAULT 0,
    `reconciliacion_total_leakage_bits` INT DEFAULT 0,
    `rondas_abortadas_reconciliacion` INT DEFAULT 0,

    -- (5) PRIVACY AMPLIFICATION --
    `pa_metodo` VARCHAR(40) DEFAULT NULL,
    `pa_input_bits` INT DEFAULT NULL,
    `pa_output_bits` INT DEFAULT NULL,
    `pa_reduction_bits` INT DEFAULT NULL,
    `bits_finales_guardados` INT DEFAULT NULL,

    PRIMARY KEY (`id_configuracion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- MÉTRICAS POR RONDA --
CREATE TABLE IF NOT EXISTS `BB84_rondas` (
    `id_ronda` INT NOT NULL AUTO_INCREMENT,
    `id_configuracion` INT NOT NULL,
    `numero_ronda` INT NOT NULL,
    `timestamp_ronda` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Estado de la ronda
    -- 0 = válida, 1 = abortada/descartada, 2 = provisional/pendiente
    `ronda_abortada` TINYINT DEFAULT 2,
    `tiempo_ronda_seg` FLOAT DEFAULT NULL,

    -- Transmisión cuántica / pérdidas
    `qubits_enviados` INT DEFAULT NULL,
    `qubits_recibidos` INT DEFAULT NULL,
    `qubits_perdidos` INT DEFAULT NULL,
    `tasa_perdida_pct` FLOAT DEFAULT NULL,
    `qubits_detectados` INT DEFAULT NULL,
    `qubits_no_detectados` INT DEFAULT NULL,

    -- Errores físicos extendidos
    `errores_measure_faulty` INT DEFAULT NULL,
    `errores_misalignment` INT DEFAULT NULL,
    `dark_counts_generados` INT DEFAULT NULL,
    `qubits_perdidos_jitter` INT DEFAULT NULL,

    -- (2) ESTIMACIÓN DE PARÁMETROS (QBER) --
    `bits_sifted` INT DEFAULT NULL,
    `qber_canal_cuantico` FLOAT DEFAULT NULL,
    `qber_verificacion` FLOAT DEFAULT NULL,
    `qber_revelados_bits` INT DEFAULT NULL,
    `eve_interceptados_pct` FLOAT DEFAULT NULL,

    -- Bits acumulados tras QBER
    `bits_validos` INT DEFAULT NULL,
    `bits_acumulados` INT DEFAULT NULL,

    -- (3) CORRECCIÓN DE ERRORES (RECONCILIACIÓN) --
    `bits_post_qber` INT DEFAULT NULL,
    `reconciliacion_ok` TINYINT DEFAULT NULL,
    `reconciliacion_correcciones` INT DEFAULT 0,
    `reconciliacion_leakage_bits` INT DEFAULT 0,
    `reconciliacion_hash_match` TINYINT DEFAULT NULL,
    `bits_post_reconciliacion` INT DEFAULT NULL,

    PRIMARY KEY (`id_ronda`),
    UNIQUE KEY `uq_configuracion_ronda` (`id_configuracion`, `numero_ronda`),

    CONSTRAINT `fk_rondas_configuracion`
      FOREIGN KEY (`id_configuracion`)
      REFERENCES `BB84_configuracion` (`id_configuracion`)
      ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- SIMSTAT (MAL, BORRAR!!!) --
CREATE TABLE IF NOT EXISTS `BB84_simstats` (
    `id_simstats` INT NOT NULL AUTO_INCREMENT,
    `id_configuracion` INT NOT NULL,
    `numero_ronda` INT NOT NULL,
    `timestamp_simstats` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    `simstats_sim_time_ns` FLOAT DEFAULT NULL,

    PRIMARY KEY (`id_simstats`),
    UNIQUE KEY `uq_simstats_configuracion_ronda` (`id_configuracion`, `numero_ronda`),

    CONSTRAINT `fk_simstats_configuracion`
      FOREIGN KEY (`id_configuracion`)
      REFERENCES `BB84_configuracion` (`id_configuracion`)
      ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- CLAVES QKD DE ALICE Y BOB --
CREATE TABLE IF NOT EXISTS `QKD_keys_alice` (
    `key_id` VARCHAR(40) PRIMARY KEY,
    `key_value` VARCHAR(1290) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `QKD_keys_bob` (
    `key_id` VARCHAR(40) PRIMARY KEY,
    `key_value` VARCHAR(1290) NOT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


FLUSH PRIVILEGES;
