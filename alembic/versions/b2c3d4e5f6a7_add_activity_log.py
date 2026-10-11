"""add activity_log table

Con cinco usuarios trabajando, "¿quién cambió esto?" no tenía respuesta. Esta
revisión agrega la tabla que registra cada alta, edición, baja y reactivación con
su autor, su momento y las diferencias campo por campo.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6

El ``upgrade`` es idempotente: si la tabla ya existe (por ejemplo en una base
creada antes de que existieran las migraciones), no falla.
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _existe(insp, tabla: str) -> bool:
    return tabla in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if _existe(insp, "activity_log"):
        return

    op.create_table(
        "activity_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity_label", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=80), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_activity_log_id", "activity_log", ["id"])
    op.create_index("ix_activity_log_entity", "activity_log",
                    ["entity", "entity_id", "created_at"])
    op.create_index("ix_activity_log_created", "activity_log", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not _existe(insp, "activity_log"):
        return
    op.drop_index("ix_activity_log_created", table_name="activity_log")
    op.drop_index("ix_activity_log_entity", table_name="activity_log")
    op.drop_index("ix_activity_log_id", table_name="activity_log")
    op.drop_table("activity_log")
