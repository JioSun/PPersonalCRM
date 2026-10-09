"""Only the guarded, disposable database configured by conftest is used."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from backend.app.core.config import settings


def test_stage_24_downgrade_upgrade(upgrade_migration):
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI.replace('+asyncpg', '+psycopg'))
    config = Config('alembic.ini')
    try:
        command.downgrade(config, '106d358536aa')
        with engine.connect() as conn:
            column = next(c for c in inspect(conn).get_columns('invoices') if c['name'] == 'status')
            assert column['type'].name == 'invoice_status'
            assert column['type'].enums == ['draft', 'sent', 'paid', 'overdue', 'cancelled']
            checks = {c['name']: c['sqltext'] for c in inspect(conn).get_check_constraints('invoices')}
            assert 'ck_invoices_currency' not in checks
            assert 'ck_invoices_label_not_blank' not in checks
            assert '>=' in checks['ck_invoices_amount_positive']
            deal_checks = {c['name'] for c in inspect(conn).get_check_constraints('deals')}
            assert 'ck_deals_currency' not in deal_checks
            assert 'ck_deals_name_not_blank' not in deal_checks
        command.upgrade(config, 'head')
        with engine.connect() as conn:
            column = next(c for c in inspect(conn).get_columns('invoices') if c['name'] == 'status')
            assert column['type'].name == 'invoice_status'
            assert column['type'].enums == ['draft', 'issued', 'paid', 'cancelled']
            checks = {c['name']: c['sqltext'] for c in inspect(conn).get_check_constraints('invoices')}
            assert 'ck_invoices_currency' in checks
            assert 'ck_invoices_label_not_blank' in checks
            assert '>=' not in checks['ck_invoices_amount_positive']
            assert '>' in checks['ck_invoices_amount_positive']
    finally:
        command.upgrade(config, 'head')
        engine.dispose()


def test_upgrade_rejects_incompatible_legacy_data(upgrade_migration):
    engine = create_engine(settings.SQLALCHEMY_DATABASE_URI.replace('+asyncpg', '+psycopg'))
    config = Config('alembic.ini')
    # Transaction-local temporary tables let the actual migration preflight run
    # against incompatible legacy rows without touching any persistent records.
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path('backend/migrations/versions/df23b8c92a36_bug_fix_002.py')
    spec = importlib.util.spec_from_file_location('stage24', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                conn.execute(text('CREATE TEMP TABLE invoices (amount numeric, deal_id text, currency text, label text) ON COMMIT DROP'))
                conn.execute(text('CREATE TEMP TABLE deals (currency text, name text, notes text) ON COMMIT DROP'))
                conn.execute(text("INSERT INTO invoices VALUES (0, 'old-deal', 'USD', 'Legacy invoice')"))
                with Operations.context(MigrationContext.configure(conn)):
                    with pytest.raises(DBAPIError, match='incompatible existing data'):
                        migration.upgrade()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
