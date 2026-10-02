"""corrections

Revision ID: a68052d0957e
Revises: 033acb1b1496
Create Date: 2026-09-30 22:27:22.651934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a68052d0957e'
down_revision: Union[str, Sequence[str], None] = '033acb1b1496'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
