from dataclasses import replace

from claim_review.models import Answer, CustomerFile, Verdict
from claim_review.pipeline import review_claim
from claim_review.reader import RecordedReader
from claim_review.summary import format_summary, summarise


def review(customer_file, answers):
    return review_claim(customer_file, RecordedReader(answers))


def test_summary_states_the_answer_in_plain_words(customer_file, answers):
    summary = summarise(review(customer_file, answers))

    assert summary.verdict == "Reason Supported"
    assert summary.rejection_reason == "Waiting Period"
    assert summary.clause_cited == "4.2 Specific illness waiting period"
    assert "24 months" in summary.why
    assert "2025-01-15" in summary.why
    assert summary.clause_quote == "excluded until 24 months of continuous cover"


def test_waiver_summary_quotes_the_waiver(customer_file, answers):
    file = replace(customer_file, policy_certificate=customer_file.policy_certificate + " Waiting period for kidney stones waived.")
    answers["waiver"] = Answer("yes", "Waiting period for kidney stones waived", "policy_certificate")

    summary = summarise(review(file, answers))

    assert summary.verdict == "Reason Not Supported"
    assert summary.clause_quote == "Waiting period for kidney stones waived"
    assert "waiver" in summary.why.lower()


def test_cannot_tell_says_what_is_missing(customer_file, answers):
    answers["cover_start"] = Answer.not_found()

    summary = summarise(review(customer_file, answers))

    assert summary.verdict == "Cannot Tell"
    assert "Cover start date" in summary.why


def test_summary_is_readable_and_keeps_the_decided_by_as_a_detail(customer_file, answers):
    text = format_summary(review(customer_file, answers))

    assert text.index("Verdict: Reason Supported") < text.index("Decided by: all_conditions_true")
    assert "Clause relied on:" in text


def test_a_rejected_quote_gives_cannot_tell_not_a_false_absence():
    """Seen live: a rejected quote read as no earlier condition, giving a wrong Reason Not Supported."""
    file = CustomerFile(
        rejection_letter="The claim is rejected as diabetes is a pre-existing disease and the waiting period applies.",
        policy_wording="6.1 Pre-existing diseases are excluded until the expiry of 36 months of continuous coverage.",
        policy_certificate="Cover start date: 15 January 2025.",
        hospital_summary="Diagnosis: foot ulcer. Date of admission: 10 June 2026. Known diabetic.",
    )
    answers = {
        "rejection_reason": Answer("pre_existing_disease", "diabetes is a pre-existing disease", "rejection_letter"),
        "rejection_basis": Answer("waiting_period", "the waiting period applies", "rejection_letter"),
        "clause_exception": Answer.not_found(),
        "other_reason": Answer.not_found(),
        "ped_definition": Answer.not_found(),
        "ped_exclusion": Answer("6.1", "6.1 Pre-existing diseases", "policy_wording"),
        "waiting_months": Answer("36", "expiry of 36 months", "policy_wording"),
        "moratorium_clause": Answer.not_found(),
        "continuity_credit_months": Answer.not_found(),
        "waiver": Answer.not_found(),
        "cover_start": Answer("2025-01-15", "Cover start date: 15 January 2025", "policy_certificate"),
        "break_in_cover": Answer.not_found(),
        "illness_treated": Answer("foot ulcer", "Diagnosis: foot ulcer", "hospital_summary"),
        "admission_date": Answer("2026-06-10", "Date of admission: 10 June 2026", "hospital_summary"),
        "condition_before_cover": Answer("yes", "a line that is not in the record", "hospital_summary"),
        "prior_condition_date": Answer.not_found(),
        "same_condition": Answer.not_found(),
        "declared_on_application": Answer.not_found(),
    }

    assert review(file, answers).verdict is Verdict.CANNOT_TELL
