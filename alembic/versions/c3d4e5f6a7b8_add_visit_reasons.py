"""add visit_reasons catalogue

El objetivo de la visita dice *qué tipo* de visita es (programada, seguimiento,
reclamo). Faltaba el *motivo*: por qué se fue esta vez. Va como catálogo para poder
filtrar y agrupar, y para que se mantenga desde Tablas Auxiliares.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "visit_reasons" in insp.get_table_names():
        return

    op.create_table(
        "visit_reasons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("inactivation_reason", sa.Text(), nullable=True),
        sa.Column("inactivated_by_id", sa.Integer(), nullable=True),
        sa.Column("inactivated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_visit_reasons_id", "visit_reasons", ["id"])
    op.create_index("ix_visit_reasons_name", "visit_reasons", ["name"], unique=True)

    # Los cuatro tipos que el formulario de visita tenía escritos a mano y que no
    # estaban en el catálogo. Sólo coincidían en «Seguimiento», así que el catálogo
    # y el formulario ofrecían listas distintas. Se agregan para no perder ninguno
    # ahora que el formulario lee del catálogo.
    existentes = {n for (n,) in bind.execute(sa.text("SELECT name FROM visit_types"))}
    for nombre in ("VISITA PROGRAMADA", "ANÁLISIS NO CONFORMIDAD",
                   "SOLICITUD DEL CLIENTE"):
        if nombre not in existentes:
            bind.execute(
                sa.text("INSERT INTO visit_types (name, is_active) VALUES (:n, true)"),
                {"n": nombre})

    # Los motivos: por qué se fue esta vez, más allá del tipo de visita.
    if bind.execute(sa.text("SELECT count(*) FROM visit_reasons")).scalar() == 0:
        motivos = ("RECORRIDA DE LÍNEA", "RETIRO DE MUESTRA",
                   "REUNIÓN CON PRODUCCIÓN", "REUNIÓN CON CALIDAD",
                   "RECLAMO DE CLIENTE", "PROPUESTA DE MEJORA",
                   "PLAN DE AHORRO", "CAPACITACIÓN", "CORTESÍA")
        for nombre in motivos:
            bind.execute(
                sa.text("INSERT INTO visit_reasons (name, is_active) VALUES (:n, true)"),
                {"n": nombre})


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "visit_reasons" not in insp.get_table_names():
        return
    op.drop_index("ix_visit_reasons_name", table_name="visit_reasons")
    op.drop_index("ix_visit_reasons_id", table_name="visit_reasons")
    op.drop_table("visit_reasons")
