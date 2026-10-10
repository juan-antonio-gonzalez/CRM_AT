"""Entrypoint: apply migrations, seed the initial administrator, start uvicorn.

Used by the Docker image and by `deploy/install.sh` on the VPS. Kept separate
from `main.py` so that `uvicorn main:app` can be run without side effects.

Environment variables honoured here:
  PORT            port to bind (default 8000)
  HOST            interface to bind (default 0.0.0.0)
  WEB_CONCURRENCY number of uvicorn workers (default 1)
  SKIP_MIGRATIONS set to "true" to skip `alembic upgrade head`
  SEED_DEMO_DATA  set to "true" to also insert demo records
"""

import os
import sys
import traceback


def run_migrations() -> None:
    if os.environ.get("SKIP_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        print("SKIP_MIGRATIONS activo: no se ejecutan migraciones.")
        return
    print("Aplicando migraciones...")
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig("alembic.ini")
    command.upgrade(cfg, "head")
    print("Migraciones OK")


def seed() -> None:
    print("Sembrando datos iniciales...")
    from main import seed_admin, seed_catalogues, seed_demo_data

    seed_catalogues()
    created = seed_admin()
    if created:
        print("Administrador inicial creado.")
    else:
        print("Ya existen usuarios; no se creó administrador.")
    if os.environ.get("SEED_DEMO_DATA", "").lower() in ("1", "true", "yes"):
        seed_demo_data()
        print("Datos de demostración insertados.")


def main() -> None:
    try:
        run_migrations()
        seed()
    except Exception as exc:  # pragma: no cover - startup path
        traceback.print_exc()
        print(f"FATAL: {exc}", file=sys.stderr)
        sys.exit(1)

    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
    print(f"Iniciando servidor en {host}:{port} ({workers} worker/s)...")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
