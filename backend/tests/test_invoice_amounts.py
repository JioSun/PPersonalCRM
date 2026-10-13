from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.app.crud.invoice import (
    get_invoice_by_engaged_amount,
    get_invoice_by_paid_status,
)
from backend.app.models.constants import InvoiceStatus
from backend.app.models.database_models import Client, Deal, Invoice, User


@pytest.mark.parametrize('calculate, expected_mixed', [
    (get_invoice_by_engaged_amount, Decimal('65.35')),
    (get_invoice_by_paid_status, Decimal('25.15')),
])
@pytest.mark.parametrize('scenario', [
    'mixed', 'empty', 'excluded_statuses', 'other_deal', 'other_user',
])
async def test_deal_invoice_amounts(
        calculate, expected_mixed, scenario, clean_tables, session_pool, monkeypatch):
    async with session_pool() as session:
        async with session.begin():
            owner = User(
                email='amounts@example.com', username='amounts',
                full_name='Amounts User', hashed_password='unused',
            )
            other = User(
                email='other-amounts@example.com', username='other-amounts',
                full_name='Other User', hashed_password='unused',
            )
            session.add_all([owner, other])
            await session.flush()
            customer = Client(client_name='Amounts Client', user_id=owner.id)
            session.add(customer)
            await session.flush()
            deal = Deal(
                name='Target deal', amount=Decimal('200.00'),
                user_id=owner.id, client_id=customer.id,
            )
            other_deal = Deal(
                name='Other deal', amount=Decimal('200.00'),
                user_id=owner.id, client_id=customer.id,
            )
            session.add_all([deal, other_deal])
            await session.flush()

            rows = []
            if scenario in ('mixed', 'other_deal', 'other_user'):
                rows = [
                    (InvoiceStatus.ISSUED, '40.20'),
                    (InvoiceStatus.PAID, '25.15'),
                    (InvoiceStatus.DRAFT, '100.00'),
                    (InvoiceStatus.CANCELLED, '10.00'),
                ]
            elif scenario == 'excluded_statuses':
                rows = [
                    (InvoiceStatus.DRAFT, '100.00'),
                    (InvoiceStatus.CANCELLED, '10.00'),
                ]
            for index, (status, amount) in enumerate(rows):
                session.add(Invoice(
                    label=f'Amount {index}', number=f'AMOUNT-{index}',
                    amount=Decimal(amount), status=status,
                    due_date=date(2000, 1, 1),
                    is_paid=status == InvoiceStatus.PAID,
                    paid_at=(datetime(2000, 1, 1, tzinfo=timezone.utc)
                             if status == InvoiceStatus.PAID else None),
                    issue_version=1 if status != InvoiceStatus.DRAFT else 0,
                    user_id=owner.id, client_id=customer.id,
                    deal_id=other_deal.id if scenario == 'other_deal' else deal.id,
                ))
            deal_id = deal.id
            user_id = other.id if scenario == 'other_user' else owner.id

    async def unexpected_commit(*args, **kwargs):
        pytest.fail('Calculation must not commit the caller transaction')

    async with session_pool() as session:
        monkeypatch.setattr(session, 'commit', unexpected_commit)
        async with session.begin():
            result = await calculate(deal_id=deal_id, user_id=user_id, session=session)
            assert isinstance(result, Decimal)
            assert result == (expected_mixed if scenario == 'mixed' else Decimal('0'))
