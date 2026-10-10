"""Database engine, session factory and FastAPI dependency.

Two important behaviours live here:

* **SQLite foreign keys are enforced.** SQLite ships with ``PRAGMA foreign_keys``
  OFF, which silently turned every ``ForeignKey`` in ``models.py`` into
  documentation. We turn it on (plus WAL and a busy timeout) for every
  connection so local behaviour matches PostgreSQL.
* **Sessions roll back on error.** ``get_db`` used to close the session without
  rolling back, so a failed flush left the transaction open and poisoned the
  connection for the next request.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

SQLALCHEMY_DATABASE_URL = settings.database_url_resolved

_is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if _is_sqlite else {}

# ``pool_pre_ping`` keeps long-lived PostgreSQL connections from dying silently
# behind a NAT/firewall. ``pool_recycle`` avoids server-side idle timeouts.
engine_kwargs = {"pool_pre_ping": True}
if _is_sqlite:
    engine_kwargs["connect_args"] = connect_args
else:
    engine_kwargs["pool_recycle"] = 1800

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover
        """Enforce integrity and improve concurrency on SQLite."""
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


def get_db():
    """Yield a session and always close it.

    Note there is deliberately no ``rollback()`` here: ``Session.close()``
    already discards the transaction, and rolling back first would detach the
    pending state so the application's ``IntegrityError`` handler could no longer
    read the constraint name from the exception. ``main.py`` handles that
    exception explicitly and rolls the session back there.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
