"""Currency added into Deal

Revision ID: 764be5e97582
Revises: 28be7a539b23
Create Date: 2026-08-28 19:33:44.113820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '764be5e97582'
down_revision: Union[str, Sequence[str], None] = '28be7a539b23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
