#!/usr/bin/env bash
# Ejecuta bob.py dentro del contenedor bob
exec docker exec -i bob bash -lc "cd /home/qkd/qkd_netsquid && python -u bob.py"
