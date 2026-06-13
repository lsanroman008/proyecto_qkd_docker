#!/usr/bin/env bash
# Ejecuta alice.py dentro del contenedor alice
exec docker exec -i alice bash -lc "cd /home/qkd/qkd_netsquid && python -u alice.py"
