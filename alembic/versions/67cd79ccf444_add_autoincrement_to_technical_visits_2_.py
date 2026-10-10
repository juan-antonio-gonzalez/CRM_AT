"""add_autoincrement_to_technical_visits_2_id

Revision ID: 67cd79ccf444
Revises: a6e7a4e9ac0b
Create Date: 2026-06-10 19:23:37.508078

En SQLite esta migración forzaba la tabla a reconstruirse para convertir ``id``
en AUTOINCREMENT. En PostgreSQL el ``id`` de ``technical_visits_2`` ya es
``SERIAL`` (lo crea la migración anterior con ``sa.Integer`` como clave
primaria), así que la operación no tiene efecto: Alembic sólo advertía
"autoincrement and existing_autoincrement only make sense for MySQL".

Se deja como una migración sin operaciones, explícitamente, en lugar de un
``batch_alter_table`` que ya no aporta nada.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401  (parte del encabezado original)


# revision identifiers, used by Alembic.
revision: str = '67cd79ccf444'
down_revision: Union[str, Sequence[str], None] = 'a6e7a4e9ac0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Sin operaciones: en PostgreSQL ``id`` ya es SERIAL."""
    pass


def downgrade() -> None:
    """Sin operaciones."""
    pass
