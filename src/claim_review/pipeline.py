import sys
from dataclasses import replace
from datetime import date

from claim_review.checklists import ANY_REASON_CHECKLIST, CHECKLISTS, generated_item
from claim_review.date_checker import check_cover
from claim_review.evidence import dates_in, months_in, quote_in_source
from claim_review.models import (
    Answer,
    AnswerType,
    ChecklistItem,
    CustomerFile,
    DateCheck,
    ItemResult,
    ItemStatus,
    Passage,
    RejectionReason,
    Review,
    Verdict,
)
from claim_review.policy_index import Clause, build_index
from claim_review.reader import Reader, ReadingQuestion
from claim_review.rules import RULE_VERSIONS, RuleVersion, active_rule_sets, rule_set
from claim_review.search import Embedder, LocalEmbedder, PolicySearch
from claim_review.conditions import (
    Outcome,
    any_reason_outcome,
    limit_to_checked_reason,
    pre_existing_disease_outcome,
    waiting_period_outcome,
)

LONG_DOCUMENT_CHARS = 6000

ILLNESS_ALIASES_QUESTION = ReadingQuestion(
    "illness_aliases",
    "List other names for this illness, including its everyday name and medical name, as a short comma separated "
    "list in value. These only guide a search. Quote is not needed.",
    AnswerType.TEXT,
)

DECIDERS = {
    RejectionReason.WAITING_PERIOD: waiting_period_outcome,
    RejectionReason.PRE_EXISTING_DISEASE: pre_existing_disease_outcome,
}

REJECTION_REASON_QUESTION = ReadingQuestion(
    "rejection_reason",
    "What reason does the letter state for rejecting the claim? Answer pre_existing_disease if it relies on an illness "
    "that existed before cover, even if it also mentions a waiting period. Answer waiting_period if it relies on a "
    "waiting period for a named illness or treatment, with no claim that it existed before cover. Otherwise answer other.",
    AnswerType.TEXT,
)


MAX_GENERATED_CHECKS = 5
CONDITIONS_QUESTION = ReadingQuestion(
    "rejection_conditions",
    "Read the clause the rejection letter relies on. List the facts that must all be true for that clause to justify "
    f"this rejection, at most {MAX_GENERATED_CHECKS}, each a short statement about this claim that the claim documents "
    "could prove or disprove. Put them in value, separated by ' | '. Quote the clause.",
    AnswerType.TEXT,
)

OTHER_REASON_QUESTION = ReadingQuestion(
    "other_reason",
    "Does the letter also reject the claim for a separate reason, such as a lapsed policy, late intimation or an "
    "excluded treatment? A waiting period, a pre-existing disease and its non-disclosure count as one reason, not "
    "separate ones. Answer yes and quote the separate reason. Otherwise answer not_found.",
    AnswerType.YES_NO,
)


def _candidates(sources: tuple[str, ...], documents: dict[str, str]) -> list[Passage]:
    return [Passage(name, documents[name]) for name in sources if documents[name].strip()]


class Evidence:
    """Gives the Reader whole short documents, and the relevant clauses of a long policy."""

    def __init__(self, customer_file: CustomerFile, embedder: Embedder | None):
        self.documents = customer_file.documents()
        self.unreadable = customer_file.unreadable
        self.search = None
        self.illness_terms = ""
        policy = customer_file.policy_wording
        if len(policy) > LONG_DOCUMENT_CHARS:
            self.search = PolicySearch(build_index(policy), embedder or LocalEmbedder())

    def _others(self, item: ChecklistItem) -> list[Passage]:
        return _candidates(tuple(n for n in item.sources + item.context if n != "policy_wording"), self.documents)

    def searches_policy(self, item: ChecklistItem) -> bool:
        return self.search is not None and "policy_wording" in item.sources + item.context

    def passages(self, item: ChecklistItem) -> tuple[list[Passage], list[Clause], list[str]]:
        """Passages to read, the clauses searched, and a Search Trace."""
        if not self.searches_policy(item):
            return _candidates(item.sources + item.context, self.documents), [], []
        refinement = self.illness_terms if item.uses_illness else ""
        clauses = self.search.find(item, self.documents["rejection_letter"], refinement)
        return self._as_passages(clauses) + self._others(item), clauses, [_trace_step(item.label, refinement, clauses)]

    def retry(self, item: ChecklistItem, query: str, seen: list[Clause]) -> tuple[list[Passage], list[Clause]]:
        clauses = self.search.find(item, query=query, exclude=tuple(seen))
        return self._as_passages(clauses) + self._others(item), clauses

    def _as_passages(self, clauses: list[Clause]) -> list[Passage]:
        return [Passage("policy_wording", c.text, f"clause {c.id}, page {c.page}") for c in clauses]

    def learn_illness(self, illness: str, reader: Reader) -> None:
        if self.search is None:
            return
        aliases = reader.answer(ILLNESS_ALIASES_QUESTION, [Passage("illness_treated", illness)])
        self.illness_terms = " ".join(filter(None, [illness, aliases.value]))

    def location(self, source: str, quote: str) -> str | None:
        if self.search is None or source != "policy_wording":
            return None
        clause = next((c for c in self.search.index.clauses if quote_in_source(quote, c.text)), None)
        return f"clause {clause.id}, page {clause.page}" if clause else None


def _trace_step(label: str, refinement: str, clauses: list[Clause]) -> str:
    found = ", ".join(f"clause {c.id}" for c in clauses) or "nothing"
    terms = f" with {refinement}" if refinement else ""
    return f"Searched for {label}{terms}: {found}"


def _gap_question(item: ChecklistItem) -> ReadingQuestion:
    return ReadingQuestion(
        "refined_query",
        f"A health insurance policy search for '{item.label}' found nothing. Write one short search query, under 12 "
        "words, using other wording an insurer might use for this. Put it in value.",
        AnswerType.TEXT,
    )


def _pick(values_in_quote: set, stated) -> object | None:
    """Code reads the value from the quote, and the model's value only chooses between several."""
    if len(values_in_quote) == 1:
        return next(iter(values_in_quote))
    return stated if stated in values_in_quote else None


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        return None


def _proven_value(item: ChecklistItem, answer: Answer) -> str | None:
    """The value a quote proves, or None if it proves nothing."""
    if item.choices:
        return answer.value if answer.value in item.choices else None
    if item.answer_type is AnswerType.DATE:
        picked = _pick(dates_in(answer.quote or ""), _parse_date(answer.value))
        return picked.isoformat() if picked else None
    if item.answer_type is AnswerType.MONTHS:
        stated = int(answer.value) if (answer.value or "").isdigit() else None
        picked = _pick(months_in(answer.quote or ""), stated)
        return str(picked) if picked is not None else None
    if item.answer_type is AnswerType.YES_NO:
        return answer.value if answer.value in ("yes", "no") else None
    return answer.value or None


def _evidence_problem(item: ChecklistItem, answer: Answer, documents: dict[str, str]) -> str | None:
    if answer.is_unclear or answer.is_not_found:
        return None
    if answer.source not in item.sources or not quote_in_source(answer.quote, documents[answer.source]):
        return f"Quote did not match the source: {(answer.quote or '')[:120]}"
    if _proven_value(item, answer) is None:
        return "Value is not shown in the quote."
    return None


def _read(
    item: ChecklistItem, passages: list[Passage], documents: dict[str, str], reader: Reader
) -> tuple[Answer, str | None]:
    """Asks once, and once more if the answer fails its evidence check."""
    allowed = ", ".join(item.sources)
    question = ReadingQuestion(item.id, f"{item.question} Quote only from: {allowed}.", item.answer_type, item.may_calculate)
    answer = reader.answer(question, passages)
    problem = _evidence_problem(item, answer, documents)
    if problem:
        answer = reader.answer(question, passages)
        problem = _evidence_problem(item, answer, documents)
    return answer, problem


def _check_item(item: ChecklistItem, evidence: Evidence, reader: Reader) -> ItemResult:
    documents = evidence.documents
    result = {"id": item.id, "label": item.label, "required": item.required}
    if not _candidates(item.sources, documents):
        unreadable = any(name in evidence.unreadable for name in item.sources)
        note = "File has no readable text." if unreadable else "Document not provided."
        return ItemResult(status=ItemStatus.NOT_FOUND, note=note, **result)

    print(f"Checking: {item.label}", file=sys.stderr, flush=True)
    passages, seen, trace = evidence.passages(item)
    answer, problem = _read(item, passages, documents, reader)

    if (item.required or item.retries) and evidence.searches_policy(item) and (answer.is_not_found or problem):
        refined = reader.answer(_gap_question(item), [Passage("gap", item.label)])
        more, new_clauses = evidence.retry(item, refined.value or item.label, seen) if refined.value else ([], [])
        if new_clauses:
            trace.append(_trace_step(item.label, refined.value, new_clauses))
            answer, problem = _read(item, more, documents, reader)
        else:
            trace.append(f"Retry Hop with {refined.value}: no new clauses, stopped")
    result["search_trace"] = tuple(trace)

    if answer.is_unclear:
        return ItemResult(status=ItemStatus.UNCLEAR, **result)
    if answer.is_not_found:
        return ItemResult(status=ItemStatus.NOT_FOUND, **result)
    if problem:
        return ItemResult(status=ItemStatus.NOT_FOUND, note=problem, **result)
    return ItemResult(
        status=ItemStatus.FOUND,
        value=_proven_value(item, answer),
        quote=answer.quote,
        source=answer.source,
        location=evidence.location(answer.source, answer.quote),
        working=answer.working,
        **result,
    )


def _read_rejection_reason(documents: dict[str, str], reader: Reader) -> tuple[RejectionReason | None, str]:
    """The reason, and the letter's own words for it."""
    passages = _candidates(("rejection_letter",), documents)
    if not passages:
        return None, ""
    answer = reader.answer(REJECTION_REASON_QUESTION, passages)
    if answer.is_unclear or answer.is_not_found:
        return None, ""
    if not quote_in_source(answer.quote, documents["rejection_letter"]):
        return None, ""
    try:
        return RejectionReason(answer.value), answer.quote
    except ValueError:
        return None, ""


def _read_other_reason(documents: dict[str, str], reader: Reader) -> str | None:
    answer = reader.answer(OTHER_REASON_QUESTION, _candidates(("rejection_letter",), documents))
    if answer.value == "yes" and quote_in_source(answer.quote, documents["rejection_letter"]):
        return answer.quote
    return None


def _flag_shared_quote(items: dict[str, ItemResult]) -> None:
    """A Waiting Period and a credit are separate facts, so one line cannot prove both."""
    length, credit = items["waiting_months"], items["continuity_credit_months"]
    if length.status is ItemStatus.FOUND and credit.status is ItemStatus.FOUND and length.quote == credit.quote:
        items["waiting_months"] = replace(
            length, status=ItemStatus.UNCLEAR, note="Same quote was used for the credit, so the length needs checking."
        )


def _date_check(items: dict[str, ItemResult], rules: dict[str, RuleVersion]) -> DateCheck | None:
    if any(items[i].status is not ItemStatus.FOUND for i in ("cover_start", "admission_date")):
        return None
    credit, waiting = items["continuity_credit_months"], items["waiting_months"]
    return check_cover(
        date.fromisoformat(items["cover_start"].value),
        date.fromisoformat(items["admission_date"].value),
        int(waiting.value) if waiting.status is ItemStatus.FOUND else None,
        int(credit.value) if credit.status is ItemStatus.FOUND else 0,
        rules["moratorium_months"].value,
    )


def _rule_sets(items: dict[str, ItemResult]) -> list[dict[str, RuleVersion]]:
    admission = items["admission_date"]
    if admission.status is ItemStatus.FOUND:
        return active_rule_sets(date.fromisoformat(admission.value))
    return [rule_set(max(r.valid_from for r in RULE_VERSIONS if r.valid_from))]


def _transition_flag(primary: Outcome, others: list[Outcome]) -> str | None:
    for other in others:
        if other.verdict is not primary.verdict:
            return (
                f"These dates fall in the 2024 transition. Under the older Rule Version this would be "
                f"{other.verdict.value}. Check which version applies to this product."
            )
    return None


def _check_items(checklist: tuple[ChecklistItem, ...], evidence: Evidence, reader: Reader) -> dict[str, ItemResult]:
    results = {}
    for item in checklist:
        results[item.id] = _check_item(item, evidence, reader)
        if item.id == "illness_treated" and results[item.id].status is ItemStatus.FOUND:
            evidence.learn_illness(results[item.id].value, reader)
    return results


def _focused_on(item: ChecklistItem, stated_reason: str) -> ChecklistItem:
    """A letter may name no clause, so its own words point the search at the right one."""
    return replace(item, search_query=stated_reason, keywords=stated_reason)


def _generate_checks(evidence: Evidence, reader: Reader, cited: ChecklistItem) -> tuple[ChecklistItem, ...]:
    print("Generating checks from the clause", file=sys.stderr, flush=True)
    answer = reader.answer(CONDITIONS_QUESTION, evidence.passages(cited)[0])
    if answer.is_unclear or answer.is_not_found:
        return ()
    facts = [fact.strip() for fact in (answer.value or "").split("|") if fact.strip()]
    return tuple(generated_item(number, fact) for number, fact in enumerate(facts[:MAX_GENERATED_CHECKS], start=1))


def _review_any_reason(
    evidence: Evidence, reader: Reader, reason: RejectionReason, stated_reason: str, other_reason: str | None
) -> Review:
    checklist = tuple(_focused_on(item, stated_reason) for item in ANY_REASON_CHECKLIST)
    by_id = _check_items(checklist, evidence, reader)
    cited = next(item for item in checklist if item.id == "cited_clause")
    generated = _generate_checks(evidence, reader, cited)
    by_id |= _check_items(generated, evidence, reader)
    outcome = limit_to_checked_reason(any_reason_outcome(by_id, [item.id for item in generated]), other_reason)
    return Review(
        outcome.verdict,
        reason,
        outcome.next_step,
        list(by_id.values()),
        None,
        outcome.decided_by,
        conditions=outcome.conditions,
        other_reason=other_reason,
        checks_generated=True,
    )


def review_claim(customer_file: CustomerFile, reader: Reader, embedder: Embedder | None = None) -> Review:
    documents = customer_file.documents()
    reason, stated_reason = _read_rejection_reason(documents, reader)
    if reason is None:
        return Review(
            Verdict.CANNOT_TELL,
            None,
            "The Rejection Reason could not be identified. Read the rejection letter, or ask the insurer to state it.",
        )
    other_reason = _read_other_reason(documents, reader)
    evidence = Evidence(customer_file, embedder)
    if reason is RejectionReason.OTHER:
        return _review_any_reason(evidence, reader, reason, stated_reason, other_reason)

    by_id = _check_items(CHECKLISTS[reason], evidence, reader)
    _flag_shared_quote(by_id)

    decide = DECIDERS[reason]
    rule_sets = _rule_sets(by_id)
    checks = [_date_check(by_id, rules) for rules in rule_sets]
    outcomes = [
        limit_to_checked_reason(decide(by_id, check, rules), other_reason) for check, rules in zip(checks, rule_sets)
    ]
    outcome = outcomes[-1]
    return Review(
        outcome.verdict,
        reason,
        outcome.next_step,
        list(by_id.values()),
        checks[-1],
        outcome.decided_by,
        conditions=outcome.conditions,
        other_reason=other_reason,
        rule_versions=list(rule_sets[-1].values()),
        transition_flag=_transition_flag(outcome, outcomes[:-1]),
    )
