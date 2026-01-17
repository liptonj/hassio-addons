FROM ghcr.io/home-assistant/amd64-base:3.20

# Copy from official MariaDB addon
# Install MariaDB
RUN apk add --no-cache mariadb mariadb-client \
    && mkdir -p /var/run/mysqld \
    && chown mysql:mysql /var/run/mysqld

# Copy configuration
COPY rootfs /

# Expose port for external access
EXPOSE 3306

WORKDIR /data
