"""add trash_items table

Revision ID: 38c2e1b6f4a9
Revises: 62b8603d3ece
Create Date: 2026-05-27 22:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38c2e1b6f4a9'
down_revision: Union[str, Sequence[str], None] = '62b8603d3ece'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('trash_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('entity_name', sa.String(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('deleted_by_name', sa.String(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('restored_at', sa.DateTime(), nullable=True),
        sa.Column('restored_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trash_items_id', 'trash_items', ['id'])
    op.create_index('ix_trash_items_entity_type', 'trash_items', ['entity_type'])


def downgrade() -> None:
    """Downgrade schema."""
    if _indice_existe('trash_items', 'ix_trash_items_entity_type'):
        op.drop_index('ix_trash_items_entity_type', table_name='trash_items')
    if _indice_existe('trash_items', 'ix_trash_items_id'):
        op.drop_index('ix_trash_items_id', table_name='trash_items')

    op.drop_table('trash_items')


def _tabla_existe(nombre: str) -> bool:
    """Indica si una tabla existe.

    Hace falta en el downgrade: la migración de reconciliación elimina
    ``technical_visits`` (tabla huérfana que ningún modelo usa), así que al
    revertir hay pasos que intentan tocar objetos que ya no están.
    """
    from sqlalchemy import inspect
    return nombre in inspect(op.get_bind()).get_table_names()


def _indice_existe(tabla: str, nombre: str) -> bool:
    """Indica si un índice existe sobre una tabla existente."""
    from sqlalchemy import inspect
    insp = inspect(op.get_bind())
    if tabla not in insp.get_table_names():
        return False
    return nombre in {i["name"] for i in insp.get_indexes(tabla)}
