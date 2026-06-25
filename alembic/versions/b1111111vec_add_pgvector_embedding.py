"""enable pgvector and add todos.embedding

Turns Postgres into a vector store: enables the `vector` extension and adds an
`embedding` column to `todos` that holds a 384-dim vector per row. After this,
SQL can rank todos by semantic distance to a query vector.

Revision ID: b1111111vec
Revises: 0e1aa0bb3582
Create Date: 2026-06-25 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'b1111111vec'
down_revision: Union[str, Sequence[str], None] = '0e1aa0bb3582'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector ships its types/operators as a Postgres extension; enable it once.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column('todos', sa.Column('embedding', Vector(EMBEDDING_DIM), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('todos', 'embedding')
    # Leave the extension installed — other objects may rely on it. Drop manually
    # with `DROP EXTENSION vector` if you really want it gone.
