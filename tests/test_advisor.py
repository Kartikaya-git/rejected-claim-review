import json

from claim_review.advisor import record_decision


def test_decision_is_recorded_without_the_customer_file(tmp_path):
    path = tmp_path / "decisions.jsonl"

    record_decision("Reason Supported", "Correct", "Waiver missed", path)

    entry = json.loads(path.read_text())
    assert entry["decision"] == "Correct"
    assert set(entry) == {"time", "tool_verdict", "decision", "comment"}
