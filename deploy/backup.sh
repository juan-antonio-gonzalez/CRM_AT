#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CRM-AT — backup de la base de datos y de los archivos subidos.
#
# Uso:
#   bash deploy/backup.sh                 # backup a /var/backups/crm-at
#   bash deploy/backup.sh /otra/ruta      # backup a otra ruta
#
# Pensado para cron diario:
#   15 3 * * * root bash /var/www/crm_at/deploy/backup.sh >/dev/null 2>&1
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_DIR="${1:-/var/backups/crm-at}"
APP_DIR="/var/www/crm_at"
ENV_FILE="/etc/crm-at/crm-at.env"
RETENTION_DAYS=14

[[ -f "$ENV_FILE" ]] || { echo "No existe $ENV_FILE" >&2; exit 1; }

# Leer DATABASE_URL del archivo de entorno sin exponerlo en la línea de comandos.
DATABASE_URL="$(grep -oP '(?<=^DATABASE_URL=).*' "$ENV_FILE" | tr -d '"')"
[[ -n "$DATABASE_URL" ]] || { echo "DATABASE_URL no está definida" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "Respaldando la base de datos..."
pg_dump --no-owner --no-acl --format=custom --file="${BACKUP_DIR}/db-${STAMP}.dump" "$DATABASE_URL"

if [[ -d "${APP_DIR}/static/uploads" ]]; then
  echo "Respaldando archivos subidos..."
  tar -czf "${BACKUP_DIR}/uploads-${STAMP}.tar.gz" -C "${APP_DIR}/static" uploads
fi

echo "Eliminando backups con más de ${RETENTION_DAYS} días..."
find "$BACKUP_DIR" -type f \( -name 'db-*.dump' -o -name 'uploads-*.tar.gz' \) \
  -mtime "+${RETENTION_DAYS}" -delete

echo "Backup completado en ${BACKUP_DIR}"
ls -lh "$BACKUP_DIR" | tail -5

# Restauración (documentada a propósito):
#   pg_restore --clean --no-owner --dbname="$DATABASE_URL" "${BACKUP_DIR}/db-FECHA.dump"
#   tar -xzf "${BACKUP_DIR}/uploads-FECHA.tar.gz" -C "${APP_DIR}/static"
