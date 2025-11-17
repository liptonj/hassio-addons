ARG BUILD_FROM
FROM thousandeyes/enterprise-agent:latest

# Install bash and required tools for Home Assistant integration
RUN apt-get update && apt-get install -y \
    bash \
    jq \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install bashio for Home Assistant add-on support
RUN curl -J -L -o /tmp/bashio.tar.gz \
    "https://github.com/hassio-addons/bashio/archive/v0.16.2.tar.gz" \
    && mkdir /tmp/bashio \
    && tar zxvf /tmp/bashio.tar.gz --strip 1 -C /tmp/bashio \
    && mv /tmp/bashio/lib /usr/lib/bashio \
    && ln -s /usr/lib/bashio/bashio /usr/bin/bashio \
    && rm -rf /tmp/bashio.tar.gz /tmp/bashio

# Copy our startup script
COPY run.sh /usr/local/bin/run.sh
RUN chmod a+x /usr/local/bin/run.sh

# Set working directory
WORKDIR /data

LABEL \
io.hass.name="ThousandEyes Agent Image for ${BUILD_ARCH}" \
io.hass.description="ThousandEyes Agent image for: ${BUILD_ARCH} base image" \
io.hass.arch="${BUILD_ARCH}" \
io.hass.type="base" \
io.hass.version=${BUILD_VERSION} \
io.hass.base.version=${BUILD_VERSION} \
io.hass.base.name="homeassistant/${BUILD_ARCH}-base:latest" \
io.hass.base.image="homeassistant/${BUILD_ARCH}-base" 

CMD ["/usr/local/bin/run.sh"]

