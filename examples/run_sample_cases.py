"""Runs each sample case live and saves its Review, so a reader can see results without an API key."""
import json
import os
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

from claim_review.__main__ import load_customer_file
from claim_review.pipeline import review_claim
from claim_review.reader import DEFAULT_PROVIDER, PROVIDERS, LlmReader, ReaderError, load_api_key
from claim_review.summary import format_summary

ROOT = Path(__file__).parent / "sample_cases"
MAX_WAIT_SECONDS = 240


def log(message: str) -> None:
    print(message, flush=True)


def sleep_with_log(seconds: float) -> None:
    log(f"  waiting {seconds:.0f}s for the rate limit")
    time.sleep(seconds)


def main() -> int:
    provider = replace(PROVIDERS[DEFAULT_PROVIDER], fallback_models=())
    reader = LlmReader(provider, load_api_key(provider), os.environ.get("CLAIM_REVIEW_MODEL"), sleep=sleep_with_log)
    reader.max_wait_seconds = MAX_WAIT_SECONDS
    cases = json.loads((ROOT / "cases.json").read_text())
    wanted = sys.argv[1:]
    results = []
    for number, case in enumerate(cases, start=1):
        if wanted and case["case"] not in wanted:
            continue
        folder = ROOT / case["case"]
        log(f"case {number}/{len(cases)} started: {case['case']}")
        started = time.time()
        try:
            review = review_claim(load_customer_file(folder / "customer_file.json"), reader)
        except ReaderError as error:
            log(f"case {number}/{len(cases)} stopped: {error}")
            return 1
        verdict = review.verdict.value
        (folder / "review_output.txt").write_text(f"Model: {reader.models[0]}\n\n{format_summary(review)}\n\nEvidence Checklist\n" + "\n".join(
            f"- {i.status.value}: {i.label}" + (f' = {i.value}' if i.value else "") + (f' | "{i.quote}" ({i.location or i.source})' if i.quote else "") + (f" | {i.note}" if i.note else "")
            for i in review.items) + "\n")
        (folder / "review_output.json").write_text(json.dumps(asdict(review), indent=2, default=str))
        match = verdict == case["expected_verdict"] and review.decided_by == case["expected_decided_by"]
        results.append(match)
        log(f"case {number}/{len(cases)} done: {verdict}, decided by {review.decided_by}, expected {case['expected_verdict']} {case['expected_decided_by']}, {'MATCH' if match else 'DIFFERENT'} ({time.time() - started:.0f}s)")
    log(f"finished: {sum(results)}/{len(results)} matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
