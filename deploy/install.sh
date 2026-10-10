#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CRM-AT — instalación / actualización en un VPS Ubuntu con PostgreSQL y Nginx.
#
# Uso:
#   sudo bash deploy/install.sh                 # instala o actualiza
#   sudo bash deploy/install.sh --ssl           # además emite el certificado
#   sudo bash deploy/install.sh --domain otro.dominio
#
# El script es idempotente: se puede volver a ejecutar para actualizar.
# Está pensado para convivir con otras aplicaciones del servidor: usa su propio
# usuario de sistema, su propia base de datos, su propio puerto y su propio
# vhost de Nginx.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_NAME="crm-at"
APP_DIR="/var/www/crm_at"
APP_USER="crmat"
ENV_DIR="/etc/crm-at"
ENV_FILE="${ENV_DIR}/crm-at.env"
DB_NAME="crm_at"
DB_USER="crm_at"
APP_PORT="8020"
DOMAIN="ejemplo.com"
ALT_DOMAIN="www.ejemplo.com"
REPO_URL="https://github.com/juan-antonio-gonzalez/CRM_AT.git"
WANT_SSL=0

# Locate the deployment templates (crm-at.service, nginx-crm-at.conf). The script
# may have been copied elsewhere (e.g. /tmp) before being run as root, so fall
# back to a deploy/ directory next to the current working directory.
_resolve_script_dir() {
  local candidate
  for candidate in \
    "${PWD}/deploy" \
    "${PWD}" \
    "$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" \
    "/var/www/crm_at/deploy"; do
    if [[ -n "$candidate" && -f "${candidate}/crm-at.service" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

if ! SCRIPT_DIR="$(_resolve_script_dir)"; then
  printf '\033[1;31m[x] No se encontró crm-at.service. Ejecutá el script desde el repositorio: sudo bash deploy/install.sh\033[0m\n' >&2
  exit 1
fi
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"

# ── Parseo de argumentos ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssl)    WANT_SSL=1; shift ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    --port)   APP_PORT="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; exit 1 ;;
  esac
done

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m[x] %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Ejecutá este script como root (sudo bash deploy/install.sh)."

# ── 1. Dependencias del sistema ─────────────────────────────────────────────
log "Instalando dependencias del sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# python3-venv / python3-pip: en Ubuntu 26.04 el módulo venv no trae ensurepip.
# build-essential + libjpeg/zlib: Pillow 11.1.0 no publica wheel para Python 3.14
# y se compila desde fuente.
apt-get install -y -qq \
  python3 python3-venv python3-pip python3-dev \
  build-essential zlib1g-dev libjpeg-dev libpq-dev \
  postgresql-client nginx git curl ca-certificates

# ── 2. Usuario de sistema ───────────────────────────────────────────────────
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  log "Creando usuario de sistema ${APP_USER}"
  adduser --system --group --home "$APP_DIR" --no-create-home "$APP_USER"
else
  log "El usuario ${APP_USER} ya existe"
fi

# ── 3. Base de datos ────────────────────────────────────────────────────────
log "Configurando PostgreSQL"
systemctl is-active --quiet postgresql || systemctl start postgresql

DB_PASSWORD=""
if [[ -f "$ENV_FILE" ]]; then
  DB_PASSWORD="$(grep -oP '(?<=^DATABASE_URL=postgresql://'"$DB_USER"':)[^@]+' "$ENV_FILE" || true)"
fi
if [[ -z "$DB_PASSWORD" ]]; then
  DB_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)"
  log "Contraseña de base de datos generada"
fi

su - postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'\"" | grep -q 1 \
  || su - postgres -c "psql -c \"CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';\""

su - postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\"" | grep -q 1 \
  || su - postgres -c "psql -c \"CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};\""

su - postgres -c "psql -c \"ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';\"" >/dev/null
# Permisos sobre el esquema público (PostgreSQL 15+ ya no lo da por defecto).
su - postgres -c "psql -d ${DB_NAME} -c \"GRANT ALL ON SCHEMA public TO ${DB_USER};\"" >/dev/null

# Base aparte para la suite de pruebas. Las pruebas exigen que el nombre termine
# en '_test' antes de borrar tablas, justamente para no tocar datos reales.
TEST_DB_NAME="${DB_NAME}_test"
su - postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${TEST_DB_NAME}'\"" | grep -q 1 \
  || su - postgres -c "psql -c \"CREATE DATABASE ${TEST_DB_NAME} OWNER ${DB_USER};\"" >/dev/null
su - postgres -c "psql -d ${TEST_DB_NAME} -c \"GRANT ALL ON SCHEMA public TO ${DB_USER};\"" >/dev/null

# ── 4. Código ───────────────────────────────────────────────────────────────
# A deployment is "in place" when APP_DIR already holds this application, which
# is true both for a git clone and for an rsync'd copy. Checking only for .git
# made the script try to `git clone` on top of an existing rsync'd directory and
# fail with "destination path already exists and is not an empty directory".
_is_app_dir() {
  [[ -f "${APP_DIR}/main.py" && -f "${APP_DIR}/requirements.txt" ]]
}

if [[ "${SOURCE_DIR}" != "${APP_DIR}" && -d "${SOURCE_DIR}/.git" ]]; then
  log "Copiando el código desde ${SOURCE_DIR}"
  mkdir -p "$APP_DIR"
  # --delete mantiene el destino igual al origen, excluyendo datos locales.
  rsync -a --delete \
    --exclude '.git' --exclude '.venv' --exclude '.venv-work' \
    --exclude '__pycache__' --exclude 'node_modules' \
    --exclude '*.db' --exclude '.env' \
    "${SOURCE_DIR}/" "${APP_DIR}/"
elif _is_app_dir && [[ ! -d "${APP_DIR}/.git" ]]; then
  log "Se usa el código ya presente en ${APP_DIR} (copia sin repositorio git)"
elif [[ ! -d "${APP_DIR}/.git" ]]; then
  log "Clonando ${REPO_URL}"
  git clone --depth 1 "$REPO_URL" "$APP_DIR"
else
  log "Actualizando el repositorio existente"
  git -C "$APP_DIR" fetch --depth 1 origin main
  git -C "$APP_DIR" reset --hard origin/main
fi

mkdir -p "${APP_DIR}/static/uploads" "${APP_DIR}/data" "$ENV_DIR"

# ── 5. Entorno virtual de Python ────────────────────────────────────────────
log "Creando entorno virtual e instalando dependencias de Python"
if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --quiet --upgrade pip wheel
"${APP_DIR}/.venv/bin/pip" install --quiet -r "${APP_DIR}/requirements.txt"

# ── 6. Variables de entorno ─────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  log "Generando ${ENV_FILE}"
  SECRET_KEY="$(openssl rand -base64 64 | tr -d '\n/+=' | cut -c1-64)"
  ADMIN_PW="$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)"
  cat > "$ENV_FILE" <<EOF
APP_NAME="CRM-AT"
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=${SECRET_KEY}
SESSION_EXPIRE_HOURS=24
COOKIE_SECURE=$([[ $WANT_SSL -eq 1 ]] && echo true || echo false)
CSRF_ENABLED=true
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}
HOST=127.0.0.1
PORT=${APP_PORT}
WEB_CONCURRENCY=2
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@${DOMAIN}
ADMIN_PASSWORD=${ADMIN_PW}
SEED_DEMO_DATA=false
UPLOAD_DIR=static/uploads
EOF
  chmod 600 "$ENV_FILE"
  ADMIN_PASSWORD_SHOWN="$ADMIN_PW"
else
  log "Se conserva ${ENV_FILE} existente"
  # Mantener sincronizados puerto y URL de base por si cambiaron los argumentos.
  sed -i "s|^PORT=.*|PORT=${APP_PORT}|" "$ENV_FILE"
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}|" "$ENV_FILE"
fi

chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"
chmod 750 "$APP_DIR" "${APP_DIR}/static/uploads"
chown root:"${APP_USER}" "$ENV_FILE"
chmod 640 "$ENV_FILE"

# Permisos del código. Un `rsync` desde otra máquina puede dejar los archivos en
# modo 600 propiedad del usuario que copió, y entonces el servicio (que corre
# como APP_USER) no puede leerlos: falla con
# "python: can't open file 'run.py': [Errno 13] Permission denied".
# Se normalizan siempre.
chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"
find "$APP_DIR" -type f -name '*.py' -exec chmod 640 {} + 2>/dev/null || true
find "$APP_DIR" -type f \( -name '*.sh' -o -name '*.ini' \) -exec chmod 640 {} + 2>/dev/null || true
find "$APP_DIR" -type d -exec chmod 750 {} + 2>/dev/null || true
chmod 750 "$APP_DIR"

# Nginx corre como www-data y necesita atravesar APP_DIR y leer los estáticos.
if id -u www-data >/dev/null 2>&1; then
  usermod -aG "$APP_USER" www-data || warn "No se pudo agregar www-data al grupo ${APP_USER}"
fi
find "$APP_DIR" -type d -exec chmod o+x {} + 2>/dev/null || true
chmod 755 "$APP_DIR/static" 2>/dev/null || true
find "$APP_DIR/static" -type d -exec chmod o+rx {} + 2>/dev/null || true
find "$APP_DIR/static" -type f -exec chmod o+r {} + 2>/dev/null || true

# ── 7. Migraciones y sembrado ───────────────────────────────────────────────
log "Aplicando migraciones y sembrando datos iniciales"
cd "$APP_DIR"
set -a; # shellcheck disable=SC1090
source "$ENV_FILE"; set +a
sudo -u "$APP_USER" env DATABASE_URL="$DATABASE_URL" ADMIN_USERNAME="${ADMIN_USERNAME:-admin}" \
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-}" ADMIN_EMAIL="${ADMIN_EMAIL:-}" \
  "${APP_DIR}/.venv/bin/python" -m alembic upgrade head

sudo -u "$APP_USER" env DATABASE_URL="$DATABASE_URL" ADMIN_USERNAME="${ADMIN_USERNAME:-admin}" \
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-}" ADMIN_EMAIL="${ADMIN_EMAIL:-}" \
  "${APP_DIR}/.venv/bin/python" main.py seed

# ── 8. Servicio systemd ─────────────────────────────────────────────────────
log "Instalando el servicio systemd"
# La Description del archivo dice "CRM-AT"; hay que reemplazarla sin distinguir
# mayúsculas o la unidad queda con un nombre distinto al del archivo.
sed -e "s|/var/www/crm_at|${APP_DIR}|g" \
    -e "s|/etc/crm-at/crm-at.env|${ENV_FILE}|g" \
    -e "s|^User=crmat|User=${APP_USER}|" \
    -e "s|^Group=crmat|Group=${APP_USER}|" \
    -e "s|Description=CRM-AT|Description=${APP_NAME}|I" \
    -e "s|^SyslogIdentifier=crm-at|SyslogIdentifier=${APP_NAME}|I" \
    "${SCRIPT_DIR}/crm-at.service" > "/etc/systemd/system/${APP_NAME}.service"

systemctl daemon-reload
systemctl enable "${APP_NAME}" >/dev/null
systemctl restart "${APP_NAME}"

sleep 3
if systemctl is-active --quiet "${APP_NAME}"; then
  log "El servicio ${APP_NAME} está activo"
else
  warn "El servicio no arrancó. Últimas líneas del log:"
  journalctl -u "${APP_NAME}" -n 40 --no-pager || true
  die "Revisá el log antes de continuar."
fi

# ── 9. Nginx ────────────────────────────────────────────────────────────────
log "Configurando Nginx"
LE_CERT="/etc/letsencrypt/live/${DOMAIN}"
EXISTING_VHOST="/etc/nginx/sites-available/${APP_NAME}"

if [[ -f "${EXISTING_VHOST}" ]] && grep -q "letsencrypt/live" "${EXISTING_VHOST}"; then
  # A Let's Encrypt certificate is already wired up. Regenerating from the
  # template would silently revert it to the self-signed one, so keep the file
  # and only refresh the port and paths.
  log "Se conserva el vhost existente (ya usa Let's Encrypt)"
  sed -i -e "s|server 127.0.0.1:[0-9]*;|server 127.0.0.1:${APP_PORT};|" \
         -e "s|/var/www/crm_at/static/|${APP_DIR}/static/|g" \
         "$EXISTING_VHOST"
else
  sed -e "s|server 127.0.0.1:8020;|server 127.0.0.1:${APP_PORT};|" \
      -e "s|server_name ejemplo.com www.ejemplo.com 203.0.113.10;|server_name ${DOMAIN} ${ALT_DOMAIN};|" \
      -e "s|/var/www/crm_at/static/|${APP_DIR}/static/|g" \
      "${SCRIPT_DIR}/nginx-crm-at.conf" > "$EXISTING_VHOST"
fi

mkdir -p /var/www/certbot/.well-known/acme-challenge

ln -sf "$EXISTING_VHOST" "/etc/nginx/sites-enabled/${APP_NAME}"

# NOTE: pre-existing sites are deliberately left untouched. This server already
# serves other applications (e.g. otro-sitio.com) and removing the 'default' site
# could change which vhost answers requests with an unknown Host header.

nginx -t || die "La configuración de Nginx es inválida."
systemctl reload nginx

# ── 10. HTTPS ───────────────────────────────────────────────────────────────
# El certificado autofirmado de la plantilla hace que la aplicación sea usable de
# inmediato. Let's Encrypt requiere que el dominio resuelva al servidor; cuando
# eso ocurra, `deploy/enable-ssl.sh` (o --ssl con el DNS ya correcto) lo cambia.
if [[ $WANT_SSL -eq 1 ]]; then
  if getent hosts "$DOMAIN" >/dev/null 2>&1; then
    log "Emitiendo certificado Let's Encrypt para ${DOMAIN}"
    LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-}" \
      bash "${SCRIPT_DIR}/enable-ssl.sh" || warn "No se pudo emitir el certificado."
  else
    warn "El dominio ${DOMAIN} todavía no resuelve a este servidor."
    warn "Se mantiene el certificado provisional autofirmado."
    warn "Cuando corrijas el DNS ejecutá:  sudo LETSENCRYPT_EMAIL=tucorreo bash deploy/enable-ssl.sh"
  fi
fi

# ── Resumen ─────────────────────────────────────────────────────────────────
log "Instalación completa"
cat <<EOF
  Aplicación : ${APP_DIR}
  Servicio   : systemctl status ${APP_NAME}
  Logs       : journalctl -u ${APP_NAME} -f
  Entorno    : ${ENV_FILE}
  Base datos : ${DB_NAME} (usuario ${DB_USER})
  Salud      : curl -s http://127.0.0.1:${APP_PORT}/health

  URL pública: http$([[ $WANT_SSL -eq 1 ]] && echo s)://${DOMAIN}
EOF

if [[ -n "${ADMIN_PASSWORD_SHOWN:-}" ]]; then
  cat <<EOF

  ┌──────────────────────────────────────────────────────────────┐
  │  CREDENCIALES DEL ADMINISTRADOR (anotalas ahora)             │
  ├──────────────────────────────────────────────────────────────┤
  │  Usuario : ${ADMIN_USERNAME:-admin}
  │  Password: ${ADMIN_PASSWORD_SHOWN}
  └──────────────────────────────────────────────────────────────┘
  Cambiala desde /auth/perfil después del primer ingreso.
EOF
else
  echo "  (Las credenciales del administrador ya existían; no se modificaron.)"
fi

if [[ $WANT_SSL -eq 0 ]]; then
  cat <<EOF

  Para habilitar HTTPS:
    sudo LETSENCRYPT_EMAIL=tucorreo@dominio bash deploy/install.sh --ssl
  (requiere que ${DOMAIN} resuelva a la IP de este servidor)
EOF
fi
