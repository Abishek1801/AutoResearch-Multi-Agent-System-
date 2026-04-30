import json
from typing import TypedDict

from ..settings import get_settings
from ..utils import call_llm, safe_parse

MODEL = get_settings().openai_model

_CRITIC_KEYS = frozenset({"gaps", "requery_needed", "requery_questions"})

CRITIC_SYSTEM_PROMPT = """You are a coverage critic for a multi-agent research system. You output ONLY a single JSON object and nothing else.

Hard rules:
- Do not use markdown, code fences, or any text before or after the JSON.
- Do not wrap the JSON in ``` or ```json.
- The response must be parseable by json.loads as exactly one object.

Required JSON shape — use ONLY these keys, no others:
{
  "gaps": ["..."],
  "requery_needed": true,
  "requery_questions": ["..."]
}

Field rules:
- gaps: short strings. Include (a) important sub-questions not adequately answered by the facts, (b) any contradictions between facts (say so explicitly, e.g. "Contradiction: ..."), and (c) missing angles. Use [] if there are no gaps or contradictions.
- requery_needed: true ONLY if there is at least one significant gap or contradiction—something that materially hurts coverage, blocks a fair answer to the sub-questions, or requires new evidence to resolve. Do NOT set true for minor wording issues, tiny omissions, or low-impact details. If the only issues are minor, set requery_needed to false and list them in gaps briefly or leave gaps empty.
- requery_questions: at most 2 concrete sub-questions to fetch next when requery_needed is true; MUST be [] when requery_needed is false.

Keep reasoning implicit; output only the JSON object."""


class CriticResult(TypedDict):
    gaps: list[str]
    requery_needed: bool
    requery_questions: list[str]


class Critic:
    def run(self, all_facts: list[dict], sub_questions: list[str]) -> CriticResult:
        payload = {
            "sub_questions": sub_questions,
            "all_facts": all_facts,
        }
        user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)
        raw = call_llm(
            system_prompt=CRITIC_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL,
        )
        data = safe_parse(raw)
        if not isinstance(data, dict):
            raise ValueError("Critic output must be a JSON object.")

        if frozenset(data.keys()) != _CRITIC_KEYS:
            raise ValueError(
                "Critic JSON must contain exactly gaps, requery_needed, requery_questions."
            )

        gaps = data["gaps"]
        requery_needed = data["requery_needed"]
        requery_questions = data["requery_questions"]

        if not isinstance(gaps, list) or not all(isinstance(x, str) for x in gaps):
            raise ValueError("gaps must be an array of strings.")
        if not isinstance(requery_needed, bool):
            raise ValueError("requery_needed must be a boolean.")
        if not isinstance(requery_questions, list) or not all(
            isinstance(x, str) for x in requery_questions
        ):
            raise ValueError("requery_questions must be an array of strings.")

        if not requery_needed and requery_questions:
            raise ValueError(
                "requery_questions must be empty when requery_needed is false."
            )
        if requery_needed and not requery_questions:
            raise ValueError(
                "requery_questions must contain at least one question when requery_needed is true."
            )
        if len(requery_questions) > 2:
            raise ValueError("requery_questions must contain at most 2 items.")

        result: CriticResult = {
            "gaps": [g.strip() for g in gaps if g.strip()],
            "requery_needed": requery_needed,
            "requery_questions": [q.strip() for q in requery_questions if q.strip()],
        }
        if result["requery_needed"] and not result["requery_questions"]:
            raise ValueError(
                "requery_questions must contain at least one non-empty question when requery_needed is true."
            )
        if result["requery_needed"] and not result["gaps"]:
            raise ValueError(
                "requery_needed may be true only when gaps lists at least one significant gap or contradiction."
            )
        return result
