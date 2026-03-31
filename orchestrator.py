import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from agents.critic import Critic
from agents.planner import Planner
from agents.retriever import Retriever
from agents.summarizer import Summarizer
from agents.writer import Writer

# Flow: one retrieval+summarize pass for all planner sub-questions, then at most one
# additional pass for critic requery_questions (two retrieval phases total).

_PLAN_KEYS = frozenset({"sub_questions", "keywords", "scope"})
_RETRIEVER_KEYS = frozenset({"snippets"})
_SUMMARIZER_KEYS = frozenset({"facts"})
_CRITIC_KEYS = frozenset({"gaps", "requery_needed", "requery_questions"})


def _json_roundtrip(obj: Any) -> Any:
    """Ensure values are JSON-serializable (agent handoffs use JSON-compatible data)."""
    return json.loads(json.dumps(obj, ensure_ascii=False))


def _validate_plan(data: dict) -> dict:
    if frozenset(data.keys()) != _PLAN_KEYS:
        raise ValueError("Invalid plan: bad keys.")
    sq = data["sub_questions"]
    kw = data["keywords"]
    sc = data["scope"]
    if not isinstance(sq, list) or not isinstance(kw, list) or not isinstance(sc, str):
        raise ValueError("Invalid plan: bad types.")
    if len(kw) != len(sq):
        raise ValueError("Invalid plan: keywords must align with sub_questions.")
    return _json_roundtrip(data)


def _validate_retriever(data: dict) -> dict:
    if frozenset(data.keys()) != _RETRIEVER_KEYS:
        raise ValueError("Invalid retriever output: expected snippets only.")
    snippets = data["snippets"]
    if not isinstance(snippets, list):
        raise ValueError("Invalid retriever output: snippets must be a list.")
    for s in snippets:
        if not isinstance(s, dict) or frozenset(s.keys()) != frozenset({"text", "url", "title"}):
            raise ValueError("Invalid snippet shape.")
    return _json_roundtrip(data)


def _validate_summarizer(data: dict) -> dict:
    if frozenset(data.keys()) != _SUMMARIZER_KEYS:
        raise ValueError("Invalid summarizer output: expected facts only.")
    facts = data["facts"]
    if not isinstance(facts, list):
        raise ValueError("Invalid summarizer output: facts must be a list.")
    for f in facts:
        if not isinstance(f, dict):
            raise ValueError("Invalid fact shape.")
        if not all(k in f for k in ("claim", "source_url", "confidence")):
            raise ValueError("Invalid fact shape.")
    return _json_roundtrip(data)


def _validate_critic(data: dict) -> dict:
    if frozenset(data.keys()) != _CRITIC_KEYS:
        raise ValueError("Invalid critic output: bad keys.")
    return _json_roundtrip(data)


def _save_run_trace(trace: dict[str, Any]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(__file__).resolve().parent / f"run_trace_{ts}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)
    return path


class Orchestrator:
    def __init__(self) -> None:
        self.planner = Planner()
        self.retriever = Retriever()
        self.summarizer = Summarizer()
        self.critic = Critic()
        self.writer = Writer()

    def run(self, question: str) -> str:
        trace: dict[str, Any] = {
            "planner_input": {"question": question},
            "planner_output": None,
            "retriever_outputs": [],
            "summarizer_outputs": [],
            "critic_input": None,
            "critic_output": None,
            "writer_input": None,
            "final_report": None,
        }

        plan = _validate_plan(self.planner.run(question))
        trace["planner_output"] = _json_roundtrip(plan)

        all_facts: list[dict] = []
        self._retrieve_and_summarize(
            plan["sub_questions"],
            plan["keywords"],
            all_facts,
            trace,
            phase="initial",
        )

        trace["critic_input"] = {
            "all_facts": _json_roundtrip(all_facts),
            "sub_questions": list(plan["sub_questions"]),
        }
        critic_out = _validate_critic(
            self.critic.run(_json_roundtrip(all_facts), plan["sub_questions"])
        )
        trace["critic_output"] = _json_roundtrip(critic_out)

        # Phase 1 = initial sub_questions; phase 2 = optional requery (max 2 phases total).
        if critic_out["requery_needed"]:
            for rq in critic_out["requery_questions"]:
                self._retrieve_and_summarize([rq], [[]], all_facts, trace, phase="requery")

        all_facts = _json_roundtrip(all_facts)
        trace["writer_input"] = {
            "sub_questions": list(plan["sub_questions"]),
            "facts": all_facts,
            "scope": plan["scope"],
        }
        report = self.writer.run(plan["sub_questions"], all_facts, plan["scope"])
        trace["final_report"] = report

        _save_run_trace(trace)
        return report

    def _retrieve_and_summarize(
        self,
        sub_questions: list[str],
        keywords_per_sub: list[list[str]],
        all_facts: list[dict],
        trace: dict[str, Any],
        phase: Literal["initial", "requery"],
    ) -> None:
        for i, sq in enumerate(sub_questions):
            kws = keywords_per_sub[i] if i < len(keywords_per_sub) else []
            ret_in = {"sub_question": sq, "keywords": kws}
            ret = _validate_retriever(self.retriever.run(sq, kws))
            trace["retriever_outputs"].append(
                {
                    "phase": phase,
                    "input": _json_roundtrip(ret_in),
                    "output": ret,
                }
            )
            snippets = ret["snippets"]
            summ_in = {"sub_question": sq, "snippets": snippets}
            summ = _validate_summarizer(self.summarizer.run(sq, snippets))
            trace["summarizer_outputs"].append(
                {
                    "phase": phase,
                    "input": _json_roundtrip(summ_in),
                    "output": summ,
                }
            )
            all_facts.extend(summ["facts"])
