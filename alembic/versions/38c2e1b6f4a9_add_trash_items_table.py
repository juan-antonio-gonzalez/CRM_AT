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
    with op.batch_alter_table('trash_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_trash_items_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_trash_items_entity_type'), ['entity_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('trash_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_trash_items_entity_type'))
        batch_op.drop_index(batch_op.f('ix_trash_items_id'))

    op.drop_table('trash_items')
