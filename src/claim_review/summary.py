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


def format_summary(review: Review) -> str:
    s = summarise(review)
    lines = ["First-pass review, not advice or a decision.", "", f"Rejection reason: {s.rejection_reason}"]
    if s.clause_cited:
        lines.append(f"Clause in question: {s.clause_cited}")
    lines += [f"Verdict: {s.verdict}", f"Why: {s.why}"]
    if s.clause_quote:
        lines.append(f'Clause relied on: "{s.clause_quote}" ({s.clause_location})')
    lines.append(f"Next step: {s.next_step}")
    if review.transition_flag:
        lines.append(f"Transition Flag: {review.transition_flag}")
    if review.other_reason:
        lines.append(f'Other reason in the letter, not checked: "{review.other_reason}"')
    if review.checks_generated:
        lines.append("Checks: generated from the clause for this claim, not tested.")
    if review.conditions:
        lines.append("Conditions for the rejection to hold:")
        lines += [f"  {c.truth.value}: {c.label}" for c in review.conditions]
    if s.decided_by:
        lines.append(f"Decided by: {s.decided_by}")
    return "\n".join(lines)
