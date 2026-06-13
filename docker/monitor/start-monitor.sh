#!/usr/bin/env bash
set -e

MYSQL_DATADIR="/var/lib/mysql"

echo "[MONITOR] Iniciando SSH..."
mkdir -p /run/sshd
/usr/sbin/sshd

echo "[MONITOR] Preparando MariaDB..."
mkdir -p /run/mysqld "$MYSQL_DATADIR"
chown -R mysql:mysql /run/mysqld "$MYSQL_DATADIR"

# Si una inicialización anterior quedó a medias, puede existir /var/lib/mysql/mysql
# pero faltar tablas del sistema como mysql.db. En ese caso se reinicializa.
if [ ! -d "$MYSQL_DATADIR/mysql" ] || ! compgen -G "$MYSQL_DATADIR/mysql/db.*" >/dev/null; then
    echo "[MONITOR] Inicializando MariaDB desde cero..."
    rm -rf "$MYSQL_DATADIR"/*
    mariadb-install-db --user=mysql --datadir="$MYSQL_DATADIR"
    chown -R mysql:mysql "$MYSQL_DATADIR"
fi

echo "[MONITOR] Arrancando MariaDB..."
mariadbd --user=mysql --datadir="$MYSQL_DATADIR" --bind-address=0.0.0.0 &

until mysqladmin ping >/dev/null 2>&1; do
    sleep 1
done

echo "[MONITOR] Ejecutando init_monitor.sql..."
mysql < /usr/local/etc/init_monitor.sql

echo "[MONITOR] Ajustando permisos Grafana..."
chmod -R 777 /var/lib/grafana

echo "[MONITOR] Arrancando Grafana..."
exec /run.sh
