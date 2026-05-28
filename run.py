"""Startup script: run migrations, seed data, then start uvicorn."""
import sys
import traceback


def main():
    try:
        print("Running DB migrations...")
        from alembic.config import Config as AlembicConfig
        from alembic import command
        alembic_cfg = AlembicConfig("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("Migrations OK")

        print("Seeding initial data...")
        from main import init_db
        init_db()
        print("Seed OK")

    except Exception as e:
        traceback.print_exc()
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)

    import uvicorn
    import os
    port = int(os.environ.get("PORT", "7860"))
    print(f"Starting server on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info", proxy_headers=True, forwarded_allow_ips='*')


if __name__ == "__main__":
    main()
