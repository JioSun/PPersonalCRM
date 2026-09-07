from pathlib import Path


def read_template(template_block_path_name: str) -> str:
    p = (Path(__file__)
            .parent
            .joinpath(template_block_path_name)
            .read_text(encoding="utf-8")
        )
    return p


def generate_html(item, template_path: str) -> str:
    rows_html = ""
    rows_html += read_template("item_block_template.txt").format(
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