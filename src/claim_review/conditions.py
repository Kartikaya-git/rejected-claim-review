"""A rejection holds only if every condition behind it holds.

Each condition is True, False or Unknown, and code alone works it out. One False is enough to say the
reason is not supported, whatever else is unknown. All True supports it. Anything else cannot be told.
"""
from dataclasses import dataclass, field
from datetime import date

from claim_review.date_checker import within_look_back
from claim_review.models import Condition, DateCheck, ItemResult, ItemStatus, Truth, Verdict
from claim_review.rules import RuleVersion

ALL_TRUE = "all_conditions_true"
UNKNOWN = "unknown_conditions"
FRAUD = "fraud_alleged"
OTHER_REASON = "other_reason"
NO_PROBLEM_FOUND = "no_problem_found"
BREAK_STEP = "A break in cover was found. Confirm the dates of continuous cover with the insurer."


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    decided_by: str
    next_step: str
    conditions: list[Condition] = field(default_factory=list)


def verdict_from(conditions: list[Condition]) -> Verdict:
    if any(c.truth is Truth.FALSE for c in conditions):
        return Verdict.REASON_NOT_SUPPORTED
    if conditions and all(c.truth is Truth.TRUE for c in conditions):
        return Verdict.REASON_SUPPORTED
    return Verdict.CANNOT_TELL


def decide(conditions: list[Condition], supported_step: str) -> Outcome:
    verdict = verdict_from(conditions)
    if verdict is Verdict.REASON_NOT_SUPPORTED:
        failed = next(c for c in conditions if c.truth is Truth.FALSE)
        return Outcome(verdict, failed.id, failed.next_step, conditions)
    if verdict is Verdict.REASON_SUPPORTED:
        return Outcome(verdict, ALL_TRUE, supported_step, conditions)
    steps = list(dict.fromkeys(c.next_step for c in conditions if c.truth is Truth.UNKNOWN))
    return Outcome(verdict, UNKNOWN, " ".join(steps), conditions)


def limit_to_checked_reason(outcome: Outcome, other_reason: str | None) -> Outcome:
    """Beating one reason means little while the letter gives another that was not checked."""
    if other_reason is None or outcome.verdict is not Verdict.REASON_NOT_SUPPORTED:
        return outcome
    step = f'The letter also says: "{other_reason}". This tool did not check that. Review it before relying on this result.'
    return Outcome(Verdict.CANNOT_TELL, OTHER_REASON, step, outcome.conditions)


def _rejected(item: ItemResult) -> bool:
    """The model answered, but the evidence failed. That is unknown, not absent."""
    return item.status is ItemStatus.NOT_FOUND and (item.note or "").startswith(("Quote did not", "Value is not"))


def _unsure(item: ItemResult) -> bool:
    return item.status is ItemStatus.UNCLEAR or _rejected(item)


def _says(item: ItemResult, value: str) -> bool:
    return item.status is ItemStatus.FOUND and item.value == value


def _obtain(labels: list[str]) -> str:
    return "Check or obtain this evidence before deciding: " + ", ".join(labels) + "."


def _yes_no(items, item_id, condition_id, label, false_why, false_step) -> Condition:
    item = items[item_id]
    if _says(item, "no"):
        return Condition(condition_id, label, Truth.FALSE, false_why, false_step, item_id)
    if _says(item, "yes"):
        return Condition(condition_id, label, Truth.TRUE, label, "", item_id)
    return Condition(condition_id, label, Truth.UNKNOWN, f"Unclear: {item.label}.", _obtain([item.label]), item_id)


def _nothing_against(item: ItemResult, condition_id: str, label: str, found_why: str, found_step: str) -> Condition:
    """True unless the evidence shows something that defeats the rejection."""
    if _says(item, "yes"):
        return Condition(condition_id, label, Truth.FALSE, found_why, found_step, item.id)
    if _unsure(item):
        return Condition(condition_id, label, Truth.UNKNOWN, f"Unclear: {item.label}.", _obtain([item.label]), item.id)
    return Condition(condition_id, label, Truth.TRUE, label, "")


def _no_waiver(items: dict[str, ItemResult]) -> Condition:
    return _nothing_against(
        items["waiver"], "no_waiver", "No waiver applies",
        "The Customer File shows a waiver of this term.",
        "The Customer File shows a waiver. Raise it with the insurer, citing the quoted term.",
    )


def _no_exception(items: dict[str, ItemResult]) -> Condition:
    return _nothing_against(
        items["clause_exception"], "no_exception", "No exception in the clause applies",
        "The policy states an exception to this clause, and this claim appears to meet it.",
        "The clause has an exception this claim appears to meet. Raise it with the insurer, citing the quoted term.",
    )


def _cover_gaps(items: dict[str, ItemResult], needed: tuple[str, ...]) -> list[str]:
    gaps = [items[i].label for i in needed if items[i].status is not ItemStatus.FOUND]
    gaps += [items[i].label for i in ("continuity_credit_months", "break_in_cover") if _unsure(items[i])]
    return gaps


def _unknown_from_cover(condition_id, label, items, gaps, evidence) -> Condition | None:
    if gaps:
        return Condition(condition_id, label, Truth.UNKNOWN, "Evidence is missing or unclear: " + ", ".join(gaps) + ".", _obtain(gaps), evidence)
    if _says(items["break_in_cover"], "yes"):
        return Condition(condition_id, label, Truth.UNKNOWN, "A break in cover was found, so continuous cover cannot be confirmed.", BREAK_STEP, "break_in_cover")
    return None


def _period_not_ended(items: dict[str, ItemResult], check: DateCheck | None) -> Condition:
    label = "The Waiting Period had not ended at admission"
    gaps = _cover_gaps(items, ("cover_start", "admission_date", "waiting_months"))
    unknown = _unknown_from_cover("period_not_ended", label, items, gaps, "waiting_months")
    if unknown:
        return unknown
    credit = f", with {check.credit_months} months of credit" if check.credit_months else ""
    why = f"The Waiting Period is {check.waiting_months} months{credit}, so it ends on {check.period_ends}. Admission was on {check.admission_date}"
    if check.period_passed:
        step = "The Waiting Period appears complete on these dates. Ask the insurer to confirm the dates it used."
        return Condition("period_not_ended", label, Truth.FALSE, f"{why}, so it was complete.", step, "waiting_months")
    return Condition("period_not_ended", label, Truth.TRUE, f"{why}, so it was not complete.", "", "waiting_months")


def waiting_period_outcome(
    items: dict[str, ItemResult], check: DateCheck | None, rules: dict[str, RuleVersion]
) -> Outcome:
    covers = _yes_no(
        items, "illness_under_clause", "illness_under_clause", "The cited clause covers this illness",
        "The illness treated does not appear to fall under the cited clause.",
        "The illness does not appear to fall under the cited clause. Ask the insurer to explain how it applies.",
    )
    missing = [items[i].label for i in ("waiting_clause", "illness_treated") if items[i].status is not ItemStatus.FOUND]
    if covers.truth is Truth.TRUE and missing:
        covers = Condition(covers.id, covers.label, Truth.UNKNOWN, "Evidence is missing or unclear: " + ", ".join(missing) + ".", _obtain(missing), covers.evidence)
    conditions = [_no_waiver(items), _no_exception(items), covers, _period_not_ended(items, check)]
    return decide(conditions, "The Customer File supports the stated reason. Confirm there is no other evidence of earlier cover or a waiver.")


def _condition_existed(items: dict[str, ItemResult]) -> Condition:
    before, prior, label = items["condition_before_cover"], items["prior_condition_date"], "The condition existed before cover"
    if _says(before, "yes") or prior.status is ItemStatus.FOUND:
        return Condition("condition_existed", label, Truth.TRUE, label, "", "condition_before_cover")
    if _unsure(before) or _unsure(prior):
        labels = [i.label for i in (before, prior) if _unsure(i)]
        return Condition("condition_existed", label, Truth.UNKNOWN, "Evidence is missing or unclear: " + ", ".join(labels) + ".", _obtain(labels), "condition_before_cover")
    step = "The Customer File shows no earlier condition. Ask the insurer for the evidence it relied on."
    return Condition("condition_existed", label, Truth.FALSE, "The Customer File shows no earlier condition.", step)


def _within_look_back(items: dict[str, ItemResult], check: DateCheck | None, rules) -> Condition:
    prior, label = items["prior_condition_date"], "The condition falls within the Look-Back Limit"
    if prior.status is not ItemStatus.FOUND:
        return Condition("within_look_back", label, Truth.TRUE, "No dated record falls outside the limit.", "")
    cover = items["cover_start"]
    if cover.status is not ItemStatus.FOUND:
        return Condition("within_look_back", label, Truth.UNKNOWN, f"Evidence is missing or unclear: {cover.label}.", _obtain([cover.label]), "prior_condition_date")
    if within_look_back(date.fromisoformat(prior.value), date.fromisoformat(cover.value), rules["ped_look_back_months"].value):
        return Condition("within_look_back", label, Truth.TRUE, label, "", "prior_condition_date")
    step = "The latest recorded diagnosis or treatment falls before the look-back limit. Check for later records."
    return Condition("within_look_back", label, Truth.FALSE, "The latest recorded diagnosis or treatment falls before the Look-Back Limit.", step, "prior_condition_date")


def _moratorium_not_complete(items: dict[str, ItemResult], check: DateCheck | None) -> Condition:
    label = "The Moratorium was not complete at admission"
    gaps = _cover_gaps(items, ("cover_start", "admission_date"))
    unknown = _unknown_from_cover("moratorium_not_complete", label, items, gaps, "moratorium_clause")
    if unknown:
        return unknown
    if check.moratorium_complete:
        step = "The Moratorium appears complete, so non-disclosure may not be relied on without established fraud."
        return Condition("moratorium_not_complete", label, Truth.FALSE, "The Moratorium appears complete, and the rejection relies on non-disclosure.", step, "moratorium_clause")
    return Condition("moratorium_not_complete", label, Truth.TRUE, label, "", "moratorium_clause")


def _not_declared(items: dict[str, ItemResult]) -> Condition:
    item, label = items["declared_on_application"], "The condition was not declared"
    if _says(item, "no"):
        return Condition("not_declared", label, Truth.TRUE, "The condition came before cover and was not declared on the application form.", "", item.id)
    if _says(item, "yes"):
        step = "The application form shows the condition was declared. Raise this with the insurer."
        return Condition("not_declared", label, Truth.FALSE, "The application form shows the condition was declared.", step, item.id)
    return Condition("not_declared", label, Truth.UNKNOWN, "The application form is not available or does not settle this.", "Obtain the application form to see what was declared.", item.id)


def _generated_condition(item: ItemResult) -> Condition:
    if _says(item, "no"):
        why = f"The documents show this does not hold: {item.label}"
        step = "The documents contradict what the rejection needs. Raise this with the insurer, citing the quote."
        return Condition(item.id, item.label, Truth.FALSE, why, step, item.id)
    if _says(item, "yes"):
        return Condition(item.id, item.label, Truth.TRUE, item.label, "", item.id)
    return Condition(item.id, item.label, Truth.UNKNOWN, f"Unsettled: {item.label}", _obtain([item.label]), item.id)


def any_reason_outcome(items: dict[str, ItemResult], generated: list[str]) -> Outcome:
    """Generated checks are untested, so they can raise a problem but can never clear the insurer."""
    if _says(items["fraud_alleged"], "yes"):
        step = "The letter alleges fraud, which only established evidence can settle. Review this manually."
        return Outcome(Verdict.CANNOT_TELL, FRAUD, step)
    conditions = [_no_waiver(items), _no_exception(items)] + [_generated_condition(items[i]) for i in generated]
    if not generated:
        step = "No checks could be generated from the clause. Review this rejection manually."
        conditions.append(Condition("checks_generated", "Checks were generated from the clause", Truth.UNKNOWN, "No checks could be generated from the clause.", step))
    outcome = decide(conditions, "")
    if outcome.verdict is Verdict.REASON_SUPPORTED:
        step = "These checks were generated for this claim and are not tested. Review the rejection yourself."
        return Outcome(Verdict.CANNOT_TELL, NO_PROBLEM_FOUND, step, conditions)
    return outcome


def pre_existing_disease_outcome(
    items: dict[str, ItemResult], check: DateCheck | None, rules: dict[str, RuleVersion]
) -> Outcome:
    basis = items["rejection_basis"]
    if _says(basis, "fraud"):
        step = "The letter alleges fraud, which only established evidence can settle. Review this manually."
        return Outcome(Verdict.CANNOT_TELL, FRAUD, step)

    conditions = [
        _no_waiver(items),
        _no_exception(items),
        _condition_existed(items),
        _yes_no(
            items, "same_condition", "same_illness", "The illness is that condition or its complication",
            "The illness treated does not appear to be the earlier condition or its complication.",
            "The treated illness does not appear linked to the earlier condition. Ask the insurer to explain the link.",
        ),
        _within_look_back(items, check, rules),
    ]
    if _says(basis, "non_disclosure"):
        conditions += [_moratorium_not_complete(items, check), _not_declared(items)]
    elif _says(basis, "waiting_period"):
        conditions.append(_period_not_ended(items, check))
    else:
        conditions.append(Condition("basis_known", "The rejection basis is clear", Truth.UNKNOWN, f"Unclear: {basis.label}.", _obtain([basis.label])))
    return decide(conditions, "The Customer File supports the stated reason. Confirm there is no waiver or earlier cover to credit.")
