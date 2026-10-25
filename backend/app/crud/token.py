from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...app.models.database_models.token import Token


async def create_token(
    invoice_id: str, issue_version: int, session: AsyncSession
) -> Token:
    new_token = Token(
        invoice_id=invoice_id,
        issue_version=issue_version,
    )
    session.add(new_token)

    return new_token


async def get_token_by_invoice_id(
    invoice_id: str, session: AsyncSession
) -> Token | None:
    stmt = select(Token).where(Token.invoice_id == invoice_id)

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_token_by_invoice_id(invoice_id: str, session: AsyncSession) -> bool:
    get_token = await get_token_by_invoice_id(invoice_id, session)

    if get_token is None:
        return False

    await session.delete(get_token)
    return True
