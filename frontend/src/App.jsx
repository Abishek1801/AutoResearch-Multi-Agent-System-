import { useState } from "react";
import ReactMarkdown from "react-markdown";

const API_URL =
  import.meta.env.VITE_API_URL ||
  (window.location.hostname === "localhost" ? "http://localhost:8000/run" : "/api/run");

function getTraceSummary(trace) {
  if (!trace) {
    return null;
  }

  const plannerCount = trace.planner_output?.sub_questions?.length ?? 0;
  const retrievalCount = trace.retriever_outputs?.length ?? 0;
  const factCount = trace.writer_input?.facts?.length ?? 0;
  const requeryCount = trace.critic_output?.requery_questions?.length ?? 0;
  const requeryNeeded = trace.critic_output?.requery_needed ? "Yes" : "No";

  return [
    { label: "Planned Questions", value: plannerCount },
    { label: "Retrieval Passes", value: retrievalCount },
    { label: "Facts Collected", value: factCount },
    { label: "Requery Needed", value: requeryNeeded },
    { label: "Follow-up Questions", value: requeryCount },
  ];
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [report, setReport] = useState("");
  const [trace, setTrace] = useState(null);
  const [warning, setWarning] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const traceSummary = getTraceSummary(trace);

  async function handleRunResearch() {
    const trimmedQuestion = question.trim();

    if (!trimmedQuestion) {
      setWarning("Please enter a research question before running the system.");
      setError("");
      return;
    }

    setWarning("");
    setError("");
    setLoading(true);
    setReport("");
    setTrace(null);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: trimmedQuestion }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "The research request failed.");
      }

      setReport(data.report || "");
      setTrace(data.trace || null);
    } catch (requestError) {
      setError(requestError.message || "Unable to reach the backend service.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="app-card">
        <div className="hero">
          <span className="eyebrow">Multi-Agent Research Workspace</span>
          <h1>AutoResearcher MAS</h1>
          <p>
            Ask a research question, run the orchestrator, and review the structured report in one
            clean workspace.
          </p>
        </div>

        <label className="input-label" htmlFor="question">
          Research Question
        </label>
        <textarea
          id="question"
          className="question-input"
          placeholder="What are the defining characteristics of agentic AI, and how does it differ from traditional automation?"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={6}
        />

        <div className="action-row">
          <button className="run-button" type="button" onClick={handleRunResearch} disabled={loading}>
            {loading ? "Running Research..." : "Run Research"}
          </button>
          {loading ? (
            <div className="loading-indicator" aria-live="polite">
              <span className="spinner" />
              Generating report
            </div>
          ) : null}
        </div>

        {warning ? <div className="message warning">{warning}</div> : null}
        {error ? <div className="message error">{error}</div> : null}

        {traceSummary ? (
          <section className="summary-panel">
            <h2>Run Summary</h2>
            <div className="summary-grid">
              {traceSummary.map((item) => (
                <div className="summary-item" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {report ? (
          <section className="report-panel">
            <h2>Research Report</h2>
            <div className="markdown-body">
              <ReactMarkdown>{report}</ReactMarkdown>
            </div>
          </section>
        ) : null}

      </section>
    </main>
  );
}
