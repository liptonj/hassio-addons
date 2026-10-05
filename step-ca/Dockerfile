ARG BUILD_FROM=docker.io/smallstep/step-ca:0.30.2
FROM ${BUILD_FROM}

ARG BUILD_ARCH
ARG BUILD_VERSION

USER root

RUN apk add --no-cache jq su-exec python3 py3-pip py3-pymysql py3-cryptography py3-aiohttp py3-qrcode py3-pillow

COPY admin/requirements.txt /opt/step-ca-admin/requirements.txt
RUN python3 -m venv --system-site-packages /opt/step-ca-runtime \
    && /opt/step-ca-runtime/bin/pip install --no-cache-dir -r /opt/step-ca-admin/requirements.txt

COPY custom_components/step_ca_scep /opt/step_ca_scep
COPY admin/app.py admin/captive.py admin/db_setup.py admin/enroll.py admin/guidance.py admin/identity_settings.py admin/portal_skin.py admin/ipsk.py admin/meraki_provider.py admin/meraki_settings.py admin/resident_access.py admin/settings_menu.py admin/ui.py /opt/step-ca-admin/
COPY custom_components/step_ca_scep/meraki_ipsk.py /opt/step-ca-admin/meraki_service.py
COPY run.sh /usr/bin/run-step-ca
RUN chmod 0755 /usr/bin/run-step-ca

ENV STEPPATH=/data/step

# The base image's check runs "step ca health" against the first dns_names
# entry, which may be a public name that does not reach port 9000 from inside
# the container; Supervisor then waits in "startup". Check locally instead.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --silent --fail --insecure --max-time 4 https://127.0.0.1:9000/health | grep -q '"ok"'

LABEL \
    io.hass.name="Step CA SCEP Server" \
    io.hass.description="Private certificate authority that issues client certificates over SCEP" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.source="https://github.com/liptonj/hassio-addons" \
    org.opencontainers.image.licenses="MIT"

ENTRYPOINT []
CMD ["/usr/bin/run-step-ca"]
