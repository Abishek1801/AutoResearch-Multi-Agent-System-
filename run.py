from datetime import datetime
from pathlib import Path

from orchestrator import Orchestrator

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


def _read_question() -> str:
    while True:
        q = input("Enter your research question: ").strip()
        if q:
            return q


def main() -> None:
    question = _read_question()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"report_{ts}.md"

    orchestrator = Orchestrator()
    report = orchestrator.run(question)

    out_path.write_text(report, encoding="utf-8")
    print(f"Success: report saved to {out_path}")


if __name__ == "__main__":
    main()
