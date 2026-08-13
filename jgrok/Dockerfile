ARG BUILD_FROM=ghcr.io/home-assistant/base:3.22
FROM ${BUILD_FROM}

ARG BUILD_ARCH
ARG TARGETARCH
ARG BUILD_VERSION
ARG JGROK_VERSION=0.3.22

SHELL ["/bin/ash", "-o", "pipefail", "-c"]

RUN apk add --no-cache ca-certificates curl \
    && addgroup --system --gid 65532 jgrok \
    && adduser --system --disabled-password --no-create-home \
        --uid 65532 --ingroup jgrok jgrok \
    && release_arch="${BUILD_ARCH:-${TARGETARCH:-}}" \
    && case "${release_arch}" in \
        amd64) \
          artifact_arch="amd64"; \
          artifact_sha256="2bb1fc0ad0ca422b73d41f4277a1d827599f8c075aeb2631a612e82c90b62529" \
          ;; \
        aarch64|arm64) \
          artifact_arch="arm64"; \
          artifact_sha256="a8985001e641dcbc9fdeaa741753e77de7a45b57f1aba586ef2f19bc0ef0ff9c" \
          ;; \
        *) \
          echo "Unsupported build architecture: ${release_arch}" >&2; \
          exit 1 \
          ;; \
      esac \
    && artifact="jgrok-agent-${JGROK_VERSION}-linux-${artifact_arch}.tar.gz" \
    && artifact_url="https://fmultmlsevqgtnqzaylg.supabase.co/storage/v1/object/public/jgrok-agent-releases/releases/linux/${JGROK_VERSION}/${artifact}" \
    && curl --fail --show-error --silent --location \
        --proto '=https' --tlsv1.2 \
        --output "/tmp/${artifact}" "${artifact_url}" \
    && echo "${artifact_sha256}  /tmp/${artifact}" | sha256sum -c - \
    && tar --extract --gzip --file "/tmp/${artifact}" \
        --directory /tmp ./jgrok-agent \
    && install -o root -g root -m 0755 /tmp/jgrok-agent /usr/bin/jgrok-agent \
    && rm "/tmp/${artifact}" /tmp/jgrok-agent

COPY run.sh /usr/bin/run-jgrok
RUN chmod 0755 /usr/bin/run-jgrok

LABEL \
    io.hass.name="JGROK Agent" \
    io.hass.description="Outbound-only JGROK agent for Home Assistant" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.source="https://github.com/liptonj/hassio-addons" \
    org.opencontainers.image.licenses="MIT"

CMD ["/usr/bin/run-jgrok"]
