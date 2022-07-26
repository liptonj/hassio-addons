ARG BUILD_FROM
FROM $BUILD_FROM
# Environment variables
ENV \
    HOME="/root" \
    LANG="C.UTF-8" \
    PS1="$(whoami)@$(hostname):$(pwd)$ " \
    S6_BEHAVIOUR_IF_STAGE2_FAILS=0 \
    TERM="xterm-256color"
# Copy root filesystem
COPY rootfs /
ARG BUILD_ARCH
RUN set -x \
 && apk add --no-cache curl \
 && if [[ "${BUILD_ARCH}" = "aarch64" ]]; then ARCH="arm64"; fi \
 && if [[ "${BUILD_ARCH}" = "amd64" ]]; then ARCH="amd64"; fi \
 && if [[ "${BUILD_ARCH}" = "armhf" ]]; then ARCH="arm"; fi \
 && if [[ "${BUILD_ARCH}" = "armv7" ]]; then ARCH="arm"; fi \
 && if [[ "${BUILD_ARCH}" = "i386" ]]; then ARCH="386"; fi \
 && curl -Lo /ngrok.zip https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-${ARCH}.zip \
 && unzip -o /ngrok.zip -d /bin \
 && rm -f /ngrok.zip
#Permissions Fix
RUN chmod 755 /usr/bin/ngrok.sh \
    && chmod 755 /etc/s6-overlay/s6-rc.d/ngrok/run \
    && chmod 755 /etc/s6-overlay/s6-rc.d/ngrok-log/run

#RUN chown root:root /usr/bin/ngrok.sh
# Entrypoint & CMD



# Build arugments
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
ENTRYPOINT ["/init"]
