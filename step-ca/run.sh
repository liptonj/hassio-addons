#!/bin/bash
set -euo pipefail

readonly options_path="/data/options.json"
readonly step_path="${STEPPATH:-/data/step}"
readonly ca_config="${step_path}/config/ca.json"
readonly ca_password_file="${step_path}/secrets/password"
readonly provisioner_password_file="${step_path}/secrets/provisioner_password"
readonly db_password_file="${step_path}/secrets/db_password"
readonly db_ro_password_file="${step_path}/secrets/db_readonly_password"
readonly templates_dir="${step_path}/templates"
readonly leaf_template="${templates_dir}/scep_leaf.tpl"
readonly leaf_template_data="${templates_dir}/scep_leaf.json"
readonly enroll_template="${templates_dir}/enroll_leaf.tpl"
readonly enroll_dir="${step_path}/enroll"
readonly enroll_password_file="${step_path}/secrets/enrollment_password"
readonly enroll_provisioner="enrollment"
readonly signer_cert="${enroll_dir}/profile_signer.crt"
readonly signer_key="${enroll_dir}/profile_signer.key"
readonly webhook_cert="${enroll_dir}/webhook.crt"
readonly webhook_key="${enroll_dir}/webhook.key"
readonly ca_bundle="${enroll_dir}/ca-bundle.pem"
readonly ssl_dir="/ssl"
readonly ssl_signer_dir="/run/step-ca-signer"
readonly enroll_port=8100
readonly webhook_port=8101
readonly ra_cert="${step_path}/scep/ra.crt"
readonly ra_key="${step_path}/scep/ra.key"
readonly https_address=":9000"
readonly http_address=":9080"
readonly ha_config="/homeassistant"
readonly integration_source="/opt/step_ca_scep"
readonly integration_target="${ha_config}/custom_components/step_ca_scep"
readonly admin_app="/opt/step-ca-admin/app.py"
readonly db_setup="/opt/step-ca-admin/db_setup.py"

log() { printf '[%s] %s: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" "$2"; }
info() { log INFO "$1"; }
warn() { log WARNING "$1"; }
fatal() { log FATAL "$1"; exit 1; }

option() { jq --raw-output "$1" "${options_path}"; }

[[ -r "${options_path}" ]] || fatal "Home Assistant did not provide ${options_path}."
[[ -L "${step_path}" ]] && fatal "${step_path} must not be a symbolic link."

# Supervisor keeps saved options that later versions removed, and shows them
# in the configuration editor. Drop the retired Let's Encrypt (lego) options.
retired='del(.profile_signing.acme_domain, .profile_signing.acme_email,
  .profile_signing.dns_provider, .profile_signing.dns_credentials,
  .profile_signing.acme_staging)'
if [[ -n "${SUPERVISOR_TOKEN:-}" ]] \
  && [[ "$(jq --compact-output "${retired}" "${options_path}")" != "$(jq --compact-output . "${options_path}")" ]]; then
  if jq --compact-output "{options: (${retired})}" "${options_path}" \
    | curl --silent --fail --output /dev/null \
      --header "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
      --header "Content-Type: application/json" \
      --data @- http://supervisor/addons/self/options; then
    info "Removed the retired profile_signing Let's Encrypt options; use the Let's Encrypt add-on instead."
  else
    warn "Could not remove the retired profile_signing Let's Encrypt options; delete them in the add-on configuration."
  fi
fi

ca_name="$(option '.ca_name')"
provisioner_name="$(option '.scep_provisioner_name')"
challenge="$(option '.scep_challenge // ""')"
encryption_algorithm="$(option '.encryption_algorithm')"
min_key_length="$(option '.min_public_key_length')"
include_root="$(option '.include_root')"
force_cn="$(option '.force_cn')"
default_duration="$(option '.default_cert_duration')"
max_duration="$(option '.max_cert_duration')"
install_integration="$(option '.install_integration // true')"
database="$(option '.database // "mariadb"')"
mariadb_database="$(option '.mariadb_database // "stepca"')"
mapfile -t dns_names < <(option '.dns_names[]')
public_url="$(option '.enrollment.public_url // ""')"
# Accept "ha.example.com" and "https://ha.example.com/" as well.
public_url="${public_url%/}"
[[ -z "${public_url}" || "${public_url}" =~ ^https?:// ]] || public_url="https://${public_url}"
link_hours="$(option '.enrollment.link_hours // 24')"
signing_cert_name="$(option '.profile_signing.ssl_certificate // "fullchain.pem"')"
signing_key_name="$(option '.profile_signing.ssl_key // "privkey.pem"')"
wifi_json="$(option '.wifi // {} | {ssid: (.ssid // ""), security: (.security // "WPA2"),
  hidden: (.hidden // false), auto_join: (.auto_join // true),
  radius_server_names: [(.radius_server_names // [])[] | select(. != null and . != "")]}' \
  | jq --compact-output .)"
# Subject attributes (O, OU, L, ST, C) as an x509util subject object; empty
# options are left out.
subject_policy="$(option '.certificate_subject // {}
  | {country, organization, organizationalUnit: .organizational_unit, locality, province: .state}
  | with_entries(select(.value != null and .value != "") | .value = [.value])' | jq --compact-output .)"
subject_display="$(jq --raw-output '[["C", .country], ["ST", .province], ["L", .locality],
  ["O", .organization], ["OU", .organizationalUnit]]
  | map(select(.[1] != null) | "\(.[0])=\(.[1][0])") | join(", ")' <<<"${subject_policy}")"

(( ${#dns_names[@]} > 0 )) || fatal "Configure at least one entry in dns_names."

install -d -m 0700 "${step_path}" "${step_path}/secrets" "${step_path}/scep" "${templates_dir}" \
  "${enroll_dir}"

# Writes {"subject": <subject_policy + commonName>} for use with --set-file, so
# option values are passed as template data and never parsed as templates.
subject_data() {
  jq --null-input --argjson policy "${subject_policy}" --arg cn "$1" \
    '{subject: ($policy + {commonName: $cn})}' > "$2"
}

# Re-signs the root and intermediate created by `step ca init` with the
# configured subject attributes, keeping their keys.
apply_ca_subject() {
  local work defaults tmp
  work="$(mktemp -d)"
  subject_data "${ca_name} Root CA" "${work}/root.json"
  subject_data "${ca_name} Intermediate CA" "${work}/intermediate.json"
  cat > "${work}/root.tpl" <<'EOF'
{
  "subject": {{ toJson .Insecure.User.subject }},
  "issuer": {{ toJson .Insecure.User.subject }},
  "keyUsage": ["certSign", "crlSign"],
  "basicConstraints": {"isCA": true, "maxPathLen": 1}
}
EOF
  cat > "${work}/intermediate.tpl" <<'EOF'
{
  "subject": {{ toJson .Insecure.User.subject }},
  "keyUsage": ["certSign", "crlSign"],
  "basicConstraints": {"isCA": true, "maxPathLen": 0}
}
EOF
  # The keys already exist; /dev/null discards step's copy of them.
  step certificate create "${ca_name} Root CA" "${work}/root.crt" /dev/null \
    --key "${step_path}/secrets/root_ca_key" --password-file "${ca_password_file}" \
    --template "${work}/root.tpl" --set-file "${work}/root.json" \
    --not-after 87600h --no-password --insecure --force >/dev/null 2>&1 || return 1
  step certificate create "${ca_name} Intermediate CA" "${work}/intermediate.crt" /dev/null \
    --key "${step_path}/secrets/intermediate_ca_key" --password-file "${ca_password_file}" \
    --ca "${work}/root.crt" --ca-key "${step_path}/secrets/root_ca_key" \
    --ca-password-file "${ca_password_file}" \
    --template "${work}/intermediate.tpl" --set-file "${work}/intermediate.json" \
    --not-after 87600h --no-password --insecure --force >/dev/null 2>&1 || return 1
  cp "${work}/root.crt" "${step_path}/certs/root_ca.crt"
  cp "${work}/intermediate.crt" "${step_path}/certs/intermediate_ca.crt"
  rm -rf "${work}"
  defaults="${step_path}/config/defaults.json"
  tmp="$(mktemp)"
  jq --arg fp "$(step certificate fingerprint "${step_path}/certs/root_ca.crt")" \
    '.fingerprint = $fp' "${defaults}" > "${tmp}"
  cat "${tmp}" > "${defaults}"
  rm -f "${tmp}"
}

# One-time PKI creation. The root and intermediate keys are generated here and
# never leave /data, which Home Assistant includes in add-on backups.
if [[ ! -f "${ca_config}" ]]; then
  info "No CA found; creating a new root and intermediate CA named '${ca_name}'."
  umask 077
  head -c 48 /dev/urandom | base64 | tr -d '\n' > "${ca_password_file}"
  head -c 48 /dev/urandom | base64 | tr -d '\n' > "${provisioner_password_file}"
  umask 022

  dns_args=()
  for name in "${dns_names[@]}"; do dns_args+=(--dns "${name}"); done

  init_output="$(step ca init \
    --deployment-type standalone \
    --name "${ca_name}" \
    "${dns_args[@]}" \
    --address "${https_address}" \
    --provisioner admin \
    --password-file "${ca_password_file}" \
    --provisioner-password-file "${provisioner_password_file}" 2>&1)" \
    || fatal "Could not create the CA: ${init_output}"
  if [[ "${subject_policy}" != "{}" ]]; then
    apply_ca_subject || fatal "Could not apply certificate_subject to the new CA."
  fi
  info "CA subject: $(step certificate inspect "${step_path}/certs/root_ca.crt" --format json | jq --raw-output '.subject_dn')"
  info "CA created. Root fingerprint: $(step certificate fingerprint "${step_path}/certs/root_ca.crt")"
fi

# SCEP needs an RSA key to decrypt client requests. step-ca's intermediate is
# EC, so a dedicated RSA registration authority (RA) certificate is issued by
# the intermediate and renewed automatically before it expires.
if [[ ! -f "${ra_cert}" || ! -f "${ra_key}" ]] \
  || step certificate needs-renewal "${ra_cert}" --expires-in 720h >/dev/null 2>&1; then
  info "Issuing SCEP RA (decrypter) certificate."
  ra_template="$(mktemp)"
  ra_data="$(mktemp)"
  subject_data "${ca_name} SCEP RA" "${ra_data}"
  cat > "${ra_template}" <<'EOF'
{
  "subject": {{ toJson .Insecure.User.subject }},
  "keyUsage": ["digitalSignature", "keyEncipherment", "dataEncipherment"],
  "basicConstraints": {"isCA": false}
}
EOF
  step certificate create "${ca_name} SCEP RA" "${ra_cert}" "${ra_key}" \
    --template "${ra_template}" --set-file "${ra_data}" \
    --kty RSA --size 2048 \
    --ca "${step_path}/certs/intermediate_ca.crt" \
    --ca-key "${step_path}/secrets/intermediate_ca_key" \
    --ca-password-file "${ca_password_file}" \
    --not-after 43800h \
    --no-password --insecure --force >/dev/null 2>&1 \
    || fatal "Could not issue the SCEP RA certificate."
  rm -f "${ra_template}" "${ra_data}"
  chmod 0600 "${ra_key}"
fi

# Fallback signer for enrollment profiles, used only when no publicly trusted
# certificate is available in /ssl. iOS shows such profiles as "Not Verified".
if [[ ! -f "${signer_cert}" || ! -f "${signer_key}" ]] \
  || step certificate needs-renewal "${signer_cert}" --expires-in 720h >/dev/null 2>&1; then
  info "Issuing the fallback profile signing certificate."
  signer_template="$(mktemp)"
  signer_data="$(mktemp)"
  subject_data "${ca_name} Profile Signing" "${signer_data}"
  cat > "${signer_template}" <<'EOF'
{
  "subject": {{ toJson .Insecure.User.subject }},
  "keyUsage": ["digitalSignature"],
  "basicConstraints": {"isCA": false}
}
EOF
  step certificate create "${ca_name} Profile Signing" "${signer_cert}" "${signer_key}" \
    --template "${signer_template}" --set-file "${signer_data}" \
    --kty RSA --size 2048 \
    --ca "${step_path}/certs/intermediate_ca.crt" \
    --ca-key "${step_path}/secrets/intermediate_ca_key" \
    --ca-password-file "${ca_password_file}" \
    --not-after 17520h \
    --no-password --insecure --force >/dev/null 2>&1 \
    || fatal "Could not issue the profile signing certificate."
  cat "${step_path}/certs/intermediate_ca.crt" >> "${signer_cert}"
  rm -f "${signer_template}" "${signer_data}"
  chmod 0600 "${signer_key}"
fi

# step-ca only calls webhooks over HTTPS. The SCEP challenge webhook listens on
# loopback with a certificate from this CA, and step-ca trusts the system roots
# plus this root for its outbound requests.
if [[ ! -f "${webhook_cert}" || ! -f "${webhook_key}" ]] \
  || step certificate needs-renewal "${webhook_cert}" --expires-in 720h >/dev/null 2>&1; then
  info "Issuing the SCEP challenge webhook certificate."
  step certificate create localhost "${webhook_cert}" "${webhook_key}" \
    --profile leaf --san localhost --san 127.0.0.1 \
    --ca "${step_path}/certs/intermediate_ca.crt" \
    --ca-key "${step_path}/secrets/intermediate_ca_key" \
    --ca-password-file "${ca_password_file}" \
    --not-after 17520h \
    --no-password --insecure --force >/dev/null 2>&1 \
    || fatal "Could not issue the webhook certificate."
  cat "${step_path}/certs/intermediate_ca.crt" >> "${webhook_cert}"
  chmod 0600 "${webhook_key}"
fi
cat /etc/ssl/certs/ca-certificates.crt "${step_path}/certs/root_ca.crt" > "${ca_bundle}" 2>/dev/null \
  || cat "${step_path}/certs/root_ca.crt" > "${ca_bundle}"

# Enrollment profiles are signed with a publicly trusted certificate so iOS
# shows them as "Verified": the one in /ssl written by Home Assistant's
# Let's Encrypt add-on (or e.g. the DuckDNS add-on). The certificate only
# signs profiles; its name does not have to match anything. It is copied for
# the unprivileged management page and re-checked hourly so renewals, or a
# certificate that appears after start, are picked up.
install -d -m 0700 "${ssl_signer_dir}"
chown step:step "${ssl_signer_dir}"
signer_label="${ssl_dir}/${signing_cert_name}"
update_signer() {
  local cert="${ssl_dir}/${signing_cert_name}" key="${ssl_dir}/${signing_key_name}"
  if [[ ! -r "${cert}" || ! -r "${key}" ]]; then
    rm -f "${ssl_signer_dir}/signer.crt" "${ssl_signer_dir}/signer.key"
    return 1
  fi
  if ! cmp -s "${cert}" "${ssl_signer_dir}/signer.crt" || ! cmp -s "${key}" "${ssl_signer_dir}/signer.key"; then
    install -m 0600 -o step -g step "${cert}" "${ssl_signer_dir}/signer.crt"
    install -m 0600 -o step -g step "${key}" "${ssl_signer_dir}/signer.key"
  fi
}
if update_signer; then
  info "Profile signing certificate: ${signer_label}."
else
  warn "${signer_label} not found; enrollment profiles are signed by this CA and iOS shows them as \"Not Verified\". Install and start the Let's Encrypt add-on to get a publicly trusted certificate."
fi
[[ -s "${enroll_password_file}" ]] || (umask 077; head -c 32 /dev/urandom | base64 | tr -d '\n' > "${enroll_password_file}")

# Resolve where step-ca keeps its records of issued and revoked certificates.
# With MariaDB the management page can read them; the embedded database is
# locked by step-ca and only usable by step-ca itself.
db_host="" db_port="" db_ro_user="" db_ro_password=""
if [[ "${database}" == "mariadb" ]]; then
  [[ -n "${SUPERVISOR_TOKEN:-}" ]] || fatal "database is 'mariadb' but the Supervisor API is not available."
  mysql_service=""
  for _ in $(seq 1 30); do
    mysql_service="$(curl --silent --fail \
      --header "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
      http://supervisor/services/mysql 2>/dev/null | jq --compact-output '.data // empty' || true)"
    [[ -n "${mysql_service}" && "${mysql_service}" != "{}" ]] && break
    mysql_service=""
    info "Waiting for the MariaDB add-on to provide its service..."
    sleep 5
  done
  [[ -n "${mysql_service}" ]] \
    || fatal "MariaDB is not available. Install and start the MariaDB add-on, or set database to 'embedded'."
  db_host="$(jq --raw-output '.host' <<<"${mysql_service}")"
  db_port="$(jq --raw-output '.port' <<<"${mysql_service}")"
  db_reachable=false
  for _ in $(seq 1 30); do
    if (exec 3<>"/dev/tcp/${db_host}/${db_port}") 2>/dev/null; then
      db_reachable=true
      break
    fi
    info "Waiting for MariaDB at ${db_host}:${db_port}..."
    sleep 2
  done
  [[ "${db_reachable}" == "true" ]] \
    || fatal "Cannot reach MariaDB at ${db_host}:${db_port}. Make sure the MariaDB add-on is running."

  # step-ca and the management page get their own accounts; the MariaDB
  # service account is only used to create them.
  umask 077
  [[ -s "${db_password_file}" ]] || head -c 32 /dev/urandom | base64 | tr -d '\n/+=' > "${db_password_file}"
  [[ -s "${db_ro_password_file}" ]] || head -c 32 /dev/urandom | base64 | tr -d '\n/+=' > "${db_ro_password_file}"
  umask 022
  db_user="stepca_rw"
  db_password="$(cat "${db_password_file}")"
  db_ro_user="stepca_ro"
  db_ro_password="$(cat "${db_ro_password_file}")"
  (
    ADMIN_HOST="${db_host}" ADMIN_PORT="${db_port}" \
    ADMIN_USER="$(jq --raw-output '.username' <<<"${mysql_service}")" \
    ADMIN_PASSWORD="$(jq --raw-output '.password' <<<"${mysql_service}")" \
    DB_NAME="${mariadb_database}" \
    RW_USER="${db_user}" RW_PASSWORD="${db_password}" \
    RO_USER="${db_ro_user}" RO_PASSWORD="${db_ro_password}" \
    python3 "${db_setup}"
  ) || fatal "Could not create the MariaDB database '${mariadb_database}' and its users."

  db_json="$(jq --null-input --compact-output \
    --arg dsn "${db_user}:${db_password}@tcp(${db_host}:${db_port})/" \
    --arg name "${mariadb_database}" \
    '{type: "mysql", dataSource: $dsn, database: $name}')"
  info "Using MariaDB database '${mariadb_database}' on ${db_host}:${db_port}."
else
  db_json="$(jq --null-input --compact-output --arg path "${step_path}/db" \
    '{type: "badgerv2", dataSource: $path, badgerFileLoadingMode: ""}')"
  info "Using the embedded database; the management page cannot list certificates."
fi

# Reconcile ca.json with the add-on options on every start so edits in the
# Home Assistant UI take effect after a restart.
# localhost is always included so the management page can reach the API.
dns_json="$(printf '%s\n' "${dns_names[@]}" localhost | jq --raw-input . | jq --slurp 'unique')"
tmp_config="$(mktemp)"
jq --argjson dns "${dns_json}" \
  --arg address "${https_address}" \
  --arg insecure "${http_address}" \
  --argjson db "${db_json}" \
  --arg enroll "${enroll_provisioner}" \
  '.dnsNames = $dns
   | .address = $address
   | .insecureAddress = $insecure
   | .db = $db
   | .crl = {enabled: true, generateOnRevoke: true, cacheDuration: "24h0m0s"}
   | .authority.provisioners |= map(select(.type != "SCEP" and .name != $enroll))' \
  "${ca_config}" > "${tmp_config}"
cat "${tmp_config}" > "${ca_config}"
rm -f "${tmp_config}"
chmod 0600 "${ca_config}"

scep_args=(
  --type SCEP
  --ca-config "${ca_config}"
  --encryption-algorithm-identifier "${encryption_algorithm}"
  --min-public-key-length "${min_key_length}"
  --scep-decrypter-certificate-file "${ra_cert}"
  --scep-decrypter-key-file "${ra_key}"
  --x509-default-dur "${default_duration}"
  --x509-max-dur "${max_duration}"
)
[[ -n "${challenge}" ]] && scep_args+=(--challenge "${challenge}")

# With certificate_subject set, issued certificates get the configured
# attributes; the Common Name, SANs, and any attribute left empty come from
# the client's request. Otherwise step-ca's default SCEP template is used.
if [[ "${subject_policy}" != "{}" ]]; then
  cat > "${leaf_template}" <<'EOF'
{
  "subject": {
    "commonName": {{ toJson .Subject.CommonName }},
    "country": {{ toJson (default .Subject.Country .subjectPolicy.country) }},
    "organization": {{ toJson (default .Subject.Organization .subjectPolicy.organization) }},
    "organizationalUnit": {{ toJson (default .Subject.OrganizationalUnit .subjectPolicy.organizationalUnit) }},
    "locality": {{ toJson (default .Subject.Locality .subjectPolicy.locality) }},
    "province": {{ toJson (default .Subject.Province .subjectPolicy.province) }},
    "streetAddress": {{ toJson .Subject.StreetAddress }},
    "postalCode": {{ toJson .Subject.PostalCode }},
    "serialNumber": {{ toJson .Subject.SerialNumber }}
  },
  "sans": {{ toJson .SANs }},
{{- if typeIs "*rsa.PublicKey" .Insecure.CR.PublicKey }}
  "keyUsage": ["keyEncipherment", "digitalSignature"],
{{- else }}
  "keyUsage": ["digitalSignature"],
{{- end }}
  "extKeyUsage": ["serverAuth", "clientAuth"]
}
EOF
  jq --null-input --argjson policy "${subject_policy}" '{subjectPolicy: $policy}' > "${leaf_template_data}"
  scep_args+=(--x509-template "${leaf_template}" --x509-template-data "${leaf_template_data}")
fi
[[ "${include_root}" == "true" ]] && scep_args+=(--include-root)
[[ "${force_cn}" == "true" ]] && scep_args+=(--force-cn)

provisioner_output="$(step ca provisioner add "${provisioner_name}" "${scep_args[@]}" 2>&1)" \
  || fatal "Could not configure the SCEP provisioner: $(grep -v 'CA Configuration' <<<"${provisioner_output}" | tail -n 3 | tr '\n' ' ')"

# The management page decides which SCEP challenges are accepted: the static
# scep_challenge and one-time challenges from enrollment profiles. With a
# SCEPCHALLENGE webhook step-ca no longer checks the static challenge itself.
# The webhook listens on loopback only.
tmp_config="$(mktemp)"
jq --arg name "${provisioner_name}" --arg url "https://127.0.0.1:${webhook_port}/scep-challenge" \
  '.authority.provisioners |= map(if .type == "SCEP" and .name == $name then
     .options.webhooks = [{id: "enrollment", name: "enrollment", url: $url,
       kind: "SCEPCHALLENGE", certType: "X509"}] else . end)' \
  "${ca_config}" > "${tmp_config}"
cat "${tmp_config}" > "${ca_config}"
rm -f "${tmp_config}"

# Provisioner used by the management page to issue .p12 bundles for devices
# without SCEP. Recreated on each start with a fresh key.
cat > "${enroll_template}" <<'EOF'
{
  "subject": {
    "commonName": {{ toJson .Subject.CommonName }},
    "country": {{ toJson (default .Subject.Country .subjectPolicy.country) }},
    "organization": {{ toJson (default .Subject.Organization .subjectPolicy.organization) }},
    "organizationalUnit": {{ toJson (default .Subject.OrganizationalUnit .subjectPolicy.organizationalUnit) }},
    "locality": {{ toJson (default .Subject.Locality .subjectPolicy.locality) }},
    "province": {{ toJson (default .Subject.Province .subjectPolicy.province) }}
  },
{{- if typeIs "*rsa.PublicKey" .Insecure.CR.PublicKey }}
  "keyUsage": ["keyEncipherment", "digitalSignature"],
{{- else }}
  "keyUsage": ["digitalSignature"],
{{- end }}
  "extKeyUsage": ["serverAuth", "clientAuth"]
}
EOF
jq --null-input --argjson policy "${subject_policy}" '{subjectPolicy: $policy}' > "${leaf_template_data}"
step ca provisioner add "${enroll_provisioner}" --type JWK --create \
  --ca-config "${ca_config}" --password-file "${enroll_password_file}" \
  --x509-template "${enroll_template}" --x509-template-data "${leaf_template_data}" \
  --x509-default-dur "${default_duration}" --x509-max-dur "${max_duration}" >/dev/null 2>&1 \
  || fatal "Could not configure the enrollment provisioner."

if [[ -z "${challenge}" ]]; then
  warn "scep_challenge is empty: any client that can reach the SCEP URL can obtain a certificate."
fi

chown -R step:step "${step_path}"

# Install or update the companion integration that serves SCEP on Home
# Assistant's own port. Home Assistant must restart to load a new version.
if [[ "${install_integration}" == "true" ]]; then
  if [[ -d "${ha_config}" ]]; then
    installed_version="$(jq --raw-output '.version // ""' \
      "${integration_target}/manifest.json" 2>/dev/null || true)"
    bundled_version="$(jq --raw-output '.version' "${integration_source}/manifest.json")"
    if [[ "${installed_version}" != "${bundled_version}" ]]; then
      install -d "${ha_config}/custom_components"
      rm -rf "${integration_target}"
      cp -R "${integration_source}" "${integration_target}"
      warn "Installed the Step CA SCEP integration ${bundled_version}. Restart Home Assistant to load it."
    fi
  else
    warn "Home Assistant configuration is not mapped; skipping integration install."
  fi
fi

# Tell Home Assistant where to forward SCEP traffic. Supervisor keeps the
# message and replays it when Home Assistant (re)starts.
if [[ -n "${SUPERVISOR_TOKEN:-}" ]]; then
  addon_host="$(curl --silent --fail \
    --header "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
    http://supervisor/addons/self/info | jq --raw-output '.data.hostname')"
  discovery="$(jq --null-input \
    --arg host "${addon_host}" \
    --arg root "$(cat "${step_path}/certs/root_ca.crt")" \
    --argjson enroll_port "${enroll_port}" \
    '{service: "step_ca_scep", config: {host: $host, port: 9080, enroll_port: $enroll_port, root_pem: $root}}')"
  if curl --silent --fail --output /dev/null \
    --header "Authorization: Bearer ${SUPERVISOR_TOKEN}" \
    --header "Content-Type: application/json" \
    --data "${discovery}" http://supervisor/discovery; then
    info "Announced SCEP endpoint ${addon_host}:9080 to Home Assistant."
  else
    warn "Supervisor discovery failed; add the Step CA SCEP integration manually."
  fi
fi

info "SCEP URL:         <your Home Assistant URL>/api/step_ca_scep/scep/${provisioner_name}"
info "Root CA download: <your Home Assistant URL>/api/step_ca_scep/roots.pem"
info "CRL download:     <your Home Assistant URL>/api/step_ca_scep/crl"
info "Starting step-ca and the management page."

SSL_CERT_FILE="${ca_bundle}" su-exec step:step step-ca --password-file "${ca_password_file}" "${ca_config}" &
ca_pid=$!

(
  export STEPPATH="${step_path}" SCEP_PROVISIONER="${provisioner_name}"
  export DB_HOST="${db_host}" DB_PORT="${db_port}" DB_USER="${db_ro_user}"
  export DB_PASSWORD="${db_ro_password}" DB_NAME="${mariadb_database}"
  export SUBJECT_POLICY="${subject_display}" CA_NAME="${ca_name}"
  export SCEP_CHALLENGE="${challenge}" WIFI_JSON="${wifi_json}"
  export ENROLL_PUBLIC_URL="${public_url}" ENROLL_LINK_HOURS="${link_hours}"
  export ENROLL_PORT="${enroll_port}" WEBHOOK_PORT="${webhook_port}"
  export WEBHOOK_CERT="${webhook_cert}" WEBHOOK_KEY="${webhook_key}"
  export PROFILE_SSL_CERT="${ssl_signer_dir}/signer.crt" PROFILE_SSL_KEY="${ssl_signer_dir}/signer.key"
  export PROFILE_SSL_LABEL="${signer_label}"
  export PROFILE_CA_CERT="${signer_cert}" PROFILE_CA_KEY="${signer_key}"
  exec su-exec step:step python3 "${admin_app}"
) &
admin_pid=$!

# Pick up renewals of the profile signing certificate.
(
  while sleep 3600; do update_signer || true; done
) &
refresh_pid=$!

# Stop both processes together; if either exits, the add-on exits and
# Supervisor reports it.
stopping=false
trap 'stopping=true; kill -TERM "${ca_pid}" "${admin_pid}" "${refresh_pid}" 2>/dev/null || true' TERM INT
set +e
wait -n "${ca_pid}" "${admin_pid}"
status=$?
kill -TERM "${ca_pid}" "${admin_pid}" "${refresh_pid}" 2>/dev/null
wait
[[ "${stopping}" == "true" ]] && exit 0
exit "${status}"
