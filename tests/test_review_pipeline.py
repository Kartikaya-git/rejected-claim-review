from dataclasses import replace

from claim_review.models import Answer, ItemStatus, RejectionReason, Verdict
from claim_review.pipeline import review_claim
from claim_review.reader import RecordedReader


def run(customer_file, answers):
    return review_claim(customer_file, RecordedReader(answers))


def item(review, item_id):
    return next(i for i in review.items if i.id == item_id)


def test_inside_waiting_period_supports_the_reason(customer_file, answers):
    review = run(customer_file, answers)

    assert review.verdict is Verdict.REASON_SUPPORTED
    assert review.rejection_reason is RejectionReason.WAITING_PERIOD
    assert review.date_check.period_ends.isoformat() == "2025-01-15"
    assert review.date_check.period_passed is False
    assert review.decided_by == "all_conditions_true"


def test_waiver_in_certificate_means_reason_not_supported(customer_file, answers):
    file = replace(
        customer_file,
        policy_certificate=customer_file.policy_certificate + " Waiting period for kidney stones waived.",
    )
    answers["waiver"] = Answer("yes", "Waiting period for kidney stones waived", "policy_certificate")

    review = run(file, answers)

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "no_waiver"


def test_completed_waiting_period_means_reason_not_supported(customer_file, answers):
    file = replace(customer_file, hospital_summary="Date of admission: 16 January 2025.")
    answers["admission_date"] = Answer("2025-01-16", "Date of admission: 16 January 2025", "hospital_summary")
    answers["illness_treated"] = Answer("Kidney stones", "Date of admission: 16 January 2025", "hospital_summary")
    answers["illness_under_clause"] = Answer("yes", "Date of admission: 16 January 2025", "hospital_summary")

    review = run(file, answers)

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.date_check.period_passed is True


def test_admission_on_the_last_day_is_not_past_the_period(customer_file, answers):
    file = replace(customer_file, hospital_summary="Diagnosis: renal calculi. Date of admission: 14 January 2025.")
    answers["admission_date"] = Answer("2025-01-14", "Date of admission: 14 January 2025", "hospital_summary")

    assert run(file, answers).date_check.period_passed is False


def test_prior_cover_credit_shortens_the_period(customer_file, answers):
    file = replace(customer_file, policy_certificate=customer_file.policy_certificate + " Prior cover credit: 12 months.")
    answers["continuity_credit_months"] = Answer("12", "Prior cover credit: 12 months", "policy_certificate")

    review = run(file, answers)

    assert review.date_check.period_passed is True
    assert review.verdict is Verdict.REASON_NOT_SUPPORTED


def test_illness_outside_the_clause_means_reason_not_supported(customer_file, answers):
    answers["illness_under_clause"] = Answer("no", "Diagnosis: renal calculi", "hospital_summary")

    assert run(customer_file, answers).verdict is Verdict.REASON_NOT_SUPPORTED


def test_break_in_cover_gives_cannot_tell(customer_file, answers):
    file = replace(customer_file, policy_certificate=customer_file.policy_certificate + " Policy lapsed in March 2023.")
    answers["break_in_cover"] = Answer("yes", "Policy lapsed in March 2023", "policy_certificate")

    review = run(file, answers)

    assert review.verdict is Verdict.CANNOT_TELL
    assert review.decided_by == "unknown_conditions"


def test_missing_required_evidence_gives_cannot_tell_and_names_it(customer_file, answers):
    answers["cover_start"] = Answer.not_found()

    review = run(customer_file, answers)

    assert review.verdict is Verdict.CANNOT_TELL
    assert item(review, "cover_start").status is ItemStatus.NOT_FOUND
    assert "Cover start date" in review.next_step


def test_unclear_reading_question_gives_cannot_tell(customer_file, answers):
    answers["illness_under_clause"] = Answer.unclear()

    review = run(customer_file, answers)

    assert review.verdict is Verdict.CANNOT_TELL
    assert item(review, "illness_under_clause").status is ItemStatus.UNCLEAR


def test_fabricated_quote_makes_the_item_not_found(customer_file, answers):
    answers["waiting_months"] = Answer("24", "This sentence is not in the policy, 24 months", "policy_wording")

    review = run(customer_file, answers)

    assert item(review, "waiting_months").status is ItemStatus.NOT_FOUND
    assert review.verdict is Verdict.CANNOT_TELL


def test_a_quote_from_the_wrong_document_is_not_accepted(customer_file, answers):
    answers["cover_start"] = Answer("2023-01-15", "Cover start date: 15 January 2023", "hospital_summary")

    assert item(run(customer_file, answers), "cover_start").status is ItemStatus.NOT_FOUND


def test_a_date_comes_from_the_quote_not_the_model(customer_file, answers):
    answers["cover_start"] = Answer("2020-01-15", "Cover start date: 15 January 2023", "policy_certificate")

    assert item(run(customer_file, answers), "cover_start").value == "2023-01-15"


def test_a_quote_without_a_date_proves_nothing(customer_file, answers):
    answers["cover_start"] = Answer("2023-01-15", "Cover start date", "policy_certificate")

    assert item(run(customer_file, answers), "cover_start").status is ItemStatus.NOT_FOUND


def test_with_several_dates_the_models_choice_must_be_one_of_them(customer_file, answers):
    file = replace(customer_file, hospital_summary="Admitted on 10 June 2024, discharged on 12 June 2024. Diagnosis: renal calculi.")
    quote = "Admitted on 10 June 2024, discharged on 12 June 2024"
    answers["illness_treated"] = Answer("Kidney stones", "Diagnosis: renal calculi", "hospital_summary")
    answers["admission_date"] = Answer("2024-06-10", quote, "hospital_summary")
    assert item(run(file, answers), "admission_date").value == "2024-06-10"

    answers["admission_date"] = Answer("2024-06-11", quote, "hospital_summary")
    assert item(run(file, answers), "admission_date").status is ItemStatus.NOT_FOUND


def test_a_month_count_comes_from_the_quote_not_the_model(customer_file, answers):
    answers["waiting_months"] = Answer("12", "excluded until 24 months of continuous cover", "policy_wording")

    assert item(run(customer_file, answers), "waiting_months").value == "24"


def test_quote_matching_allows_for_line_wrapping(customer_file, answers):
    file = replace(customer_file, policy_certificate="Cover start\n  date: 15 January 2023.")

    assert item(run(file, answers), "cover_start").status is ItemStatus.FOUND


def test_an_undetermined_reason_gives_cannot_tell(customer_file, answers):
    answers["rejection_reason"] = Answer.unclear()

    assert run(customer_file, answers).verdict is Verdict.CANNOT_TELL


def test_missing_document_is_not_sent_to_the_reader(customer_file, answers):
    answers.pop("illness_treated")
    answers.pop("admission_date")
    file = replace(customer_file, hospital_summary="")

    review = run(file, answers)

    assert item(review, "admission_date").status is ItemStatus.NOT_FOUND
    assert review.verdict is Verdict.CANNOT_TELL


def test_review_language_never_says_the_insurer_is_right_or_wrong(customer_file, answers):
    answers["illness_under_clause"] = Answer("no", "Diagnosis: renal calculi", "hospital_summary")

    text = run(customer_file, answers).next_step.lower()

    assert "insurer is wrong" not in text
    assert "insurer is right" not in text


def test_an_unclear_waiver_blocks_reason_supported(customer_file, answers):
    answers["waiver"] = Answer.unclear()

    assert run(customer_file, answers).verdict is Verdict.CANNOT_TELL


def test_a_fabricated_waiver_is_not_believed(customer_file, answers):
    answers["waiver"] = Answer("yes", "All waiting periods are waived", "policy_certificate")

    review = run(customer_file, answers)

    assert item(review, "waiver").status is ItemStatus.NOT_FOUND
    assert review.verdict is Verdict.CANNOT_TELL


def test_a_quote_cannot_come_from_outside_the_items_documents(customer_file, answers):
    answers["waiting_months"] = Answer("24", "a 24 month waiting period", "rejection_letter")

    assert item(run(customer_file, answers), "waiting_months").status is ItemStatus.NOT_FOUND


def test_month_end_start_date_is_handled(customer_file, answers):
    file = replace(customer_file, policy_certificate="Cover start date: 31 January 2023.")
    answers["cover_start"] = Answer("2023-01-31", "Cover start date: 31 January 2023", "policy_certificate")
    answers["waiting_months"] = Answer("1", "1 month", "policy_certificate")
    file = replace(file, policy_certificate=file.policy_certificate + " Waiting period 1 month.")

    assert run(file, answers).date_check.period_ends.isoformat() == "2023-02-28"


def test_indian_short_dates_and_worded_periods_are_read(customer_file, answers):
    file = replace(
        customer_file,
        hospital_summary="Diagnosis: renal calculi. Admitted on 12.07.24.",
        policy_wording=customer_file.policy_wording + " Exclusion applies for two (2) years.",
    )
    answers["admission_date"] = Answer("2024-07-12", "Admitted on 12.07.24", "hospital_summary")
    answers["waiting_months"] = Answer("24", "applies for two (2) years", "policy_wording")

    review = run(file, answers)

    assert item(review, "admission_date").status is ItemStatus.FOUND
    assert item(review, "waiting_months").status is ItemStatus.FOUND


def test_credit_reported_as_the_waiting_period_is_not_trusted(customer_file, answers):
    """Seen live: an ambiguously worded question led the model to give the credit as the Waiting Period."""
    file = replace(customer_file, policy_certificate=customer_file.policy_certificate + " Prior cover credit: 12 months.")
    answers["waiting_months"] = Answer("12", "Prior cover credit: 12 months", "policy_certificate")
    answers["continuity_credit_months"] = Answer("12", "Prior cover credit: 12 months", "policy_certificate")

    review = run(file, answers)

    assert item(review, "waiting_months").status is ItemStatus.UNCLEAR
    assert review.verdict is Verdict.CANNOT_TELL


def test_a_bad_answer_is_asked_again_once(customer_file, answers):
    class Flaky(RecordedReader):
        calls = 0

        def answer(self, question, passages):
            if question.id == "cover_start":
                Flaky.calls += 1
                if Flaky.calls == 1:
                    return Answer("2023-01-15", "not in the document", "policy_certificate")
            return super().answer(question, passages)

    review = review_claim(customer_file, Flaky(answers))

    assert item(review, "cover_start").status is ItemStatus.FOUND
    assert Flaky.calls == 2


def test_a_date_the_model_adjusted_is_ignored(customer_file, answers):
    """Seen live: asked about continuous cover, the model adjusted the stated date for a 12 month credit."""
    answers["cover_start"] = Answer("2022-01-15", "Cover start date: 15 January 2023", "policy_certificate")

    review = run(customer_file, answers)

    assert item(review, "cover_start").value == "2023-01-15"
    assert review.date_check.cover_start.isoformat() == "2023-01-15"


def test_a_period_stated_in_days_is_read_as_months(customer_file, answers):
    file = replace(customer_file, policy_wording=customer_file.policy_wording + " No cover during the first 90 days.")
    answers["waiting_months"] = Answer("3", "No cover during the first 90 days", "policy_wording")

    assert item(run(file, answers), "waiting_months").value == "3"
