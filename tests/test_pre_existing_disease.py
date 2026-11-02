from dataclasses import replace
from datetime import date

import pytest

from claim_review.models import Answer, CustomerFile, ItemStatus, RejectionReason, Verdict
from claim_review.pipeline import review_claim
from claim_review.reader import RecordedReader
from claim_review.rules import RULE_VERSIONS, RuleVersion, active_rule_sets, rule_set


@pytest.fixture
def ped_file():
    return CustomerFile(
        rejection_letter="Your claim is rejected under clause 6.1 as diabetes is a pre-existing disease and the waiting period applies.",
        policy_wording=(
            "3.1 Pre-existing Disease means any condition diagnosed by a physician not more than 36 months prior to commencement. "
            "6.1 Pre-existing Diseases (Code-Excl01): expenses are excluded until the expiry of 36 months of continuous coverage. "
            "8.2 Moratorium period: after 60 months of continuous coverage no look back applies."
        ),
        policy_certificate="Cover start date: 15 January 2025. Break in cover: None.",
        hospital_summary="Diabetic foot ulcer. Date of admission: 10 June 2026. Known diabetic, diagnosed on 5 March 2024.",
        application_form="Medical history declared: none.",
    )


@pytest.fixture
def ped_answers():
    return {
        "rejection_reason": Answer("pre_existing_disease", "diabetes is a pre-existing disease", "rejection_letter"),
        "rejection_basis": Answer("waiting_period", "the waiting period applies", "rejection_letter"),
        "clause_exception": Answer.not_found(),
        "other_reason": Answer.not_found(),
        "ped_definition": Answer("3.1", "3.1 Pre-existing Disease means", "policy_wording"),
        "ped_exclusion": Answer("6.1", "6.1 Pre-existing Diseases (Code-Excl01)", "policy_wording"),
        "waiting_months": Answer("36", "until the expiry of 36 months", "policy_wording"),
        "moratorium_clause": Answer("8.2", "8.2 Moratorium period", "policy_wording"),
        "continuity_credit_months": Answer.not_found(),
        "waiver": Answer.not_found(),
        "cover_start": Answer("2025-01-15", "Cover start date: 15 January 2025", "policy_certificate"),
        "break_in_cover": Answer.not_found(),
        "illness_treated": Answer("Diabetic foot ulcer", "Diabetic foot ulcer", "hospital_summary"),
        "admission_date": Answer("2026-06-10", "Date of admission: 10 June 2026", "hospital_summary"),
        "condition_before_cover": Answer("yes", "Known diabetic", "hospital_summary"),
        "prior_condition_date": Answer("2024-03-05", "diagnosed on 5 March 2024", "hospital_summary"),
        "same_condition": Answer("yes", "Diabetic foot ulcer", "hospital_summary"),
        "declared_on_application": Answer("no", "Medical history declared: none", "application_form"),
    }


def run(file, answers):
    return review_claim(file, RecordedReader(answers))


def test_condition_inside_waiting_period_supports_the_reason(ped_file, ped_answers):
    review = run(ped_file, ped_answers)

    assert review.rejection_reason is RejectionReason.PRE_EXISTING_DISEASE
    assert review.verdict is Verdict.REASON_SUPPORTED
    assert review.decided_by == "all_conditions_true"


def test_no_evidence_of_earlier_condition_asks_for_the_insurers_evidence(ped_file, ped_answers):
    ped_answers["condition_before_cover"] = Answer.not_found()
    ped_answers["prior_condition_date"] = Answer.not_found()

    review = run(ped_file, ped_answers)

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "condition_existed"
    assert "evidence" in review.next_step


def test_new_illness_is_not_covered_by_the_exclusion(ped_file, ped_answers):
    ped_answers["same_condition"] = Answer("no", "Diabetic foot ulcer", "hospital_summary")

    assert run(ped_file, ped_answers).decided_by == "same_illness"


def test_an_unclear_medical_link_gives_cannot_tell(ped_file, ped_answers):
    ped_answers["same_condition"] = Answer.unclear()

    assert run(ped_file, ped_answers).verdict is Verdict.CANNOT_TELL


def test_diagnosis_older_than_the_look_back_is_not_pre_existing(ped_file, ped_answers):
    file = replace(ped_file, hospital_summary=ped_file.hospital_summary + " First found on 1 January 2020.")
    ped_answers["prior_condition_date"] = Answer("2020-01-01", "First found on 1 January 2020", "hospital_summary")

    review = run(file, ped_answers)

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "within_look_back"


def test_waiting_period_complete_means_reason_not_supported(ped_file, ped_answers):
    file = replace(ped_file, policy_certificate="Cover start date: 15 January 2022. Break in cover: None.")
    ped_answers["cover_start"] = Answer("2022-01-15", "Cover start date: 15 January 2022", "policy_certificate")
    ped_answers["prior_condition_date"] = Answer.not_found()

    review = run(file, ped_answers)

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "period_not_ended"


def test_non_disclosure_within_moratorium_supports_the_reason(ped_file, ped_answers):
    ped_answers["rejection_basis"] = Answer("non_disclosure", "pre-existing disease", "rejection_letter")

    assert run(ped_file, ped_answers).decided_by == "all_conditions_true"


def test_a_declared_condition_defeats_non_disclosure(ped_file, ped_answers):
    file = replace(ped_file, application_form="Declared: diabetes since 2024.")
    ped_answers["rejection_basis"] = Answer("non_disclosure", "pre-existing disease", "rejection_letter")
    ped_answers["declared_on_application"] = Answer("yes", "Declared: diabetes since 2024", "application_form")

    review = run(file, ped_answers)

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "not_declared"


def test_non_disclosure_without_the_application_form_gives_cannot_tell(ped_file, ped_answers):
    file = replace(ped_file, application_form="")
    ped_answers["rejection_basis"] = Answer("non_disclosure", "pre-existing disease", "rejection_letter")

    review = run(file, ped_answers)

    assert review.verdict is Verdict.CANNOT_TELL
    assert "application form" in review.next_step.lower()


def test_moratorium_blocks_a_non_disclosure_rejection(ped_file, ped_answers):
    file = replace(
        ped_file,
        policy_certificate="Cover start date: 15 January 2020. Break in cover: None.",
        hospital_summary="Diabetic foot ulcer. Date of admission: 10 June 2026. Known diabetic.",
    )
    ped_answers["cover_start"] = Answer("2020-01-15", "Cover start date: 15 January 2020", "policy_certificate")
    ped_answers["prior_condition_date"] = Answer.not_found()
    ped_answers["rejection_basis"] = Answer("non_disclosure", "pre-existing disease", "rejection_letter")

    review = run(file, ped_answers)

    assert review.date_check.moratorium_complete is True
    assert review.decided_by == "moratorium_not_complete"


def test_a_fraud_allegation_is_left_to_the_advisor(ped_file, ped_answers):
    ped_answers["rejection_basis"] = Answer("fraud", "pre-existing disease", "rejection_letter")

    review = run(ped_file, ped_answers)

    assert review.verdict is Verdict.CANNOT_TELL
    assert review.decided_by == "fraud_alleged"


def test_a_basis_outside_the_allowed_values_is_not_accepted(ped_file, ped_answers):
    ped_answers["rejection_basis"] = Answer("something else", "pre-existing disease", "rejection_letter")

    assert run(ped_file, ped_answers).verdict is Verdict.CANNOT_TELL


def test_review_shows_the_rule_versions_used(ped_file, ped_answers):
    review = run(ped_file, ped_answers)

    used = {rule.id: rule.value for rule in review.rule_versions}
    assert used["moratorium_months"] == 60
    assert used["ped_look_back_months"] == 36
    assert all(rule.source for rule in review.rule_versions)


def test_an_older_claim_uses_the_older_rule_version(ped_file, ped_answers):
    file = replace(
        ped_file,
        policy_certificate="Cover start date: 15 January 2019. Break in cover: None.",
        hospital_summary="Diabetic foot ulcer. Date of admission: 10 June 2023. Known diabetic.",
    )
    ped_answers["cover_start"] = Answer("2019-01-15", "Cover start date: 15 January 2019", "policy_certificate")
    ped_answers["admission_date"] = Answer("2023-06-10", "Date of admission: 10 June 2023", "hospital_summary")
    ped_answers["prior_condition_date"] = Answer.not_found()

    review = run(file, ped_answers)

    used = {rule.id: rule.value for rule in review.rule_versions}
    assert used["moratorium_months"] == 96
    assert review.transition_flag is None


def test_the_waiting_period_is_the_number_in_the_policy(ped_file, ped_answers):
    file = replace(ped_file, policy_wording=ped_file.policy_wording + " Exclusion lasts 48 months.")
    ped_answers["waiting_months"] = Answer("48", "Exclusion lasts 48 months", "policy_wording")

    review = run(file, ped_answers)

    assert review.date_check.waiting_months == 48
    assert review.date_check.period_ends.isoformat() == "2029-01-15"


def test_verdict_that_changes_in_the_transition_window_raises_a_flag(ped_file, ped_answers):
    """Cover of 62 months: past the new 60 month Moratorium, short of the old 96."""
    file = replace(
        ped_file,
        policy_certificate="Cover start date: 15 April 2019. Break in cover: None.",
        hospital_summary="Diabetic foot ulcer. Date of admission: 20 June 2024. Known diabetic.",
    )
    ped_answers["cover_start"] = Answer("2019-04-15", "Cover start date: 15 April 2019", "policy_certificate")
    ped_answers["admission_date"] = Answer("2024-06-20", "Date of admission: 20 June 2024", "hospital_summary")
    ped_answers["prior_condition_date"] = Answer.not_found()
    ped_answers["rejection_basis"] = Answer("non_disclosure", "pre-existing disease", "rejection_letter")

    review = run(file, ped_answers)

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.transition_flag is not None
    assert "Reason Supported" in review.transition_flag


def test_no_flag_when_the_transition_does_not_change_the_verdict(ped_file, ped_answers):
    file = replace(
        ped_file,
        policy_certificate="Cover start date: 15 January 2024. Break in cover: None.",
        hospital_summary="Diabetic foot ulcer. Date of admission: 20 June 2024. Known diabetic.",
    )
    ped_answers["cover_start"] = Answer("2024-01-15", "Cover start date: 15 January 2024", "policy_certificate")
    ped_answers["admission_date"] = Answer("2024-06-20", "Date of admission: 20 June 2024", "hospital_summary")
    ped_answers["prior_condition_date"] = Answer.not_found()

    assert run(file, ped_answers).transition_flag is None


def test_only_the_2024_window_has_two_active_rule_sets():
    assert len(active_rule_sets(date(2024, 3, 31))) == 1
    assert len(active_rule_sets(date(2024, 4, 1))) == 2
    assert len(active_rule_sets(date(2024, 9, 30))) == 2
    assert len(active_rule_sets(date(2024, 10, 1))) == 1


def test_adding_a_rule_version_leaves_older_ones_unchanged():
    newer = RuleVersion("moratorium_months", 48, date(2027, 1, 1), None, "test", "test")
    extended = RULE_VERSIONS + (newer,)

    assert rule_set(date(2023, 6, 10), extended)["moratorium_months"].value == 96
    assert rule_set(date(2028, 1, 1), extended)["moratorium_months"].value in (48, 60)


def test_a_proven_earlier_date_counts_as_an_earlier_condition(ped_file, ped_answers):
    """Seen live: the date was found, but the yes or no answer was missed."""
    ped_answers["condition_before_cover"] = Answer.not_found()

    assert run(ped_file, ped_answers).decided_by == "all_conditions_true"


def test_an_earlier_condition_with_no_medical_link_answer_gives_cannot_tell(ped_file, ped_answers):
    ped_answers["same_condition"] = Answer.not_found()

    assert run(ped_file, ped_answers).verdict is Verdict.CANNOT_TELL


def test_medical_questions_can_see_the_rejection_letter(ped_file, ped_answers):
    seen = {}

    class Spy(RecordedReader):
        def answer(self, question, passages):
            seen[question.id] = {p.source for p in passages}
            return super().answer(question, passages)

    review_claim(ped_file, Spy(ped_answers))

    assert "rejection_letter" in seen["same_condition"]
    assert "rejection_letter" in seen["condition_before_cover"]


def test_a_quote_from_context_cannot_prove_a_medical_answer(ped_file, ped_answers):
    ped_answers["same_condition"] = Answer("yes", "diabetes is a pre-existing disease", "rejection_letter")

    review = run(ped_file, ped_answers)

    assert next(i for i in review.items if i.id == "same_condition").status is ItemStatus.NOT_FOUND
    assert review.verdict is Verdict.CANNOT_TELL


def test_non_disclosure_needs_no_waiting_period(ped_file, ped_answers):
    ped_answers["rejection_basis"] = Answer("non_disclosure", "pre-existing disease", "rejection_letter")
    ped_answers["waiting_months"] = Answer.not_found()
    ped_answers["ped_exclusion"] = Answer.not_found()

    assert run(ped_file, ped_answers).decided_by == "all_conditions_true"


def test_waiting_basis_without_a_period_gives_cannot_tell(ped_file, ped_answers):
    ped_answers["waiting_months"] = Answer.not_found()

    review = run(ped_file, ped_answers)

    assert review.verdict is Verdict.CANNOT_TELL
    assert review.decided_by == "unknown_conditions"
