"""add invoice issue_version

Revision ID: 76ffe9eb2c67
Revises: ec2cc5f4aa73
Create Date: 2026-10-07 21:02:23.654943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76ffe9eb2c67'
down_revision: Union[str, Sequence[str], None] = 'ec2cc5f4aa73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('invoices', sa.Column('issue_version', sa.BigInteger(), nullable=False, server_default="0"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('invoices', 'issue_version')
