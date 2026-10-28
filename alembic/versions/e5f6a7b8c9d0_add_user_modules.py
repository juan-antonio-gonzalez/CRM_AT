"""Módulos visibles por usuario

Agrega `users.modulos`: la lista de claves de módulo que ve cada usuario, según el
catálogo de `services/permisos.py`.

La columna es **nullable a propósito**, y `NULL` no es lo mismo que la lista vacía:

* `NULL` — sin configurar. El usuario ve todos los módulos que no son de
  administración, que es exactamente lo que veía antes de que existieran los
  permisos. Es el estado de todos los usuarios que ya estaban.
* `[]` — configurado sin ningún módulo. No ve nada. Es una decisión explícita.

Si el default hubiera sido `[]`, todos los usuarios existentes habrían amanecido
sin acceso a nada.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotente: se puede volver a correr sobre una base que ya tiene la columna.
    inspector = sa.inspect(op.get_bind())
    columnas = {c["name"] for c in inspector.get_columns("users")}
    if "modulos" not in columnas:
        op.add_column("users", sa.Column("modulos", sa.JSON(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columnas = {c["name"] for c in inspector.get_columns("users")}
    if "modulos" in columnas:
        op.drop_column("users", "modulos")
