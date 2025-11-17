ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install jq for JSON parsing (needed to read Home Assistant config)
# ThousandEyes container is Alpine-based, so use apk
RUN apk add --no-cache jq bash

# Copy startup script that bridges Home Assistant config to ThousandEyes
COPY init.sh /init.sh
RUN chmod +x /init.sh

# Create mount points for ThousandEyes data (matching official Docker command)
# At runtime, we'll bind mount /data subdirectories to these paths
RUN mkdir -p /var/lib/te-agent /var/lib/te-browserbot /var/log/agent

# Working directory
WORKDIR /data

# Build arguments
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION
ARG BUILD_ARCH
ARG BUILD_REPOSITORY

# Labels
LABEL \
    io.hass.name="ThousandEyes Agent Image for ${BUILD_ARCH}" \
    io.hass.description="ThousandEyes Enterprise Agent for: ${BUILD_ARCH}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Josh Lipton <Josh.Lipton@outlook.com>" \
    org.opencontainers.image.title="ThousandEyes Agent for ${BUILD_ARCH}" \
    org.opencontainers.image.description="Home Assistant Add-on: ThousandEyes Enterprise Agent" \
    org.opencontainers.image.vendor="Josh Lipton" \
    org.opencontainers.image.authors="Josh Lipton <Josh.Lipton@outlook.com>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/master/thousandeyes/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

# Use init.sh to read Home Assistant config and start ThousandEyes
# The init.sh script will automatically find and execute the correct ThousandEyes entrypoint
CMD ["/init.sh"]

