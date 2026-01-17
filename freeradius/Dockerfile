# FreeRADIUS Server Add-on for Home Assistant
# Alpine-based with RadSec support
#
# Note: Using FreeRADIUS 3.x (stable) until v4 has better package availability
# FreeRADIUS 4.0 is still in alpha with limited distribution support

FROM ghcr.io/home-assistant/amd64-base-python:3.12-alpine3.20

# Install FreeRADIUS and dependencies
RUN apk add --no-cache \
    freeradius \
    freeradius-radclient \
    freeradius-utils \
    freeradius-sqlite \
    freeradius-postgresql \
    freeradius-mysql \
    freeradius-rest \
    freeradius-eap \
    openssl \
    ca-certificates \
    curl \
    sqlite \
    postgresql-client \
    mariadb-client \
    python3 \
    py3-pip \
    py3-cryptography \
    py3-jinja2 \
    certbot \
    bash \
    && rm -rf /var/cache/apk/*

# Install Python packages for configuration API
RUN pip3 install --no-cache-dir --break-system-packages \
    fastapi \
    uvicorn \
    pydantic \
    pydantic-settings \
    pydantic[email] \
    python-multipart \
    sqlalchemy \
    psycopg2-binary \
    pymysql \
    cryptography \
    slowapi \
    httpx \
    jinja2 \
    certbot-dns-cloudflare \
    pytest \
    pytest-asyncio \
    pytest-cov \
    pytest-mock

WORKDIR /app

# Copy new modular application
COPY rootfs/usr/bin/radius_app /usr/bin/radius_app

# Copy database migrations
COPY rootfs/usr/bin/migrations /usr/bin/migrations

# Copy old radius-manager.py for backward compatibility (will be removed)
COPY rootfs/usr/bin/radius-manager.py /usr/bin/radius-manager.py
RUN chmod +x /usr/bin/radius-manager.py

# Copy configuration templates and fallback configs
# These provide secure defaults if dynamic generation fails
COPY rootfs/etc/raddb/clients.conf.template /etc/raddb/clients.conf.template
COPY rootfs/etc/raddb/users.template /etc/raddb/users.template

# Copy secure EAP module configuration (TLS 1.2+, strong ciphers, no MD5)
COPY rootfs/etc/raddb/mods-available/eap /etc/raddb/mods-available/eap.fallback

# Copy Meraki vendor dictionary for IPSK authentication
COPY rootfs/etc/raddb/dictionary.meraki /etc/raddb/dictionary.meraki

# Copy customized virtual server configs as fallbacks
# These contain our security settings and Cisco-AVPair handling
COPY rootfs/etc/raddb/sites-available/ /etc/raddb/sites-available.fallback/

# Copy run scripts
COPY rootfs/usr/bin/run.sh /usr/bin/run.sh
COPY rootfs/usr/bin/run-standalone.sh /usr/bin/run-standalone.sh
RUN chmod +x /usr/bin/run.sh /usr/bin/run-standalone.sh

# Create necessary directories
RUN mkdir -p \
    /var/log/radius \
    /var/run/radiusd \
    /config/certs \
    /config/clients \
    /tmp/radiusd \
    && chown -R radius:radius /var/log/radius /var/run/radiusd /tmp/radiusd \
    && chmod 700 /tmp/radiusd

# Expose ports
# 1812/udp - RADIUS Authentication
# 1813/udp - RADIUS Accounting
# 2083/tcp - RadSec (RADIUS over TLS)
# 3799/udp - CoA/DM (Change of Authorization)
# 8000/tcp - Configuration API (bound to localhost by default)
EXPOSE 1812/udp 1813/udp 2083/tcp 3799/udp 8000/tcp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD radtest healthcheck healthcheck localhost 1812 testing123 || exit 1

# Run
CMD ["/usr/bin/run.sh"]
