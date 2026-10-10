#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CRM-AT — cambia el certificado autofirmado por uno de Let's Encrypt.
#
# Se ejecuta UNA vez que `ejemplo.com` resuelva a la IP de este servidor:
#     dig +short ejemplo.com     # debe devolver 203.0.113.10
#
# Uso:
#   sudo LETSENCRYPT_EMAIL=tu@correo.com bash deploy/enable-ssl.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="ejemplo.com"
ALT_DOMAIN="www.ejemplo.com"
SERVER_IP="203.0.113.10"
VHOST="/etc/nginx/sites-available/CRM-AT"
ENV_FILE="/etc/crm-at/crm-at.env"
WEBROOT="/var/www/certbot"

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Ejecutá este script como root."

# ── 1. Verificar DNS ────────────────────────────────────────────────────────
log "Verificando que ${DOMAIN} resuelva a ${SERVER_IP}"
RESOLVED="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)"
if [[ "$RESOLVED" != "$SERVER_IP" ]]; then
  die "${DOMAIN} resuelve a '${RESOLVED:-nada}', no a ${SERVER_IP}.
     Corregí el registro A en el panel DNS y esperá la propagación.
     El certificado actual (autofirmado) sigue funcionando mientras tanto."
fi
log "DNS correcto (${RESOLVED})"

# ── 2. Emitir el certificado ────────────────────────────────────────────────
command -v certbot >/dev/null 2>&1 || {
  log "Instalando certbot"
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y -qq certbot
}

mkdir -p "${WEBROOT}/.well-known/acme-challenge"

log "Solicitando el certificado a Let's Encrypt"
CERTBOT_ARGS=(certonly --webroot -w "$WEBROOT" -d "$DOMAIN" -d "$ALT_DOMAIN"
              --non-interactive --agree-tos --keep-until-expiring)
if [[ -n "${LETSENCRYPT_EMAIL:-}" ]]; then
  CERTBOT_ARGS+=(-m "$LETSENCRYPT_EMAIL")
else
  warn "Sin LETSENCRYPT_EMAIL: se registra sin correo de contacto."
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi
certbot "${CERTBOT_ARGS[@]}"

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
[[ -f "${CERT_DIR}/fullchain.pem" ]] || die "No se generó ${CERT_DIR}/fullchain.pem"

# ── 3. Apuntar el vhost al certificado real ─────────────────────────────────
log "Actualizando el vhost para usar el certificado de Let's Encrypt"
cp "$VHOST" "${VHOST}.bak-$(date +%Y%m%d-%H%M%S)"
# Al incluir options-ssl-nginx.conf hay que quitar del vhost las directivas TLS
# que ese archivo ya define (ssl_protocols, ssl_ciphers, ssl_session_*): si se
# repiten, Nginx aborta con "directive is duplicate" y el sitio no recarga.
python3 - "$VHOST" "$CERT_DIR" <<'PYEOF'
import re
import sys

vhost, cert_dir = sys.argv[1], sys.argv[2]
with open(vhost, encoding="utf-8") as fh:
    out = fh.read()

# Apuntar al certificado emitido.
out = re.sub(r"ssl_certificate\s+[^\n;]+;",
             f"ssl_certificate     {cert_dir}/fullchain.pem;", out, count=1)
out = re.sub(r"ssl_certificate_key\s+[^\n;]+;",
             f"ssl_certificate_key {cert_dir}/privkey.pem;", out, count=1)

# Quitar las directivas que el archivo de Certbot redefine.
for pattern in (
    r"^[ \t]*ssl_protocols[^\n]*\n",
    r"^[ \t]*ssl_ciphers[^\n]*\n",
    r"^[ \t]*ssl_session_cache[^\n]*\n",
    r"^[ \t]*ssl_session_timeout[^\n]*\n",
):
    out = re.sub(pattern, "", out, flags=re.MULTILINE)

# Incluir la configuración TLS de Certbot, una sola vez.
if "options-ssl-nginx.conf" not in out:
    anchor = f"ssl_certificate_key {cert_dir}/privkey.pem;"
    out = out.replace(
        anchor,
        anchor
        + "\n    include /etc/letsencrypt/options-ssl-nginx.conf;"
        + "\n    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;",
        1,
    )

with open(vhost, "w", encoding="utf-8") as fh:
    fh.write(out)
PYEOF

if ! nginx -t; then
  cp "$(ls -t "${VHOST}".bak-* | head -1)" "$VHOST"
  die "Configuración inválida; se restauró el respaldo."
fi
systemctl reload nginx

# ── 4. Renovación automática ────────────────────────────────────────────────
log "Habilitando la renovación automática"
systemctl enable --now certbot.timer >/dev/null 2>&1 || warn "No se pudo habilitar certbot.timer"

# ── 5. Asegurar la cookie Secure ────────────────────────────────────────────
if grep -q '^COOKIE_SECURE=' "$ENV_FILE"; then
  sed -i 's|^COOKIE_SECURE=.*|COOKIE_SECURE=true|' "$ENV_FILE"
else
  echo 'COOKIE_SECURE=true' >> "$ENV_FILE"
fi
systemctl restart CRM-AT

# ── 6. Verificación ─────────────────────────────────────────────────────────
sleep 3
log "Verificando"
curl -s -o /dev/null -w "  https://${DOMAIN}/health -> HTTP %{http_code}\n" -m 20 "https://${DOMAIN}/health" || true
echo
echo "  Emisor del certificado:"
echo | openssl s_client -connect "${DOMAIN}:443" -servername "$DOMAIN" 2>/dev/null \
  | openssl x509 -noout -issuer -dates 2>/dev/null | sed 's/^/    /' || true

log "Listo"
echo "  La aplicación queda en: https://${DOMAIN}"
echo "  Renovación: systemctl list-timers certbot.timer"
