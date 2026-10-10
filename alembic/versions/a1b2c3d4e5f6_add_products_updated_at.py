"""add products.updated_at and backfill from last_modified

``products.last_modified`` was free text written in three incompatible formats
("Hace 2 días", "Hoy", "%Y-%m-%d %H:%M") and was silently stale after every
edit, so it could not be sorted or compared. It is replaced by a real
``updated_at`` timestamp; this revision adds the column and backfills it from
whatever legacy value can be parsed.

Revision ID: a1b2c3d4e5f6
Revises: 9f1c2d3e4a5b
"""

import datetime

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "9f1c2d3e4a5b"
branch_labels = None
depends_on = None


def _column_names(insp, table: str) -> set:
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "products" not in insp.get_table_names():
        return

    if "updated_at" not in _column_names(insp, "products"):
        op.add_column("products", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Backfill: parse the legacy free-text value when it is a real timestamp.
    rows = bind.execute(
        sa.text("SELECT id, last_modified FROM products WHERE updated_at IS NULL")
    ).fetchall()

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    for row_id, legacy in rows:
        parsed = None
        if isinstance(legacy, str) and legacy.strip():
            candidate = legacy.strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    parsed = datetime.datetime.strptime(candidate, fmt)
                    break
                except ValueError:
                    continue
        bind.execute(
            sa.text("UPDATE products SET updated_at = :ts WHERE id = :id"),
            {"ts": parsed or now, "id": row_id},
        )

    # Give every remaining row a value so callers can rely on it being present.
    bind.execute(
        sa.text("UPDATE products SET updated_at = :ts WHERE updated_at IS NULL"),
        {"ts": now},
    )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "products" in insp.get_table_names() and "updated_at" in _column_names(insp, "products"):
        op.drop_column("products", "updated_at")
