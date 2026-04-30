import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .orchestrator import Orchestrator
from .settings import get_settings

BASE_DIR = Path(__file__).resolve().parent


class RunRequest(BaseModel):
    question: str


class RunResponse(BaseModel):
    report: str
    trace: dict | None = None


app = FastAPI(title="AutoResearch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_latest_trace() -> dict | None:
    trace_dir = get_settings().trace_dir
    trace_files = sorted(trace_dir.glob("run_trace_*.json"), key=lambda path: path.stat().st_mtime)
    if not trace_files:
        return None

    latest_trace = trace_files[-1]
    with latest_trace.open("r", encoding="utf-8") as file:
        return json.load(file)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run", response_model=RunResponse)
def run_research(payload: RunRequest) -> RunResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        orchestrator = Orchestrator()
        report = orchestrator.run(question)
        trace = _load_latest_trace()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RunResponse(report=report, trace=trace)
