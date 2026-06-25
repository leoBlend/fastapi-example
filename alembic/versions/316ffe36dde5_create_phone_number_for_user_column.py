"""Create phone_number for User column

Revision ID: 316ffe36dde5
Revises: a0000000init
Create Date: 2026-06-09 13:54:05.289927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '316ffe36dde5'
down_revision: Union[str, Sequence[str], None] = 'a0000000init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('phone_number', sa.String(), nullable=True))
    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'phone_number')
    pass
