import json
import re
from typing import Any

from openai import OpenAI

from .settings import get_settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to your environment or to /Users/abi/Documents/New project/.env."
            )
        client_kwargs: dict[str, str] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        _client = OpenAI(**client_kwargs)
    return _client


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> str:
    settings = get_settings()
    response = _get_client().chat.completions.create(
        model=model or settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    content = response.choices[0].message.content
    return content if content is not None else ""


_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*\r?\n?(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_from_markdown_fences(text: str) -> str:
    """Pull JSON from ``` or ```json fenced blocks; keeps plain text if none match."""
    t = text.strip()
    m = _FENCE_PATTERN.search(t)
    if m:
        return m.group(1).strip()
    return t


def _extract_balanced_json(text: str) -> str | None:
    """If the payload is wrapped in prose, take the first top-level {...} or [...] with string-aware braces."""
    for i, c in enumerate(text):
        if c not in "{[":
            continue
        opener, closer = (c, "}") if c == "{" else (c, "]")
        depth = 0
        in_string = False
        escape = False
        for j in range(i, len(text)):
            ch = text[j]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[i : j + 1]
        break
    return None


def _normalize_for_json_parse(text: str) -> str:
    """Strip BOM, fenced ```json blocks, stray whitespace; then isolate balanced JSON if needed."""
    t = text.strip()
    if t.startswith("\ufeff"):
        t = t[1:].lstrip()
    t = _extract_from_markdown_fences(t)
    t = t.strip()
    try:
        json.loads(t)
    except json.JSONDecodeError:
        candidate = _extract_balanced_json(t)
        if candidate is not None:
            t = candidate
    return t


def safe_parse(text: str) -> Any:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as first_err:
        try:
            return json.loads(_normalize_for_json_parse(text))
        except json.JSONDecodeError as second_err:
            raise ValueError(
                "Failed to parse JSON after two attempts (raw string and normalized). "
                f"First: {first_err}. Second: {second_err}."
            ) from second_err
