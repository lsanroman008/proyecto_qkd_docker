#!/usr/bin/env bash
# Ejecuta netSquidControl.py dentro del contenedor netsquid
docker exec netsquid pkill -f netSquidControl.py 2>/dev/null || true
exec docker exec -i netsquid bash -lc "cd /home/qkd/qkd_netsquid && python -u netSquidControl.py"
