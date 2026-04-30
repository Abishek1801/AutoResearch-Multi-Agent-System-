# AutoResearcher MAS

This repository is now organized as a clean monolithic full-stack application for AutoResearcher MAS, with separate `backend/` and `frontend/` folders.

## Structure

```text
.
├── backend
│   ├── agents
│   ├── outputs
│   ├── orchestrator.py
│   ├── server.py
│   ├── utils.py
│   └── requirements.txt
├── frontend
│   ├── src
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Backend

The backend uses FastAPI and wraps your existing `Orchestrator` class.

- `POST /run`
- Accepts `{ "question": "..." }`
- Returns the generated Markdown report
- Also returns the latest `run_trace_*.json` payload when available

Start it from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.server:app --reload
```

The API will run at [http://localhost:8000](http://localhost:8000).

Before starting the backend, configure OpenAI for the LLM connection:

```bash
cp .env.example .env
```

Then set at least:

```bash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

The backend reads `.env` automatically and uses those values for all LLM-based agents.

## Frontend

The frontend uses React with Vite and provides:

- A centered input form for the research question
- A loading state while the orchestrator runs
- Markdown report rendering
- A compact run summary
- An optional collapsible trace viewer

Start it from the project root:

```bash
cd frontend
npm install
npm run dev
```

The frontend will run at [http://localhost:5173](http://localhost:5173).

## Notes

- Set `OPENAI_API_KEY` in `.env` or your shell before running the backend.
- Generated reports are written under `backend/outputs/`.
- Generated traces are written as `backend/run_trace_<timestamp>.json`.
