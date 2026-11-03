from dataclasses import dataclass

from claim_review.conditions import ALL_TRUE, NO_PROBLEM_FOUND, OTHER_REASON
from claim_review.models import ItemResult, ItemStatus, RejectionReason, Review, Truth

REASON_NAMES = {
    RejectionReason.WAITING_PERIOD: "Waiting Period",
    RejectionReason.PRE_EXISTING_DISEASE: "Pre-Existing Disease",
    RejectionReason.OTHER: "Other",
}
CLAUSE_ITEMS = ("waiting_clause", "ped_exclusion", "cited_clause")


@dataclass(frozen=True)
class ReviewSummary:
    rejection_reason: str
    clause_cited: str | None
    verdict: str
    why: str
    clause_quote: str | None
    clause_location: str | None
    next_step: str
    decided_by: str | None


def _found(review: Review, item_id: str | None) -> ItemResult | None:
    item = next((i for i in review.items if i.id == item_id), None)
    return item if item and item.status is ItemStatus.FOUND else None


def _deciding_conditions(review: Review) -> list:
    if review.decided_by == ALL_TRUE:
        last = review.conditions[-1:]
        return last
    wanted = Truth.FALSE if any(c.truth is Truth.FALSE for c in review.conditions) else Truth.UNKNOWN
    picked = [c for c in review.conditions if c.truth is wanted]
    return picked[:1] if wanted is Truth.FALSE else picked


def _why(review: Review) -> str:
    if review.decided_by == "fraud_alleged":
        return "The letter alleges fraud, which this tool does not assess."
    if review.decided_by == NO_PROBLEM_FOUND:
        return "The checks generated from the clause found no problem. They are not tested, so this tool will not say the rejection is supported."
    if review.decided_by == OTHER_REASON:
        return "The reason checked does not hold up, but the letter gives another reason this tool did not check."
    picked = _deciding_conditions(review)
    if not picked:
        return "The Rejection Reason could not be identified."
    return " ".join(dict.fromkeys(c.why for c in picked))


def summarise(review: Review) -> ReviewSummary:
    reason = REASON_NAMES.get(review.rejection_reason, "Not identified")
    cited = next((found.value for i in CLAUSE_ITEMS if (found := _found(review, i))), None)
    picked = _deciding_conditions(review)
    evidence = _found(review, picked[0].evidence) if picked else None
    return ReviewSummary(
        reason,
        cited,
        review.verdict.value,
        _why(review),
        evidence.quote if evidence else None,
        (evidence.location or evidence.source) if evidence else None,
        review.next_step,
        review.decided_by,
    )
