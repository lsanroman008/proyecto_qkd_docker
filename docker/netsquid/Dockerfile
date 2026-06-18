# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    sudo \
    gcc \
    g++ \
    python3-dev \
    iputils-ping \
    net-tools \
    iproute2 \
    default-mysql-client \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python base del proyecto.
# mysql-connector-python es necesario para db_utils.py.
# NumPy/Scipy se fijan para evitar incompatibilidades de NetSquid con NumPy 2.x.
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir \
        mysql-connector-python \
        "numpy==1.26.4" \
        "scipy==1.13.1"

# Usuario qkd y SSH.
RUN useradd -m -s /bin/bash qkd && \
    echo "qkd:qkd" | chpasswd && \
    adduser qkd sudo && \
    echo "qkd ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p /run/sshd

# Evita el error TLS/SSL del cliente mysql CLI en la red Docker.
RUN mkdir -p /etc/mysql/conf.d && \
    printf "[client]\nssl=0\n" > /etc/mysql/conf.d/disable_ssl.cnf

# Instalación privada de NetSquid mediante secreto BuildKit.
# Requiere en docker-compose.yaml:
#   build:
#     secrets:
#       - netsquid_creds
RUN --mount=type=secret,id=netsquid_creds \
    python -m pip install --no-cache-dir netsquid $(cat /run/secrets/netsquid_creds) && \
    python -m pip install --no-cache-dir --force-reinstall \
        "numpy==1.26.4" \
        "scipy==1.13.1"

WORKDIR /home/qkd

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]