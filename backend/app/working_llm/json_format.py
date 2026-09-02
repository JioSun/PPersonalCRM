from google import genai
from google.genai import errors
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.app.core.config import settings
from backend.app.working_llm.llm_classes import ExtractedDealInfo

client = genai.Client(api_key=settings.GEMINI_API_KEY)

SYSTEM_PROMPT = """"""


def is_rate_limit_error(exception):
    return isinstance(exception, errors.APIError) and exception.code in (429, 500, 503)


@retry(
    retry=retry_if_exception(is_rate_limit_error),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
)
async def note_formatter(note_text: str, deal_names: str):
    final_prompt = SYSTEM_PROMPT.format(note_text=note_text, deal_names=deal_names)
    interaction = await client.aio.interactions.create(
        model="gemini-3.6-flash",
        input=final_prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ExtractedDealInfo.model_json_schema(),
        },
    )

    return ExtractedDealInfo.model_validate_json(interaction.output_text)
