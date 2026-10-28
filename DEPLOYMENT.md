# Despliegue

Cómo llevar la aplicación a un servidor Ubuntu desde cero, y cómo mantenerla.

Está escrita para que sirva en **cualquier servidor**, no sólo en el que se usa hoy.
Todo lo que depende de la instalación —el dominio, el puerto, las rutas— es un
parámetro; al final hay un apéndice con los datos concretos del despliegue actual.

Para entender el sistema antes de desplegarlo: [docs/arquitectura.md](docs/arquitectura.md).

---

## 1. Lo que hace falta

| | Requisito |
|---|---|
| Servidor | Ubuntu 22.04 o superior, 2 vCPU y 2 GB de RAM como mínimo, con acceso root |
| PostgreSQL | 14 o superior, en el mismo servidor |
| Nginx | como proxy inverso delante de la aplicación |
| Dominio | uno propio, con capacidad de crear registros DNS |
| Correo | una casilla para Let's Encrypt (avisos de vencimiento) |

La aplicación escucha en `127.0.0.1:8020` y **no** se expone directo: Nginx es el
que atiende el 443.

## 2. Antes de tocar el servidor: DNS

El dominio tiene que apuntar a la IP del servidor **antes** de pedir el
certificado.

```bash
dig +short crm.miempresa.com       # tiene que devolver la IP del servidor
```

Si todavía no resuelve, se puede instalar igual y emitir el certificado después
(con `deploy/enable-ssl.sh`), pero el sitio quedará en HTTP mientras tanto.

## 3. La instalación en un comando

El repositorio trae un instalador que hace todo: usuario de sistema, base, código,
entorno virtual, configuración, migraciones, servicio y vhost.

```bash
# En el servidor, como root
git clone https://github.com/juan-antonio-gonzalez/CRM_AT.git /root/CRM_AT
cd /root/CRM_AT
sudo bash deploy/install.sh --domain crm.miempresa.com
```

Y cuando el DNS ya resuelva, el certificado:

```bash
sudo LETSENCRYPT_EMAIL=tu@correo.com bash deploy/install.sh --ssl --domain crm.miempresa.com
```

### Qué hace, en orden

1. Instala dependencias del sistema (Python, PostgreSQL, Nginx, Certbot).
2. Crea el usuario `crmat`, sin shell ni home real.
3. Crea el rol y la base `crm_at` en el PostgreSQL existente, con contraseña
   aleatoria. **No toca otras bases del servidor.**
4. Copia el código a `/var/www/crm_at`.
5. Crea el entorno virtual e instala `requirements.txt`.
6. Genera `/etc/crm-at/crm-at.env` con `SECRET_KEY` y contraseña de administrador
   aleatorias, y **las imprime una sola vez**.
7. Aplica migraciones y siembra catálogos y administrador.
8. Instala y arranca el servicio `CRM-AT`.
9. Configura Nginx. **No elimina** el sitio `default` ni ninguno de los que ya
   existan.

Es **idempotente**: se puede volver a correr para actualizar. No regenera las
credenciales si ya existen.

> **Anotá la contraseña del administrador que imprime el instalador.** No se vuelve
> a mostrar y está hasheada en la base. Si se pierde, se reemplaza con
> `crm-at-clave` (ver §9).

### Opciones

```
bash deploy/install.sh --domain <dominio>    # obligatorio (o DOMAIN=... en el entorno)
bash deploy/install.sh --port <puerto>       # por defecto 8020
bash deploy/install.sh --ssl                 # además emite el certificado
```

## 4. La instalación paso a paso

Si preferís hacerlo a mano, o entender qué hace el instalador.

### 4.1. Dependencias

```bash
apt update
apt install -y python3-venv python3-dev libpq-dev postgresql nginx certbot \
               python3-certbot-nginx rsync
```

### 4.2. Usuario de sistema

```bash
useradd --system --shell /usr/sbin/nologin --home-dir /var/www/crm_at crmat
```

### 4.3. Base de datos

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE crm_at LOGIN PASSWORD 'UNA_CONTRASEÑA_LARGA';
CREATE DATABASE crm_at OWNER crm_at;
SQL
```

### 4.4. Código

```bash
mkdir -p /var/www/crm_at
rsync -rlptD --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
      ./ usuario@servidor:/var/www/crm_at/
```

O `git clone` directo en el servidor. Cualquiera de las dos, después:

```bash
chown -R crmat:crmat /var/www/crm_at
```

### 4.5. Entorno virtual

```bash
cd /var/www/crm_at
sudo -u crmat python3 -m venv .venv
sudo -u crmat .venv/bin/pip install -r requirements.txt
```

### 4.6. Configuración

```bash
mkdir -p /etc/crm-at
cp deploy/env.example /etc/crm-at/crm-at.env
```

Editar `/etc/crm-at/crm-at.env`:

| Variable | Qué poner |
|---|---|
| `SECRET_KEY` | 64 caracteres aleatorios: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `postgresql://crm_at:LA_CONTRASEÑA@127.0.0.1:5432/crm_at` |
| `ADMIN_PASSWORD` | la contraseña inicial del administrador |
| `COOKIE_SECURE` | `true` si vas a servir por HTTPS (**si es `true` sobre HTTP no se puede entrar**) |
| `WEB_CONCURRENCY` | 2 por defecto; subilo si el servidor tiene más núcleos |
| `DEEPSEEK_API_KEY` | opcional; sin ella la asistente aparece apagada y el resto funciona igual |

```bash
chown root:crmat /etc/crm-at/crm-at.env
chmod 640 /etc/crm-at/crm-at.env      # contiene la clave de sesión y la de la base
```

### 4.7. Migraciones y datos iniciales

```bash
cd /var/www/crm_at
set -a; . /etc/crm-at/crm-at.env; set +a
sudo -u crmat .venv/bin/python -m alembic upgrade head
sudo -u crmat .venv/bin/python main.py seed
```

### 4.8. Servicio

```bash
cp deploy/crm-at.service /etc/systemd/system/CRM-AT.service
systemctl daemon-reload
systemctl enable --now CRM-AT
systemctl status CRM-AT
```

> **El nombre de la unidad lleva mayúsculas.** `systemctl is-active crm-at` no
> falla: responde `inactive`. Parece que la aplicación está caída justo cuando está
> corriendo. Los comandos son siempre `systemctl <acción> CRM-AT`.

### 4.9. Nginx

```bash
cp deploy/nginx-crm-at.conf /etc/nginx/sites-available/CRM-AT
sed -i "s|server_name __DOMINIO__ __DOMINIO_ALT__ [0-9.]*;|server_name crm.miempresa.com www.crm.miempresa.com;|" \
    /etc/nginx/sites-available/CRM-AT
ln -sf /etc/nginx/sites-available/CRM-AT /etc/nginx/sites-enabled/CRM-AT
nginx -t && systemctl reload nginx
```

### 4.10. Certificado

```bash
LETSENCRYPT_EMAIL=tu@correo.com DOMAIN=crm.miempresa.com bash deploy/enable-ssl.sh
```

El script comprueba que el dominio resuelva a este servidor, emite el certificado y
verifica el resultado. La renovación la maneja `certbot.timer`, que se instala solo.

## 5. Verificación

```bash
# El servicio
systemctl is-active CRM-AT                 # active

# La aplicación responde, con base y esquema al día
curl -s http://127.0.0.1:8020/health

# Nginx y el certificado
curl -I https://crm.miempresa.com
echo | openssl s_client -connect crm.miempresa.com:443 -servername crm.miempresa.com 2>/dev/null \
  | openssl x509 -noout -dates

# Las páginas públicas
curl -s https://crm.miempresa.com/robots.txt
curl -s https://crm.miempresa.com/sitemap.xml
```

Y en el navegador: `https://crm.miempresa.com` tiene que mostrar la presentación, y
`/auth/login` el formulario.

Si no podés entrar y el login te devuelve al formulario, revisá `COOKIE_SECURE`:
en `true` sobre HTTP, el navegador no manda la cookie.

## 6. Actualizar

```bash
cd /root/CRM_AT && git pull
sudo bash deploy/install.sh --domain crm.miempresa.com
```

El instalador reinstala dependencias, aplica las migraciones nuevas y reinicia. No
regenera credenciales.

Si preferís sincronizar desde tu máquina, **cuidado con `--delete`**:

> `rsync --delete` borra lo que no está en el origen, y hay archivos que **sólo
> existen en el servidor**: `static/uploads/` (las fotos que suben los usuarios),
> `data/` (datos de ejecución) y los scripts de verificación. Excluilos siempre.
> Antes de correrlo, mirá qué borraría con `--dry-run --itemize-changes | grep deleting`.

### Permisos de archivos

`rsync -a` conserva el modo del archivo **de origen**, y Git no versiona permisos
más allá del bit de ejecución. Un archivo en `600` cuyo dueño no sea `crmat` es
ilegible para el servicio, y el síntoma es engañoso:

| Archivo en `600` | Síntoma |
|---|---|
| `run.py` | El servicio entra en bucle: `can't open file 'run.py': [Errno 13] Permission denied` |
| `templates/_ui.html` | Sólo esa pantalla da HTTP 500: `PermissionError: ...` |

Después de cualquier sincronización:

```bash
chown -R crmat:crmat /var/www/crm_at
chmod -R u+rwX,go+rX /var/www/crm_at
```

## 7. Volver atrás

```bash
cd /var/www/crm_at
git log --oneline -5
git checkout <commit-anterior>
sudo bash deploy/install.sh --domain crm.miempresa.com
```

Si la migración nueva ya se aplicó y hay que deshacerla, `alembic downgrade -1`
**antes** de volver al código viejo. Las migraciones de este proyecto son aditivas
en su mayoría, así que el código viejo suele funcionar con el esquema nuevo; aun
así, restaurar el backup es lo seguro.

## 8. Backups

```bash
sudo bash deploy/backup.sh          # a /var/backups/crm-at
```

Guarda un `pg_dump` comprimido de la base y un `tar` de `static/uploads`, y conserva
14 días. Las instrucciones de restauración están al final del script.

Para que corra solo:

```bash
sudo crontab -e
15 3 * * * root bash /var/www/crm_at/deploy/backup.sh >/dev/null 2>&1
```

**Un backup que no se probó restaurar no es un backup.** Conviene hacerlo al menos
una vez en una base descartable.

## 9. Problemas conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| `systemctl is-active crm-at` dice `inactive` pero anda | El nombre real es `CRM-AT` | Usar `CRM-AT` |
| El login vuelve al formulario sin error | `COOKIE_SECURE=true` sobre HTTP | Ponerla en `false` o servir por HTTPS |
| Bucle de reinicio, `Permission denied` en `run.py` | Archivo en modo `600` | `chown -R crmat:crmat` + `chmod -R u+rwX,go+rX` |
| Una pantalla da 500 y el resto anda | Un archivo de `templates/` ilegible | Igual que arriba |
| `502 Bad Gateway` | La aplicación no está corriendo | `systemctl status CRM-AT`, `journalctl -u CRM-AT -n 50` |
| Certbot falla | El dominio no resuelve al servidor | `dig +short <dominio>`, esperar la propagación |
| No se puede entrar después de restaurar | El `.env` cambió de `SECRET_KEY` | Volver a la clave anterior o iniciar sesión de nuevo |
| El sitio carga sin estilos | El CSS no está compilado | `npm run build:css` y volver a desplegar |
| Un ícono se ve como texto | El glifo no está en la fuente | `bash deploy/subset-iconos.sh` |
| Olvidé la contraseña del administrador | bcrypt, irreversible | `crm-at-clave` en el servidor |

### Reemplazar una contraseña

```bash
ssh root@servidor
crm-at-clave                    # pide la contraseña dos veces, de forma interactiva
crm-at-clave otro_usuario       # o para otra cuenta
```

La contraseña no queda en el historial de comandos.

### El dominio está bloqueado en una red corporativa

Es lo más probable si el sitio anda desde el celular y no desde la oficina: los
filtros corporativos bloquean por defecto lo que no conocen, y un dominio nuevo los
gatilla. La aplicación ya trae página de presentación, `robots.txt`, `sitemap.xml` y
datos estructurados para que un revisor lo categorice; aun así, la solución de fondo
es que el área de sistemas lo permita o lo recategorice.

## 10. Detalles que conviene conocer

- **Migraciones automáticas**: `run.py` ejecuta `alembic upgrade head` en cada
  arranque. Es idempotente. Con `SKIP_MIGRATIONS=true` se saltea.
- **`WEB_CONCURRENCY`**: 2 workers por defecto. Cada worker tiene su propio límite
  de tasa del agente en memoria, así que el límite efectivo se multiplica por la
  cantidad de workers.
- **Archivos subidos**: viven en `static/uploads/` y Nginx los sirve directo. En el
  servicio, `ReadWritePaths` incluye ese directorio porque `ProtectSystem=full`
  deja el resto de sólo lectura.
- **Estáticos y caché**: cada archivo se sirve con `?v=<hash>`. Las fuentes llevan
  además la huella de su propio archivo, porque la caché de fuentes va por URL.
- **Nginx no toca otras aplicaciones**: agrega un sitio, no borra ninguno.
- **Logs**: `journalctl -u CRM-AT -f`. Con `LOG_JSON=true` salen en JSON.

---

## Apéndice — El despliegue actual

Datos de la instalación que está en producción hoy, por si hay que operarla.
El dominio y la dirección del servidor no se publican: son datos de la instalación,
no del proyecto.

| | |
|---|---|
| URL | el dominio de la instalación |
| Servidor | un VPS Ubuntu 26.04 con PostgreSQL 18 |
| Aplicación | `/var/www/crm_at`, usuario `crmat` |
| Configuración | `/etc/crm-at/crm-at.env` (modo 640, `root:crmat`) |
| Servicio | `CRM-AT.service`, puerto 8020, 2 workers |
| Vhost | `/etc/nginx/sites-available/CRM-AT` |
| Certificado | Let's Encrypt, renovación automática activa |
| Backups | `deploy/backup.sh` |

### Comandos del día a día

```bash
systemctl status CRM-AT
systemctl restart CRM-AT
journalctl -u CRM-AT -n 100 --no-pager
tail -f /var/log/nginx/access.log
crm-at-clave                       # reemplazar una contraseña
cd /var/www/crm_at && sudo -u crmat .venv/bin/python main.py check-schema
```

### Actualizar

```bash
# Desde la máquina de desarrollo
rsync -rlptD --exclude '.git' --exclude '.venv' --exclude '.venv-work' \
      --exclude '__pycache__' --exclude 'node_modules' --exclude '*.db' \
      --exclude '.env' --exclude '.DS_Store' --exclude '.pytest_cache' \
      --exclude 'static/uploads' ./ usuario@servidor:/var/www/crm_at/

# En el servidor
chown -R crmat:crmat /var/www/crm_at
chmod -R u+rwX,go+rX /var/www/crm_at
systemctl restart CRM-AT
```

### Las otras aplicaciones del servidor

El servidor sirve otros sitios además de éste. **No se tocan**: cada uno tiene su
propio vhost, su propia base y su propio usuario. El instalador tampoco los toca.

### Estado de la base

Al momento de escribir esto la base de producción está **vacía** de datos de
negocio (0 clientes, 0 máquinas, 0 visitas), con los catálogos sembrados y cinco
usuarios. Eso significa que no hay nada que migrar a mano ni respaldos históricos
que recuperar: se puede reinstalar sin pérdida.
