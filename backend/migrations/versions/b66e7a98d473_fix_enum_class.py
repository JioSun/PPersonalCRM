"""Fix enum class

Revision ID: b66e7a98d473
Revises: fe7d411d5229
Create Date: 2026-10-20 14:04:08.726621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b66e7a98d473'
down_revision: Union[str, Sequence[str], None] = 'fe7d411d5229'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
enum_name = 'invoice_status'
table_name = 'invoices'
column_name = 'status'

new_statuses = ('draft', 'issued', 'paid', 'cancelled')
old_statuses = ('draft', 'issued', 'paid', 'cancelled')

new_type = sa.Enum(*new_statuses, name=enum_name)
old_type = sa.Enum(*old_statuses, name=enum_name)


def upgrade() -> None:
    op.execute(f"ALTER TYPE {enum_name} RENAME TO {enum_name}_old")

    new_type.create(op.get_bind(), checkfirst=False)

    op.alter_column(
        table_name,
        column_name,
        type_=new_type,
        existing_type=old_type,
        postgresql_using=f"{column_name}::text::{enum_name}"
    )

    # 5. Удаляем старую версию ENUM из базы
    op.execute(f"DROP TYPE {enum_name}_old")


def downgrade() -> None:
    op.execute(f"ALTER TYPE {enum_name} RENAME TO {enum_name}_old")
    old_type.create(op.get_bind(), checkfirst=False)
    op.alter_column(
        table_name,
        column_name,
        type_=old_type,
        existing_type=new_type,
        postgresql_using=f"{column_name}::text::{enum_name}"
    )
    op.execute(f"DROP TYPE {enum_name}_old")