import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import TypedDict

# https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy
_USER_AGENT = "MultiAgentResearch/1.0 (educational; Python urllib)"

_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Stop words / question glue — removed so remaining tokens skew toward main topic & noun phrases.
_STOP_WORDS = frozenset(
    """
    a an the and or but if in on at to for of as is are was were be been being
    has have had do does did doing done will would could should may might must shall can
    what which who whom whose where when why how this that these those it its
    we you they he she i me my your our their his her them then than so not no
    there here with from by about into through during before after above below
    between under again further once both each few more most other some such only
    own same than too very just also any both
    get gets got make made use uses using take takes taking give gives given
    does did doing include includes including define defines defined defining
    regarding concerning pertaining especially particularly generally typically usually
    main primarily various different many much some any
    """.split()
)

# Standalone technical / topic tokens to try as Wikipedia titles (original casing optional).
_KNOWN_TOPIC_TOKENS = frozenset(
    "mrna trna dna rna ai ml nlp api gpt llm cpu gpu".split()
)

_MIN_EXTRACT_LEN = 50


class Snippet(TypedDict):
    text: str
    url: str
    title: str


class RetrieverResult(TypedDict):
    snippets: list[Snippet]


def _as_json_result(result: RetrieverResult) -> RetrieverResult:
    return json.loads(json.dumps(result, ensure_ascii=False))


def _empty_result() -> RetrieverResult:
    return {"snippets": []}


def _snippet(*, text: str, url: str, title: str) -> Snippet:
    return {"text": text, "url": url, "title": title}


def _desktop_url(data: dict) -> str:
    url = ""
    urls = data.get("content_urls")
    if isinstance(urls, dict):
        desktop = urls.get("desktop")
        if isinstance(desktop, dict):
            page = desktop.get("page")
            if isinstance(page, str):
                url = page.strip()
    return url


def _clean_text(raw: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    s = raw.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return " ".join(s.split())


def _to_underscore(phrase: str) -> str:
    return phrase.replace(" ", "_").strip("_")


def _content_words(sq: str) -> list[str]:
    """Tokens with stopwords removed — main topical words for the sub-question."""
    return [w for w in _clean_text(sq).split() if w not in _STOP_WORDS and len(w) > 1]


def _topic_token_queries_from_raw(raw: str) -> list[str]:
    """Likely noun phrases from original casing: Title Case runs, agentic AI, mRNA, …"""
    out: list[str] = []
    text = raw.strip()
    # "Agentic AI", "MRNA Vaccine" style
    for m in re.finditer(r"\b(?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+)+\b", text):
        q = _to_underscore(_clean_text(m.group(0)))
        if q:
            out.append(q)
    # "agentic AI" style (lowercase + capitalized head)
    for m in re.finditer(r"\b[a-z][a-z0-9]*\s+[A-Z][a-z]+\b", text):
        q = _to_underscore(_clean_text(m.group(0)))
        if q:
            out.append(q)
    low = text.lower()
    for tok in _KNOWN_TOPIC_TOKENS:
        if re.search(r"\b" + re.escape(tok) + r"\b", low):
            out.append(tok)
    return out


def _query_main_topic(sq: str) -> str | None:
    """All content words joined — primary topic string."""
    words = _content_words(sq)
    if not words:
        return None
    return _to_underscore(" ".join(words))


def _query_content_bigrams(sq: str) -> list[str]:
    """Consecutive content-word pairs (noun-phrase style), end of question first."""
    words = _content_words(sq)
    if len(words) < 2:
        return []
    pairs = [_to_underscore(f"{words[i]} {words[i + 1]}") for i in range(len(words) - 1)]
    return list(reversed(pairs))


def _query_from_sub_question_full(sq: str) -> str:
    """Full sub_question: cleaned, spaces → underscores."""
    return _to_underscore(_clean_text(sq))


def _query_last_content_terms(sq: str, n: int) -> str | None:
    """Last n content words (often the head noun phrase)."""
    words = _content_words(sq)
    if len(words) < n:
        return None
    return _to_underscore(" ".join(words[-n:]))


def _query_from_top_keywords(keywords: list[str], k: int = 2) -> str | None:
    """Join first k planner keywords: each cleaned, spaces→underscores, then segments joined."""
    segs: list[str] = []
    for x in keywords[:k]:
        if not (x and x.strip()):
            continue
        c = _to_underscore(_clean_text(x))
        if c:
            segs.append(c)
    if not segs:
        return None
    return "_".join(segs)


def _is_valid_extract(data: dict) -> bool:
    if "extract" not in data:
        return False
    ex = data.get("extract")
    if not isinstance(ex, str):
        return False
    return len(ex.strip()) > _MIN_EXTRACT_LEN


def _fetch_summary(title_query: str) -> dict | None:
    if not title_query:
        return None
    try:
        encoded = urllib.parse.quote(title_query, safe="")
        url = _SUMMARY_URL.format(title=encoded)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None


def _snippet_from_extract(data: dict) -> Snippet | None:
    if not isinstance(data, dict) or not _is_valid_extract(data):
        return None
    title = data.get("title")
    if not isinstance(title, str):
        title = ""
    title = title.strip()
    ex = data["extract"].strip()
    return _snippet(text=ex, url=_desktop_url(data), title=title)


def _build_query_attempts(sub_question: str, keywords: list[str]) -> list[str]:
    """Prefer main topic & noun-phrase queries from sub_question; then planner keywords."""
    sq = sub_question.strip()
    seen: set[str] = set()
    out: list[str] = []

    def add(q: str | None) -> None:
        if not q or q in seen:
            return
        seen.add(q)
        out.append(q)

    # 1) Capitalized / technical phrases from raw text (agentic AI, mRNA, …)
    for q in _topic_token_queries_from_raw(sq):
        add(q)

    # 2) Main topic = all non-stop content words (defines, characteristics, agentic, ai → one string)
    add(_query_main_topic(sq))

    # 3) Adjacent content-word pairs, end-weighted (noun phrases like agentic_ai)
    for bg in _query_content_bigrams(sq):
        add(bg)

    # 4) Short tails (last 2–3 content words)
    add(_query_last_content_terms(sq, 2))
    add(_query_last_content_terms(sq, 3))

    # 5) Full line (long fallback)
    add(_query_from_sub_question_full(sq))

    # 6) Planner keywords
    parts = [k.strip() for k in keywords if k.strip()]
    if len(parts) >= 2:
        add(_query_from_top_keywords(parts, 2))
    elif len(parts) == 1:
        add(_query_from_top_keywords(parts, 1))

    return out


class Retriever:
    def run(self, sub_question: str, keywords: list[str]) -> RetrieverResult:
        try:
            return _as_json_result(self._run_impl(sub_question, keywords))
        except Exception:
            return _as_json_result(_empty_result())

    def _run_impl(self, sub_question: str, keywords: list[str]) -> RetrieverResult:
        attempts = _build_query_attempts(sub_question, keywords)
        if not attempts:
            return _empty_result()

        for query in attempts:
            print(f"[Retriever] Using query: {query}", flush=True)
            data = _fetch_summary(query)
            if data is None:
                continue
            sn = _snippet_from_extract(data)
            if sn is not None:
                return {"snippets": [sn]}

        return _empty_result()
