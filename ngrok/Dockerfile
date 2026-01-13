# Build argument needs to be declared before any FROM statement
ARG BUILD_FROM

# Use official ngrok image to get the latest ngrok binary
FROM ngrok/ngrok:latest AS ngrok-official

# Build the Home Assistant add-on
FROM $BUILD_FROM

# Environment variables
ENV \
    HOME="/root" \
    LANG="C.UTF-8" \
    PS1="$(whoami)@$(hostname):$(pwd)$ " \
    S6_LOGGING=0 \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=0 \
    TERM="xterm-256color"

# Copy ngrok binary from official image
COPY --from=ngrok-official /bin/ngrok /bin/ngrok

# Copy root filesystem
COPY rootfs /

# Verify ngrok installation and set permissions
RUN set -x \
 && echo "Verifying ngrok installation..." \
 && /bin/ngrok version \
 && echo "ngrok installation complete" \
 && chmod 755 /usr/bin/generate-config.sh \
 && chmod 755 /etc/services.d/ngrok/run \
 && chmod 755 /etc/services.d/ngrok/finish

# Build arguments
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION
ARG BUILD_REPOSITORY
# Labels
LABEL \
    io.hass.name="NGROK Image for ${BUILD_ARCH}" \
    io.hass.description="Home Assistant NGROK image for: ${BUILD_ARCH} base image" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="base" \
    io.hass.version=${BUILD_VERSION} \
    io.hass.base.version=${BUILD_VERSION} \
    io.hass.base.name="homeassistant/${BUILD_ARCH}-base:latest" \
    io.hass.base.image="homeassistant/${BUILD_ARCH}-base" \
    maintainer="Josh Lipton <Josh.Lipton@outlook.com>" \
    org.opencontainers.image.title="NGROK Image for ${BUILD_ARCH}" \
    org.opencontainers.image.description="Home Assistant Community Add-on: ${BUILD_ARCH} Base image" \
    org.opencontainers.image.vendor="Josh Lipton" \
    org.opencontainers.image.authors="Josh Lipton <Josh.Lipton@outlook.com>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}
# Initialize ngrok
#CMD ["ngrok --version"]
ENTRYPOINT ["/init"]
