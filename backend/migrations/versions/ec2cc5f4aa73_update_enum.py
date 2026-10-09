"""Update enum

Revision ID: ec2cc5f4aa73
Revises: df23b8c92a36
Create Date: 2026-10-03 19:58:53.890174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ec2cc5f4aa73'
down_revision: Union[str, Sequence[str], None] = 'df23b8c92a36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_STATUSES = ('draft', 'sent', 'paid', 'overdue', 'cancelled')
NEW_STATUSES = ('draft', 'issued', 'paid', 'cancelled')


def replace_status_enum(old_values, new_values) -> None:
    """Replace the type only on an empty invoices table; never discard data."""
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM invoices) THEN
                RAISE EXCEPTION 'Enum replacement requires an empty invoices table';
            END IF;
        END $$;
    """)
    old_enum = postgresql.ENUM(*old_values, name='invoice_status')
    new_enum = postgresql.ENUM(*new_values, name='invoice_status')
    op.alter_column(
        'invoices', 'status', existing_type=old_enum, type_=sa.String(255),
        postgresql_using='status::text', existing_nullable=False,
    )
    old_enum.drop(op.get_bind(), checkfirst=False)
    new_enum.create(op.get_bind(), checkfirst=False)
    op.alter_column(
        'invoices', 'status', existing_type=sa.String(255), type_=new_enum,
        postgresql_using='status::invoice_status', existing_nullable=False,
    )


def upgrade() -> None:
    """Upgrade an empty database to the current status contract."""
    replace_status_enum(OLD_STATUSES, NEW_STATUSES)


def downgrade() -> None:
    """Downgrade schema."""
    replace_status_enum(NEW_STATUSES, OLD_STATUSES)

