from pathlib import Path

ITEM_BLOCK_TEMPLATE = """<div class="item-block">
    <div class="item-row"><span class="key">Название</span><span class="value">{name}</span></div>
    <div class="item-row"><span class="key">Имя клиента</span><span class="value">{client_name}</span></div>
    <div class="item-row"><span class="key">Название сделки</span><span class="value">{deal_name}</span></div>
    <div class="item-row"><span class="key">Сумма чека</span><span class="value">{mid_amount}</span></div>
    <div class="item-row"><span class="key">Сумма сделки</span><span class="value">{deal_amount}</span></div>
    <div class="item-row"><span class="key">Дата выплаты</span><span class="value">{due_date}</span></div>
    <div class="item-row"><span class="key">Дедлайн</span><span class="value">{deadline}</span></div>
</div>
"""

def generate_html(item, template_path: str):
    rows_html = ""
    rows_html += ITEM_BLOCK_TEMPLATE.format(
        name=item.label,
        client_name=item.deal.client.username,
        mid_amount=item.mid_amount,
        due_date=item.due_date,
        created_at=item.created_at,
        deal_name=item.deal.name,
        deal_amount=item.deal.amount,
        deadline=item.deal.deadline,
    )

    html = Path(template_path).read_text(encoding="utf-8")
    html = html.replace("{item_blocks}", rows_html)

    return html


if __name__ == "__main__":
    pass