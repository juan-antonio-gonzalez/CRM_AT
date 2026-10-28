# Despliegue en el VPS — CRM-AT

Guía para desplegar esta aplicación en un VPS Ubuntu con **PostgreSQL** y **Nginx**
locales. Está escrita para el servidor `servidor.ejemplo.com` (Hostinger,
Ubuntu 26.04, PostgreSQL 18, Nginx), que además ya sirve otras aplicaciones. El despliegue de CRM-AT es
**completamente independiente**: usa
su propio usuario de sistema, su propia base de datos, su propio puerto y su
propio virtual host, así que no interfiere con lo que ya está corriendo.

---

## 0. Estado actual: desplegado y en producción

La aplicación está corriendo en el VPS con dominio propio y HTTPS válido:

El dominio **no está escrito en el proyecto**: es un dato de cada instalación y se
pasa por variable de entorno (`DOMAIN=... bash deploy/install.sh`).

| Dato | Valor |
|---|---|
| URL | `https://<dominio>` |
| Certificado | Let's Encrypt, renovación automática activa |
| Usuario administrador | `admin` (la contraseña se define en el despliegue) |
| Servicio | `systemctl status CRM-AT` |
| Logs | `journalctl -u CRM-AT -f` |
| Config | `/etc/crm-at/crm-at.env` (modo 640, dueño `root:crmat`) |
| Caty (instructora de uso) | Requiere `DEEPSEEK_API_KEY` en el archivo de config. Sin ella el botón no aparece y la aplicación funciona igual |
| Código | `/var/www/crm_at` |
| Base de datos | PostgreSQL local, base `crm_at`, usuario `crm_at` |
| Puerto interno | `127.0.0.1:8020` |

> Las credenciales **no se guardan en este archivo**. La contraseña del
> administrador está en `/etc/crm-at/crm-at.env` (modo 640, dueño `root:crmat`) y se cambia desde
> `/auth/perfil`. Este documento se versiona en el repositorio.

### Estado de la base de datos

La base de producción está **limpia de datos de negocio**, lista para empezar a
cargar información real:

| Contenido | Estado |
|---|---|
| Clientes, visitas, máquinas, minutas, asignaciones AT | vacíos, con los contadores en 1 |
| Catálogos (sectores, tipos de máquina, tipos de visita) | sembrados |
| Usuarios | 5 |

Los datos de demostración que se usaron durante el desarrollo se eliminaron con
`TRUNCATE ... RESTART IDENTITY CASCADE`, que además reinicia los contadores de id
para que el primer registro real sea el 1. Queda un respaldo previo al borrado en
`/tmp/crm_at_antes_de_limpiar.dump` del servidor.

Para cargar datos de ejemplo en un entorno de desarrollo (nunca en producción):

```bash
python main.py seed --demo
```

### Las otras aplicaciones del VPS

Los otros sitios del servidor **no se tocan**. El vhost de este proyecto es un
sitio aparte; `deploy/install.sh` nunca elimina ni el sitio `default` ni ninguno
de los que ya existan.

---

## 1. Reinstalar o actualizar

El despliegue nativo (PostgreSQL y Nginx del propio servidor) es el que está en
uso. Para actualizar el código:

```bash
# Desde tu máquina
rsync -a --delete --exclude '.git' --exclude '.venv*' --exclude '__pycache__' \
  --exclude 'node_modules' --exclude '*.db' --exclude '.env' --exclude '.DS_Store' \
  --exclude 'static/uploads' --exclude 'data' --exclude 'probe_informe.py' \
  --exclude 'deploy/nginx-crm-at.conf' \
  ~/ruta/al/proyecto/ root@203.0.113.10:/var/www/crm_at/

# Y después, para que los archivos queden del usuario del servicio:
#   ssh root@203.0.113.10 'chown -R crmat:crmat /var/www/crm_at'

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
   contraseña aleatoria. **No toca ninguna otra base del servidor.**
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
curl -I "https://${DOMINIO}"
```

Navegá a `https://<dominio>` e iniciá sesión con el usuario `admin` y la
contraseña que imprimió el instalador.

---

## 4. Operación diaria

| Tarea | Comando |
|---|---|
| Ver logs en vivo | `journalctl -u CRM-AT -f` |
| Reiniciar | `systemctl restart CRM-AT` |
| Detener | `systemctl stop CRM-AT` |
| Estado | `systemctl status CRM-AT` |

> **El nombre de la unidad lleva mayúsculas.** `crm-at` en minúsculas no existe, y
> `systemctl is-active crm-at` no falla: responde `inactive`. Es decir, parece que la
> aplicación está caída justo cuando está corriendo. Los comandos son
> `systemctl <acción> CRM-AT`.
| Revisión de esquema aplicada | `cd /var/www/crm_at && sudo -u crmat .venv/bin/python main.py check-schema` |
| Editar configuración | `sudo nano /etc/crm-at/crm-at.env` y luego `systemctl restart CRM-AT` |

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
  **no** elimina ni el sitio `default` ni ninguno de los que ya existan.
- **Permisos de archivos**: el instalador normaliza **todos** los archivos del
  proyecto, no sólo el código Python. Un `rsync` desde otra máquina conserva el
  modo del archivo de origen, y un editor puede crear un archivo en modo `600`.
  El servicio corre como `crmat`, así que un archivo en `600` cuyo dueño no sea
  `crmat` es ilegible. Ya pasó dos veces, con dos síntomas distintos:

  | Archivo en 600 | Síntoma |
  | --- | --- |
  | `run.py` | El servicio entra en bucle de reinicio: `can't open file 'run.py': [Errno 13] Permission denied` |
  | `templates/_ui.html` | La pantalla devuelve HTTP 500: `PermissionError: [Errno 13] Permission denied: 'templates/_ui.html'` |

  El segundo es más engañoso: sólo falla la pantalla que importa ese componente.
  Por eso la regla es general (`find "$APP_DIR" -type f -exec chmod 640 {} +`) y no
  una lista de extensiones.

  **Ojo con `--delete`.** `rsync` no borra lo que está excluido, así que las exclusiones
de arriba son lo que protege a los archivos que **sólo existen en el servidor**:
`static/uploads` (las fotos que suben los usuarios), `data/` (datos de ejecución),
`probe_informe.py` (el verificador del PDF del informe) y
`deploy/nginx-crm-at.conf`. Sin esas exclusiones, un `--delete` los elimina sin
preguntar. Antes de desplegar conviene mirar qué borraría:

```bash
rsync -a --delete --dry-run --itemize-changes <las mismas exclusiones> \
  ~/ruta/al/proyecto/ root@203.0.113.10:/var/www/crm_at/ | grep deleting
```

**El origen son los permisos locales.** `rsync -a` preserva el modo del archivo de
  origen, y Git **no** versiona permisos más allá del bit de ejecución. Durante el
  desarrollo varios archivos quedaron en `600` en la máquina local —`run.py` y
  `templating.py` entre ellos— y cada `rsync -a` volvía a desplegarlos así. Antes
  de sincronizar conviene normalizarlos:

  ```bash
  find . -type d -not -path './.git/*' -not -path './.venv*' -exec chmod 755 {} +
  find . -type f -not -path './.git/*' -not -path './.venv*' -exec chmod 644 {} +
  find . -type f -name '*.sh' -not -path './.git/*' -exec chmod 755 {} +
  ```

  El instalador del servidor igual los corrige, así que esto es defensa en
  profundidad, no un paso obligatorio.

- **Caché de estáticos**: Nginx sirve `/static` con `Cache-Control: public,
  immutable` y 30 días de vigencia. `immutable` le indica al navegador que **no
  revalide**. Con una URL fija, ningún cambio de CSS o JS llegaba al usuario: el
  servidor tenía todo desplegado y el navegador seguía mostrando la copia vieja
  durante un mes. Por eso los estáticos se piden con `?v=<huella>`
  (`static_url()` en `templating.py`): cada despliegue cambia la dirección. Con las
  URLs versionadas, `immutable` pasa a ser lo correcto, porque un cambio de
  contenido siempre implica una URL distinta.

  Si hacés un cambio y no lo ves, **antes de dudar del código comprobá la URL del
  CSS** en el HTML servido: debe terminar en `?v=...`. Un refresco forzado
  (Cmd+Shift+R) hace falta una sola vez, para que el navegador tome el HTML nuevo.

---

## 7. Integración continua

El workflow vive en `.github/workflows/ci.yml` y **ya está en el repositorio**. Se
ejecuta en cada push a `main`: levanta un PostgreSQL 16, aplica las migraciones y
corre la suite completa.

Si alguna vez hay que volver a subirlo desde cero, el token de GitHub necesita el
permiso `workflow` (GitHub no permite crear ni modificar archivos de Actions sin
él):

```bash
gh auth refresh --scope workflow
git push origin main
```


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

Es casi siempre DNS. Verificá con `dig +short <dominio>` que devuelva
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
