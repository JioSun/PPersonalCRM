from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ..app.working_llm import json_format


@pytest.mark.parametrize(
    'deal_names',
    [
        '0: Website redesign\n1: Mobile app\n',
        '',
        '0: Website {draft}\n',
    ],
)
async def test_provider_receives_note_and_deal_list(deal_names, monkeypatch):
    note = 'Обсудили сайт {landing}: стоимость 250 USD, срок 2030-06-01.'
    call = AsyncMock(
        return_value=SimpleNamespace(
            output_text='{"name":"Website","amount":"250.00","matched_index":null}',
        )
    )
    monkeypatch.setattr(
        json_format,
        'client',
        SimpleNamespace(
            aio=SimpleNamespace(interactions=SimpleNamespace(create=call)),
        ),
    )
    result = await json_format.note_formatter(note_text=note, deal_names=deal_names)
    call.assert_awaited_once()
    prompt = call.call_args.kwargs['input']
    assert note in prompt
    if deal_names:
        assert deal_names in prompt
    assert '{note_text}' not in prompt
    assert '{deal_names}' not in prompt
    assert call.call_args.kwargs['response_format']['mime_type'] == 'application/json'
    assert result.name == 'Website'
