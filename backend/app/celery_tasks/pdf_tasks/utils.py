from pathlib import Path

from backend.app.models.database_models import Invoice


def read_template(template_block_path_name: str) -> str:
    p = (
        Path(__file__)
        .parent.joinpath(template_block_path_name)
        .read_text(encoding='utf-8')
    )
    return p


def generate_html(item: Invoice | None, template_path: str) -> str | None:
    rows_html = ''
    if item is None:
        return None

    rows_html += read_template('item_block_template.txt').format(
        name=item.label,
        client_name=item.deal.client.client_name if item.deal is not None else '',
        mid_amount=item.amount,
        due_date=item.due_date,
        created_at=item.created_at,
        deal_name=item.deal.name if item.deal is not None else '',
        deal_amount=item.deal.amount if item.deal is not None else '',
        deadline=item.deal.deadline if item.deal is not None else '',
    )

    html = Path(template_path).read_text(encoding='utf-8')
    html = html.replace('{item_blocks}', rows_html)

    return html
