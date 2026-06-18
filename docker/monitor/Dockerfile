FROM grafana/grafana:latest-ubuntu

USER root

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    mariadb-server \
    mariadb-client \
    bash \
    openssh-server \
    sudo \
    iproute2 \
    net-tools \
    iputils-ping \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash qkd && \
    echo "qkd:qkd" | chpasswd && \
    usermod -aG sudo qkd && \
    echo "qkd ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p /run/sshd

RUN mkdir -p /run/mysqld /var/lib/mysql /var/lib/grafana && \
    chown -R mysql:mysql /run/mysqld /var/lib/mysql && \
    chmod -R 777 /var/lib/grafana

COPY init_monitor.sql /usr/local/etc/init_monitor.sql
COPY start-monitor.sh /usr/local/bin/start-monitor.sh

RUN chmod +x /usr/local/bin/start-monitor.sh

EXPOSE 22 3000 3306

ENTRYPOINT ["/usr/local/bin/start-monitor.sh"]