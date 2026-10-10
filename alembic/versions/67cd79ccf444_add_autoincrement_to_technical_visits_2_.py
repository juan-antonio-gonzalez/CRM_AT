"""add_autoincrement_to_technical_visits_2_id

Revision ID: 67cd79ccf444
Revises: a6e7a4e9ac0b
Create Date: 2026-06-10 19:23:37.508078

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67cd79ccf444'
down_revision: Union[str, Sequence[str], None] = 'a6e7a4e9ac0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("technical_visits_2") as batch_op:
        batch_op.alter_column("id", existing_type=sa.Integer(), existing_autoincrement=False, autoincrement=True)


def downgrade() -> None:
    with op.batch_alter_table("technical_visits_2") as batch_op:
        batch_op.alter_column("id", existing_type=sa.Integer(), existing_autoincrement=True, autoincrement=False)
