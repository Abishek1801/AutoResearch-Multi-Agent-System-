import json
from typing import TypedDict

from ..settings import get_settings
from ..utils import call_llm, safe_parse

MODEL = get_settings().openai_model

_CONFIDENCE = frozenset({"high", "medium", "low"})

SUMMARIZER_SYSTEM_PROMPT = """You are a fact extractor. Return ONLY valid JSON — a single object, nothing else.

Forbidden: markdown, code fences (```), explanations, commentary, or any text outside the JSON.

Required shape (only top-level key "facts"):
{
  "facts": [
    {"claim": "string", "source_url": "string", "confidence": "high"},
    ...
  ]
}

Grounding (strict):
- Use ONLY the provided snippets. Every claim MUST be directly supported by wording or clear implication in a snippet's "text" (and title if needed for context). Do not use outside knowledge, general knowledge, or filler.
- Never invent facts, numbers, names, dates, or causal claims that do not appear in the snippets.
- If the snippets do not support a claim, do not include it. Prefer omitting over guessing.

When evidence is thin:
- Return fewer facts, or an empty "facts" array, rather than padding with weak or speculative claims.
- Do not fabricate claims to reach a target count.

Counts:
- At most 5 facts. There is no minimum—quality and grounding beat quantity.

Per fact:
- source_url: copy the "url" from the snippet that supports the claim when present; use "" if no matching url.
- confidence: one of "high", "medium", "low" — use "low" when support is partial or narrow.
- Each claim: one short sentence stating only what the snippets support.

Output the JSON object only."""


class Fact(TypedDict):
    claim: str
    source_url: str
    confidence: str


class SummarizerResult(TypedDict):
    facts: list[Fact]


def _allowed_urls_from_snippets(snippets: list[dict]) -> set[str]:
    out: set[str] = set()
    for s in snippets:
        if not isinstance(s, dict):
            continue
        u = s.get("url")
        if isinstance(u, str) and u.strip():
            out.add(u.strip())
    return out


def _normalize_confidence(raw: object) -> str:
    if isinstance(raw, str) and raw.strip().lower() in _CONFIDENCE:
        return raw.strip().lower()
    return "low"


class Summarizer:
    def run(self, sub_question: str, snippets: list[dict]) -> SummarizerResult:
        if not snippets:
            return {"facts": []}

        payload = {
            "sub_question": sub_question.strip(),
            "snippets": snippets,
        }
        user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)
        raw = call_llm(
            system_prompt=SUMMARIZER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL,
        )
        data = safe_parse(raw)
        if not isinstance(data, dict):
            raise ValueError("Summarizer output must be a JSON object.")

        facts = data.get("facts")
        if facts is None:
            facts = []
        if not isinstance(facts, list):
            raise ValueError("facts must be an array.")

        if len(facts) > 5:
            facts = facts[:5]

        allowed_urls = _allowed_urls_from_snippets(snippets)
        out_facts: list[Fact] = []
        for i, item in enumerate(facts):
            if not isinstance(item, dict):
                continue
            claim = item.get("claim")
            source_url = item.get("source_url")
            conf = item.get("confidence")
            if not isinstance(claim, str) or not claim.strip():
                continue
            if not isinstance(source_url, str):
                source_url = ""
            su = source_url.strip()
            if su and allowed_urls and su not in allowed_urls:
                su = ""
            conf_n = _normalize_confidence(conf)
            out_facts.append(
                {
                    "claim": claim.strip(),
                    "source_url": su,
                    "confidence": conf_n,
                }
            )

        if len(out_facts) < 3:
            sq_preview = sub_question.strip()
            if len(sq_preview) > 100:
                sq_preview = sq_preview[:97] + "..."
            print(
                f"[Summarizer] Warning: only {len(out_facts)} fact(s) after parsing "
                f"(expected grounded facts; sub-question: {sq_preview!r})",
                flush=True,
            )

        result: SummarizerResult = {"facts": out_facts}
        return result
