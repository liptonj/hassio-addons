#!/usr/bin/with-contenv bashio
set -euo pipefail

readonly credential_directory="/data/jgrok"
readonly credential_path="${credential_directory}/credentials.json"
readonly application_id="app.jgrok.docker"
readonly platform="docker"
readonly control_url="https://edge-01.relays.jgrok.app"

if [[ ! -r /data/options.json ]]; then
  bashio::log.fatal "Home Assistant did not provide /data/options.json."
  exit 1
fi

device_name="$(jq --exit-status --raw-output '.device_name | select(type == "string" and length > 0)' /data/options.json)"

if [[ -L "${credential_directory}" ]]; then
  bashio::log.fatal "The persistent credential directory must not be a symbolic link."
  exit 1
fi

install -d -o jgrok -g jgrok -m 0700 "${credential_directory}"

if [[ -L "${credential_path}" ]]; then
  bashio::log.fatal "The persistent credential file must not be a symbolic link."
  exit 1
fi

if [[ -e "${credential_path}" ]]; then
  chown jgrok:jgrok "${credential_path}"
  chmod 0600 "${credential_path}"
fi

credential_is_current() {
  jq --exit-status '
    (.server | type == "string" and startswith("wss://")) and
    (.accessToken | type == "string" and length > 0) and
    (.applicationId == "app.jgrok.docker") and
    (.installationId | type == "string" and length == 36) and
    (
      .accessTokenExpiresAt
      | type == "string"
      and (
        sub("\\.[0-9]+Z$"; "Z")
        | fromdateiso8601 > now
      )
    )
  ' "${credential_path}" >/dev/null 2>&1
}

export JGROK_APPLICATION_ID="${application_id}"
export JGROK_AUTO_UPDATE="false"
export JGROK_CREDENTIALS="${credential_path}"
export JGROK_PLATFORM="${platform}"

if ! credential_is_current; then
  bashio::log.warning "JGROK registration is required."
  bashio::log.warning "Open the URL and approve the five-character code shown below."

  if ! s6-setuidgid jgrok /usr/bin/jgrok-agent register \
    --application-id "${application_id}" \
    --control "${control_url}" \
    --credentials "${credential_path}" \
    --name "${device_name}" \
    --platform "${platform}"; then
    bashio::log.fatal "JGROK registration did not complete. Start the add-on again to retry."
    exit 1
  fi

  if ! credential_is_current; then
    bashio::log.fatal "JGROK registration completed without a valid persistent credential."
    exit 1
  fi

  bashio::log.info "JGROK registration is saved in Home Assistant persistent storage."
else
  bashio::log.info "Using the saved JGROK registration from Home Assistant persistent storage."
fi

bashio::log.info "Starting JGROK agent."
exec s6-setuidgid jgrok /usr/bin/jgrok-agent
