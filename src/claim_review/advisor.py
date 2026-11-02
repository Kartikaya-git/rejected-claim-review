import json
from datetime import datetime, timezone
from pathlib import Path

DECISIONS_FILE = Path("data/advisor_decisions.jsonl")


def record_decision(verdict: str | None, decision: str, comment: str, path: Path = DECISIONS_FILE) -> None:
    """Keeps the Claims Advisor's Decision. The Customer File itself is not stored."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.now(timezone.utc).isoformat(), "tool_verdict": verdict, "decision": decision, "comment": comment}
    with path.open("a") as file:
        file.write(json.dumps(entry) + "\n")
