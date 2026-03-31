# AutoResearch: Multi-Agent Research System

## Overview

**AutoResearch** is a multi-agent pipeline that accepts a **plain-English research question** and produces a **structured Markdown research report**. Specialized agents collaborate to **plan** the inquiry, **retrieve** evidence from the open web, **summarize** it into cited facts, **critique** coverage, and **write** the final document.

- **Language models:** [OpenAI](https://platform.openai.com/) Chat Completions API, model **`gpt-4o-mini`** (all LLM steps; temperature **0** for determinism).
- **Web sources:** [Wikipedia](https://www.wikipedia.org/) via the free [REST summary API](https://en.wikipedia.org/api/rest_v1/) (no API key; subject to Wikimedia [terms of use](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use)).

The system demonstrates **orchestrated agents** with **JSON-only** structured handoffs. It is **not** a substitute for peer-reviewed research.

---

## System Architecture

| Agent | Responsibility |
|--------|------------------|
| **Planner** | Decomposes the user question into **sub-questions**, aligned **keyword** lists (for retrieval), and a **scope** statement. Output is **strict JSON**. |
| **Retriever** | For each sub-question, builds Wikipedia title-style **queries** and fetches **page summaries** (text, title, URL). No LLM; uses HTTP only. |
| **Summarizer** | Reads retrieved **snippets** and outputs **structured facts** (`claim`, `source_url`, `confidence`). **Strict JSON**; skips the LLM when snippets are empty to avoid hallucination. |
| **Critic** | Compares aggregated facts to the plan; lists **gaps** and **contradictions**; may set **`requery_needed`** and up to **two** follow-up questions when gaps are **significant**. |
| **Writer** | Synthesizes a **Markdown** report (executive summary, one section per sub-question with citations, limitations) from the provided facts and scope. |

**Inter-agent communication** is **JSON-shaped data**: each agent’s output is parsed and validated before the next step. The orchestrator may round-trip values through JSON to keep payloads serializable and consistent.

---

## Orchestration

End-to-end flow:

1. **Planner** — Produces sub-questions, keywords per sub-question, and scope.
2. **Retriever + Summarizer** — For each sub-question: fetch Wikipedia snippets, then extract facts. Facts are **aggregated** across sub-questions.
3. **Critic** — Evaluates coverage vs. sub-questions; optionally requests **requery** (limited follow-up questions).
4. **Optional second retrieval phase** — If the critic requires it, the pipeline runs **additional** retrieve → summarize passes (at most **two retrieval phases** total: initial + requery).
5. **Writer** — Generates the final **Markdown** report from all facts and the planner’s scope.

---

## Installation

**Requirements:** Python **3.10+** recommended.

1. Create and activate a virtual environment (optional but recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install the OpenAI SDK:

   ```bash
   pip install openai
   ```

   Wikipedia access uses Python’s standard library (`urllib`); no separate `requests` package is required for the default retriever.

3. Set your API key (never commit it to the repository):

   ```bash
   export OPENAI_API_KEY="sk-..."   # macOS / Linux
   ```

   On Windows, use **Environment Variables** in System Settings or `set` in `cmd`.

---

## How to Run

From the **project root**:

```bash
python run.py
```

You will be prompted:

```text
Enter your research question:
```

Enter a non-empty question; the pipeline runs and exits when the report is written. The `outputs/` directory is created automatically if missing.

---

## Output Files

| File | Description |
|------|-------------|
| **`outputs/report_<timestamp>.md`** | Final **Markdown** research report. |
| **`run_trace_<timestamp>.json`** | Full **trace** of agent inputs and outputs (planner, retriever, summarizer, critic, writer, final report) for debugging and reproducibility. |

Timestamps use a `YYYYMMDD_HHMMSS`-style suffix.

---

## Design Decisions

- **Wikipedia REST API** — Free, stable, and keyless; trades depth for simplicity (summary text only, not full articles or ranked web search).
- **`gpt-4o-mini`** — Single model for all LLM agents to balance **cost**, **latency**, and acceptable quality for structured JSON and report drafting.
- **JSON between agents** — Enforces inspectable, validatable handoffs and keeps each step’s inputs and outputs explicit.
- **Thin orchestration** — Linear pipeline with an optional **critic-triggered** second retrieval pass (**max two retrieval phases**), avoiding complex scheduling while still demonstrating re-planning.
- **Empty retrieval handling** — Summarizer returns empty facts when there are no snippets, avoiding LLM-invented content in that case.

---

## Limitations

- **Retrieval** — Results depend on **query–article title** match; niche or multi-hop questions may yield **irrelevant** or **empty** snippets. There is **no** search engine ranking or multi-corpus fusion.
- **Query formulation** — Heuristic cleaning (stopwords, underscores, fallbacks) is **not** semantic search; weak queries propagate downstream.
- **Summarizer** — Fact quality is bounded by **snippet quality**; thin or noisy text limits useful claims.
- **Verification** — Mostly **single-source** (one Wikipedia summary per attempt); no cross-source consistency checks.
- **Model behavior** — Even with prompts and validation, **hallucination** or **overconfident** phrasing is possible; outputs should be treated as **AI-assisted drafts**, not authoritative citations.

---

## Cost Estimate

With **`gpt-4o-mini`** across planning, summarization, critique, and writing, a typical end-to-end run is on the order of **US $0.005–$0.01** per run for moderate-length prompts (order-of-magnitude only). Actual cost depends on token counts and [current OpenAI pricing](https://platform.openai.com/docs/pricing); check your usage dashboard.

---

## Example Questions

Useful prompts for testing:

1. *What are the defining characteristics of agentic AI, and how does it differ from traditional automation?*
2. *What are the main mechanisms of mRNA vaccines, and how has public uptake varied by region?*
3. *How does photosynthesis convert light energy into chemical energy in plants?*

---

## Future Improvements

- **Richer retrieval** — Multi-source search, embeddings, or ranked results beyond a single summary title.
- **Query understanding** — Entity linking or question decomposition tuned to open-domain QA.
- **Stronger fact validation** — Entailment checks, minimum evidence thresholds, or human-in-the-loop review.
- **Parallelism** — Concurrent retrieve/summarize per sub-question where dependencies allow.
- **Configuration** — CLI flags or a config file for model name, temperature, and paths.

---

*Do not embed API keys or other secrets in source control.*
