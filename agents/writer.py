import json

from utils import call_llm

MODEL = "gpt-4o-mini"

WRITER_SYSTEM_PROMPT = """You are a research report writer. You produce Markdown only—no JSON, no XML, no surrounding commentary before or after the document.

Content rules (strict):
- Use ONLY the facts and scope given in the user message. Do not add facts, statistics, names, dates, or claims that are not clearly supported by the provided facts.
- Do not use outside knowledge to fill gaps. If something is missing, say so briefly in Limitations rather than inventing it.
- Every substantive point in the body should trace to the supplied facts. Paraphrase and organize; do not introduce new information.

Grouping (required):
- Under EACH sub-question section, present ONLY the facts that are relevant to that sub-question. Assign every fact to the single best-matching sub-question section (or the closest one if ambiguous). Do not repeat the same fact verbatim in multiple sections; if a fact fits several, place it once under the best fit.
- Within each sub-question section, use bullet points: one bullet per fact (or one bullet that clearly bundles related facts), with citation for each.

Markdown formatting (required):
- Use a clear heading hierarchy: one `#` title, then `##` for Executive Summary, each sub-question, and Limitations. Optional `###` subheadings inside a section if it improves readability.
- Put a blank line after each heading before body text or lists.
- Use `-` bullet lists for fact groupings; keep bullets parallel and concise.
- No wall-of-text paragraphs in sub-question sections—prefer short bullets; you may add one short intro sentence per section if needed.
- Use consistent spacing (no trailing spaces; single blank line between sections).

Structure (use these headings in order):
1. `#` — report title
2. `## Executive Summary` — short narrative overview; you may use a short bullet list only if it stays within provided facts.
3. For each sub-question in order: `##` + the sub-question text as the section title — body MUST be bullet list(s) of the facts grouped under this question, each with citation.
4. `## Limitations` — include the provided scope and honest limits of the evidence (e.g. source coverage, confidence where relevant) without adding new factual claims. Bullets encouraged.

Citations:
- For each bullet tied to a fact, cite using that fact’s source_url: Markdown links like [source](url) or `Source: <url>`. If source_url is empty, write `Source: not available` and do not invent URLs.

Output: the Markdown document only."""


class Writer:
    def run(
        self,
        sub_questions: list[str],
        facts: list[dict],
        scope: str,
    ) -> str:
        payload = {
            "sub_questions": sub_questions,
            "facts": facts,
            "scope": scope,
        }
        user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)
        raw = call_llm(
            system_prompt=WRITER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=MODEL,
        )
        return raw.strip()
