from typing import TypedDict

from utils import call_llm, safe_parse

MODEL = "gpt-4o-mini"

PLANNER_SYSTEM_PROMPT = """You are a research planner for a multi-agent system. You output ONLY a single JSON object and nothing else.

Hard rules:
- Do not use markdown, code fences, bullet lists, or any text before or after the JSON.
- Do not wrap the JSON in ``` or ```json.
- The response must be parseable by json.loads as exactly one object.

Required JSON shape — use ONLY these three keys, no others:
{
  "sub_questions": ["...", "..."],
  "keywords": [["...", "..."], ["...", "..."]],
  "scope": "..."
}

Do not include any other top-level keys (no metadata, no ids, no notes).

Field rules:
- sub_questions: 3 to 5 distinct, concrete sub-questions that together cover the user's topic.
- keywords: MUST be a list of keyword lists with the SAME length as sub_questions. keywords[i] is ONLY for sub_questions[i] (same index). Each inner list has 3–8 short keywords or short phrases.
- scope: one string stating what the research will include, key assumptions, and explicit exclusions or boundaries.

Output the JSON object only."""


class PlannerResult(TypedDict):
    sub_questions: list[str]
    keywords: list[list[str]]
    scope: str


_PLANNER_KEYS = frozenset({"sub_questions", "keywords", "scope"})


class Planner:
    def run(self, question: str) -> PlannerResult:
        raw = call_llm(
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_prompt=question.strip(),
            model=MODEL,
        )
        data = safe_parse(raw)
        if not isinstance(data, dict):
            raise ValueError("Planner output must be a JSON object.")
        keys = frozenset(data.keys())
        if keys != _PLANNER_KEYS:
            extra = sorted(keys - _PLANNER_KEYS)
            missing = sorted(_PLANNER_KEYS - keys)
            parts = []
            if extra:
                parts.append(f"unexpected keys {extra}")
            if missing:
                parts.append(f"missing keys {missing}")
            raise ValueError(
                "Planner JSON must contain exactly sub_questions, keywords, and scope — "
                + "; ".join(parts)
            )

        sub_q = data["sub_questions"]
        kws = data["keywords"]
        scope = data["scope"]

        if not isinstance(sub_q, list) or not isinstance(kws, list) or not isinstance(scope, str):
            raise ValueError("sub_questions and keywords must be arrays; scope must be a string.")
        if not all(isinstance(s, str) for s in sub_q):
            raise ValueError("sub_questions must be a list of strings.")
        if len(sub_q) < 3 or len(sub_q) > 5:
            raise ValueError("sub_questions must contain between 3 and 5 items.")
        if len(kws) != len(sub_q):
            raise ValueError(
                f"keywords must align with sub_questions: got {len(kws)} keyword lists "
                f"for {len(sub_q)} sub_questions (index i of keywords pairs with index i of sub_questions)."
            )
        for i, inner in enumerate(kws):
            if not isinstance(inner, list) or not all(isinstance(x, str) for x in inner):
                raise ValueError(
                    f"keywords[{i}] must be a list of strings (aligned with sub_questions[{i}])."
                )
        out: PlannerResult = {
            "sub_questions": sub_q,
            "keywords": kws,
            "scope": scope,
        }
        return out
