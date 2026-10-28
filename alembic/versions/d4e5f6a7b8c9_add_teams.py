"""equipos asignados a clientes

Crea la tabla `teams` —comercial, diseñador y AT como una unidad reutilizable— y
las dos columnas que hacen falta para que un equipo se pueda asignar.

Tres cambios:

1. **`teams`**, la tabla nueva. Los tres miembros son `NOT NULL`: un equipo
   incompleto no puede existir. La regla se garantiza en la base y no en el
   formulario, porque una importación o un script no pasan por el formulario.

2. **`customers.team_id`**. Una columna alcanza porque la fila del cliente ya es
   un par cliente-planta: un cliente con tres plantas son tres filas, así que
   cada planta queda con su propio equipo.

   Las columnas `assigned_commercial`, `designer` y `technical_advisor` **no se
   tocan**. Se siguen llenando, ahora desde el equipo, y son las que leen el
   listado, los filtros, los KPIs, los reportes y la importación: 208 usos en
   unos 40 archivos que no hace falta abrir.

3. **`at_assignments.plant`**. Hasta ahora la asignación AT se buscaba sólo por
   nombre de cliente, y con varias plantas eso obligaba a un único AT para
   todas: `Control de Asignación AT` joinea por nombre y después descarta filas
   agrupando por nombre, así que mostraba una sola fila con la planta que ganara
   el desempate. Con un equipo por planta —y su AT— esa situación deja de ser
   representable. Queda nullable para que una asignación vieja sin planta no
   rompa la lectura.

No hay datos que migrar: la base no tiene clientes ni asignaciones reales.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

NOMBRE_FK_CLIENTE = "fk_customers_team_id"


def _columnas(insp, tabla: str) -> set:
    return {c["name"] for c in insp.get_columns(tabla)}


def _indices(insp, tabla: str) -> set:
    return {i["name"] for i in insp.get_indexes(tabla)}


def _nombres_fk(insp, tabla: str) -> set:
    return {fk["name"] for fk in insp.get_foreign_keys(tabla) if fk.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tablas = set(insp.get_table_names())

    # ── 1. teams ────────────────────────────────────────────────────────────
    if "teams" not in tablas:
        op.create_table(
            "teams",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(), nullable=False),
            # NOT NULL: un equipo no puede estar incompleto.
            sa.Column("commercial", sa.String(), nullable=False),
            sa.Column("designer", sa.String(), nullable=False),
            sa.Column("technical_advisor", sa.String(), nullable=False),
            sa.Column("observations", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("inactivation_reason", sa.Text(), nullable=True),
            sa.Column("inactivated_by_id", sa.Integer(), nullable=True),
            sa.Column("inactivated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_teams_id", "teams", ["id"])
        # Único sólo el nombre del equipo. Los miembros no llevan unicidad: una
        # persona puede integrar varios equipos.
        op.create_index("ix_teams_name", "teams", ["name"], unique=True)

    # ── 2. customers.team_id ────────────────────────────────────────────────
    if "team_id" not in _columnas(insp, "customers"):
        op.add_column("customers", sa.Column("team_id", sa.Integer(), nullable=True))
        op.create_index("ix_customers_team_id", "customers", ["team_id"])
        op.create_foreign_key(
            NOMBRE_FK_CLIENTE, "customers", "teams", ["team_id"], ["id"])

    # ── 3. at_assignments.plant ─────────────────────────────────────────────
    if "plant" not in _columnas(insp, "at_assignments"):
        op.add_column("at_assignments", sa.Column("plant", sa.String(), nullable=True))

    if "ix_at_assignments_customer_plant" not in _indices(insp, "at_assignments"):
        op.create_index("ix_at_assignments_customer_plant", "at_assignments",
                        ["customer_name", "plant"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "ix_at_assignments_customer_plant" in _indices(insp, "at_assignments"):
        op.drop_index("ix_at_assignments_customer_plant", table_name="at_assignments")
    if "plant" in _columnas(insp, "at_assignments"):
        op.drop_column("at_assignments", "plant")

    if "customers" in set(insp.get_table_names()):
        if NOMBRE_FK_CLIENTE in _nombres_fk(insp, "customers"):
            op.drop_constraint(NOMBRE_FK_CLIENTE, "customers", type_="foreignkey")
        if "ix_customers_team_id" in _indices(insp, "customers"):
            op.drop_index("ix_customers_team_id", table_name="customers")
        if "team_id" in _columnas(insp, "customers"):
            op.drop_column("customers", "team_id")

    if "teams" in set(insp.get_table_names()):
        op.drop_index("ix_teams_name", table_name="teams")
        op.drop_index("ix_teams_id", table_name="teams")
        op.drop_table("teams")
