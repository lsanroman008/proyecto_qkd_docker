FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Paquetes de sistema:
# - mariadb-server: BBDD local de Alice/Bob
# - default-mysql-client: comando mysql para pruebas
# - openssh-server: acceso SSH
# - iproute2/net-tools/ping: diagnóstico de red
# - gcc/python3-dev: compilaciones Python si alguna dependencia lo requiere
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    sudo \
    gcc \
    python3-dev \
    iputils-ping \
    net-tools \
    iproute2 \
    default-mysql-client \
    mariadb-server \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# MariaDB escuchando también fuera de localhost dentro del contenedor.
# Necesario si se quiere acceder desde el host por los puertos 3310/3320.
RUN sed -i 's/127.0.0.1/0.0.0.0/g' /etc/mysql/mariadb.conf.d/50-server.cnf

# Dependencias Python de Alice/Bob.
# mysql-connector-python es necesario para:
#   import mysql.connector
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir \
        mysql-connector-python

# Evita errores TLS/SSL del cliente mysql CLI en pruebas internas Docker.
RUN mkdir -p /etc/mysql/conf.d && \
    printf "[client]\nssl=0\n" > /etc/mysql/conf.d/disable_ssl.cnf

# Usuario qkd con sudo
RUN useradd -m -s /bin/bash qkd && \
    echo "qkd:qkd" | chpasswd && \
    adduser qkd sudo && \
    echo "qkd ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p /run/sshd

WORKDIR /home/qkd

# SQL local de Alice/Bob
COPY init_local.sql /usr/local/etc/init_local.sql

# Arranque: inicializa MariaDB si el volumen está vacío,
# ejecuta init_local.sql y deja SSH en primer plano.
COPY entrypoint.qkd.sh /usr/local/bin/entrypoint.qkd.sh

RUN chmod +x /usr/local/bin/entrypoint.qkd.sh

EXPOSE 22 3306

ENTRYPOINT ["/usr/local/bin/entrypoint.qkd.sh"]