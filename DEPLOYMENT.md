# Despliegue en el VPS — CRM-AT

Guía para desplegar esta aplicación en un VPS Ubuntu con **PostgreSQL** y **Nginx**
locales. Está escrita para el servidor `servidor.ejemplo.com` (Hostinger,
Ubuntu 26.04, PostgreSQL 18, Nginx), que además ya sirve otra aplicación
(`otro-sitio.com`). El despliegue de CRM-AT es **completamente independiente**: usa
su propio usuario de sistema, su propia base de datos, su propio puerto y su
propio virtual host, así que no interfiere con lo que ya está corriendo.

---

## 0. Estado actual: ya desplegado

La aplicación **está corriendo en el VPS** desde esta sesión:

| Dato | Valor |
|---|---|
| URL | `https://203.0.113.10` (certificado provisional) |
| Usuario | `admin` |
| Contraseña | `FcVMozag3fIvX1tW` — **cambiala en `/auth/perfil`** |
| Servicio | `systemctl status CRM-AT` |
| Logs | `journalctl -u CRM-AT -f` |
| Config | `/etc/crm-at/crm-at.env` |
| Código | `/var/www/crm_at` |
| Base de datos | PostgreSQL local, base `crm_at`, usuario `crm_at` |
| Puerto interno | `127.0.0.1:8020` |

El certificado es **autofirmado**, así que el navegador muestra una advertencia
que hay que aceptar. Se reemplaza por uno de Let's Encrypt en cuanto se corrija
el DNS (sección 1).

### Pendiente único: el registro DNS

`ejemplo.com` sigue apuntando a `2.57.91.91` (parking de Hostinger) en lugar de
al VPS (`203.0.113.10`). La zona DNS **ya está administrada por Hostinger**
(nameservers `nebula.dns-parking.com` / `aurora.dns-parking.com`, TTL de 50 s),
así que es un cambio de un solo registro que propaga en minutos:

1. Panel de Hostinger → Dominios → `ejemplo.com` → **DNS / Nameservers**.
2. En la zona DNS, editá el registro **A** de `@` y poné `203.0.113.10`.
   Hacé lo mismo con el de `www`.
3. Verificá desde tu máquina:

   ```bash
   dig +short ejemplo.com     # debe devolver 203.0.113.10
   ```

4. En cuanto resuelva, cambiá el certificado (un comando):

   ```bash
   ssh root@203.0.113.10
   cd /var/www/crm_at
   sudo LETSENCRYPT_EMAIL=tu@correo.com bash deploy/enable-ssl.sh
   ```

Ese script verifica el DNS antes de tocar nada, emite el certificado con el
método webroot (el desafío ACME ya está funcionando), apunta el vhost al
certificado real, habilita la renovación automática y deja la aplicación en
`https://ejemplo.com` sin advertencias.

---

## 1. Reinstalar o actualizar

El despliegue nativo (PostgreSQL y Nginx del propio servidor) es el que está en
uso. Para actualizar el código:

```bash
# Desde tu máquina
rsync -a --delete --exclude '.git' --exclude '.venv*' --exclude '__pycache__' \
  --exclude 'node_modules' --exclude '*.db' --exclude '.env' \
  ~/ruta/al/proyecto/ root@203.0.113.10:/var/www/crm_at/

# En el servidor
ssh root@203.0.113.10
cd /var/www/crm_at && sudo bash deploy/install.sh
```

El instalador es idempotente: reinstala dependencias si hace falta, aplica
migraciones nuevas, **no** pisa las credenciales existentes y **no** revierte el
certificado si ya está usando Let's Encrypt.

## 2. Detalle de la instalación (un solo comando)

Copiá el proyecto al servidor y ejecutá el instalador. Desde tu máquina:

```bash
# Sincronizar el código (ajustá la ruta local)
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude '.venv-work' \
  --exclude '__pycache__' --exclude 'node_modules' --exclude '*.db' \
  ~/ruta/al/proyecto/ root@203.0.113.10:/var/www/crm_at/

# En el servidor
ssh root@203.0.113.10
cd /var/www/crm_at
sudo bash deploy/install.sh --ssl
```

`install.sh` hace todo esto, de forma idempotente (podés re-ejecutarlo para
actualizar):

1. Instala dependencias del sistema. En Ubuntu 26.04 el módulo `venv` **no trae
   `ensurepip`**, así que instala `python3-venv` y `python3-pip` explícitamente.
   También `build-essential`, `zlib1g-dev` y `libjpeg-dev` porque **Pillow 11.1.0
   no publica wheel para Python 3.14** y se compila desde fuente.
2. Crea el usuario de sistema `crmat` (sin shell ni home real).
3. Crea el rol `crm_at` y la base `crm_at` en el PostgreSQL existente, con una
   contraseña aleatoria. **No toca la base `ejemplo`.**
4. Crea el entorno virtual e instala `requirements.txt`.
5. Genera `/etc/crm-at/crm-at.env` con `SECRET_KEY` aleatoria, la contraseña de
   base de datos y una contraseña inicial de administrador. El archivo queda en
   modo `640` y **fuera del repositorio**.
6. Aplica `alembic upgrade head` y siembra los catálogos y el administrador.
7. Instala y arranca el servicio `crm-at.service` (systemd), en el puerto **8020**.
8. Instala el virtual host de Nginx y, con `--ssl`, emite el certificado.

Al terminar, **el script imprime la contraseña del administrador una sola vez**.
Anotala; después podés cambiarla desde `/auth/perfil`.

---

## 3. Verificación

```bash
# El servicio está activo
systemctl status crm-at

# La sonda de salud responde (sin autenticación)
curl -s http://127.0.0.1:8020/health
# {"status":"ok","database":"ok","revision":"a1b2c3d4e5f6"}

# Nginx está bien configurado
nginx -t

# Desde afuera
curl -I https://ejemplo.com
```

Navegá a `https://ejemplo.com` e iniciá sesión con el usuario `admin` y la
contraseña que imprimió el instalador.

---

## 4. Operación diaria

| Tarea | Comando |
|---|---|
| Ver logs en vivo | `journalctl -u crm-at -f` |
| Reiniciar | `systemctl restart crm-at` |
| Detener | `systemctl stop crm-at` |
| Estado | `systemctl status crm-at` |
| Revisión de esquema aplicada | `cd /var/www/crm_at && sudo -u crmat .venv/bin/python main.py check-schema` |
| Editar configuración | `sudo nano /etc/crm-at/crm-at.env` y luego `systemctl restart crm-at` |

### Actualizar a una versión nueva

```bash
cd /var/www/crm_at
sudo git pull            # o re-sincronizar con rsync
sudo bash deploy/install.sh
```

El instalador vuelve a instalar dependencias, aplica migraciones nuevas y
reinicia el servicio. **No** regenera las credenciales si ya existen.

### Backups

```bash
sudo bash deploy/backup.sh                       # a /var/backups/crm-at
sudo crontab -e                                  # backup diario a las 03:15
# 15 3 * * * root bash /var/www/crm_at/deploy/backup.sh >/dev/null 2>&1
```

Guarda un `pg_dump` comprimido de la base y un tar de `static/uploads`, y
conserva 14 días. Las instrucciones de restauración están al final del script.

---

## 5. Por qué no se usa Docker

El repositorio tuvo un `Dockerfile` y un `docker-compose.yml`, pero ya no están
versionados. El despliegue real usa PostgreSQL y Nginx nativos del servidor, y
mantener dos caminos de despliegue solo agregaba divergencia: el
`docker-compose.yml` levantaba su propio PostgreSQL en un contenedor, distinto
del que realmente se respalda.

Si en algún momento querés dockerizar el proyecto, hay que volver a crear esos
archivos; no están en el repositorio.

---

## 6. Detalles de configuración que conviene conocer

- **`COOKIE_SECURE`**: el instalador la pone en `true` cuando usás `--ssl`. Si
  desplegás sin HTTPS y la dejás en `true`, el navegador **no enviará la cookie de
  sesión** y no vas a poder iniciar sesión. Está documentado en `deploy/env.example`.
- **`WEB_CONCURRENCY`**: por defecto 2 workers de uvicorn. El VPS tiene 4 vCPU y
  15 GB de RAM, así que hay margen para subirlo.
- **Archivos subidos**: viven en `static/uploads/` y Nginx los sirve directamente.
  En el servicio systemd, `ReadWritePaths` incluye ese directorio (con
  `ProtectSystem=full` el resto del árbol es de solo lectura).
- **Migraciones automáticas**: `run.py` ejecuta `alembic upgrade head` en cada
  arranque. Es idempotente. Si alguna vez necesitás arrancar sin migrar, definí
  `SKIP_MIGRATIONS=true`.
- **Nginx no toca las otras aplicaciones**: el instalador agrega un sitio nuevo y
  **no** elimina ni el sitio `default` ni el de `ejemplo`.

---

## 7. Subir el CI a GitHub (requiere un paso manual)

El workflow de CI (`.github/workflows/ci.yml`) **está en tu copia local pero
todavía no se subió**, porque el token de GitHub configurado no tiene el permiso
`workflow` que GitHub exige para crear o modificar archivos de Actions:

```
! [remote rejected] main -> main (refusing to allow an OAuth App to create or
  update workflow `.github/workflows/ci.yml` without `workflow` scope)
```

El token actual tiene los permisos `gist`, `read:org` y `repo`. Para habilitarlo:

```bash
gh auth refresh --hostname github.com --scopes workflow
```

Eso abre el navegador para autorizar el permiso adicional. Después:

```bash
git add .github/workflows/ci.yml
git commit -m "CI: compila plantillas, migra y prueba sobre PostgreSQL"
git push origin main
```

Si preferís no dar ese permiso, podés borrar el archivo; no afecta al
funcionamiento de la aplicación, solo se pierde la verificación automática.

---

## 8. Resolución de problemas

**El servicio no arranca**

```bash
journalctl -u crm-at -n 60 --no-pager
```
Las causas más comunes son `DATABASE_URL` mal formada o permisos sobre
`/etc/crm-at/crm-at.env`.

**Error 502 desde Nginx**

```bash
curl -s http://127.0.0.1:8020/health   # ¿responde la app?
ss -tlnp | grep 8020                   # ¿está escuchando?
```
Si la app responde pero Nginx da 502, revisá que el `proxy_pass` apunte al puerto
correcto y que `SELinux`/AppArmor no esté bloqueando el proxy local.

**No puedo iniciar sesión**

- Verificá que `COOKIE_SECURE` coincida con el esquema real (ver punto 6).
- Comprobá que exista un usuario:
  ```bash
  sudo -u postgres psql -d crm_at -c "SELECT username, role, is_active FROM users;"
  ```
- Si no hay ninguno, creá uno:
  ```bash
  cd /var/www/crm_at
  sudo -u crmat env DATABASE_URL="$(grep -oP '(?<=^DATABASE_URL=).*' /etc/crm-at/crm-at.env)" \
    ADMIN_PASSWORD='UnaClaveSegura' .venv/bin/python main.py create-admin
  ```

**Certbot falla**

Es casi siempre DNS. Verificá con `dig +short ejemplo.com` que devuelva
`203.0.113.10`, esperá la propagación y reintentá:

```bash
sudo LETSENCRYPT_EMAIL=tu@correo.com bash deploy/install.sh --ssl
```

**Quiero volver a la versión anterior**

```bash
cd /var/www/crm_at
sudo git log --oneline -10
sudo git checkout <commit-anterior>
sudo bash deploy/install.sh
```
Las migraciones tienen `downgrade` implementado, pero con datos reales conviene
restaurar un backup en lugar de revertir el esquema.
