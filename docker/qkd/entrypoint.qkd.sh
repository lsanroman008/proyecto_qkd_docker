#!/usr/bin/env bash
set -e

MYSQL_DATADIR="/var/lib/mysql"
LOCAL_DB="QKD_keys_KMS1"

echo "[QKD] Preparando MariaDB local..."
mkdir -p /run/mysqld "$MYSQL_DATADIR"
chown -R mysql:mysql /run/mysqld "$MYSQL_DATADIR"

if [ -d "$MYSQL_DATADIR/$LOCAL_DB" ]; then
    chown -R mysql:mysql "$MYSQL_DATADIR/$LOCAL_DB"
    chmod 750 "$MYSQL_DATADIR/$LOCAL_DB"
fi

# Si una inicialización anterior quedó a medias, puede existir /var/lib/mysql/mysql
# pero faltar tablas del sistema como mysql.db. En ese caso se reinicializa.
if [ ! -d "$MYSQL_DATADIR/mysql" ] || ! compgen -G "$MYSQL_DATADIR/mysql/db.*" >/dev/null; then
    echo "[QKD] Inicializando MariaDB local desde cero..."
    rm -rf "$MYSQL_DATADIR"/*
    mariadb-install-db --user=mysql --datadir="$MYSQL_DATADIR"
    chown -R mysql:mysql "$MYSQL_DATADIR"
fi

echo "[QKD] Arrancando MariaDB local..."
service mariadb start

until mysqladmin ping >/dev/null 2>&1; do
    sleep 1
done

echo "[QKD] Ejecutando init_local.sql..."
mysql < /usr/local/etc/init_local.sql

echo "[QKD] Arrancando SSH..."
exec /usr/sbin/sshd -D
