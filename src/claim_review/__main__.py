import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from claim_review.documents import read_pdf
from claim_review.models import CustomerFile
from claim_review.pipeline import review_claim
from claim_review.summary import format_summary
from claim_review.reader import DEFAULT_PROVIDER, PROVIDERS, LlmReader, ReaderError, load_api_key


def load_customer_file(path: Path) -> CustomerFile:
    """A value ending in .pdf is read from that file, and anything else is treated as pasted text."""
    data = json.loads(path.read_text())
    texts, unreadable = {}, []
    for name in ("rejection_letter", "policy_wording", "policy_certificate", "hospital_summary", "application_form"):
        value = data.get(name, "")
        if value.lower().endswith(".pdf"):
            document = read_pdf(Path(value))
            value = document.text
            if not document.readable:
                unreadable.append(name)
        texts[name] = value
    return CustomerFile(**texts, unreadable=tuple(unreadable))


def main() -> int:
    arguments = [a for a in sys.argv[1:] if a != "--json"]
    if len(arguments) != 1:
        print("Usage: python -m claim_review <customer_file.json> [--json]", file=sys.stderr)
        return 2
    customer_file = load_customer_file(Path(arguments[0]))
    try:
        provider = PROVIDERS[os.environ.get("CLAIM_REVIEW_PROVIDER", DEFAULT_PROVIDER)]
        reader = LlmReader(provider, load_api_key(provider), os.environ.get("CLAIM_REVIEW_MODEL"))
        review = review_claim(customer_file, reader)
    except ReaderError as error:
        print(error, file=sys.stderr)
        return 1
    print(format_summary(review))
    if "--json" in sys.argv:
        print(json.dumps(asdict(review), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
