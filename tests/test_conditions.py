from claim_review.conditions import decide, verdict_from
from claim_review.models import Answer, Condition, Truth, Verdict
from claim_review.pipeline import review_claim
from claim_review.reader import RecordedReader


def condition(truth, id="c"):
    return Condition(id, "A condition", truth, "why", "ask")


def test_all_true_supports_the_reason():
    assert verdict_from([condition(Truth.TRUE), condition(Truth.TRUE)]) is Verdict.REASON_SUPPORTED


def test_one_false_decides_even_with_unknowns_beside_it():
    conditions = [condition(Truth.TRUE), condition(Truth.UNKNOWN), condition(Truth.FALSE)]

    assert verdict_from(conditions) is Verdict.REASON_NOT_SUPPORTED


def test_unknown_with_no_false_gives_cannot_tell():
    assert verdict_from([condition(Truth.TRUE), condition(Truth.UNKNOWN)]) is Verdict.CANNOT_TELL


def test_no_conditions_gives_cannot_tell():
    assert verdict_from([]) is Verdict.CANNOT_TELL


def test_first_false_condition_explains_the_result():
    outcome = decide([condition(Truth.TRUE, "a"), condition(Truth.FALSE, "b"), condition(Truth.FALSE, "c")], "ok")

    assert outcome.decided_by == "b"


def test_waiver_settles_the_claim_even_when_a_date_is_missing(customer_file, answers):
    """The flaw in the old rows: a missing date hid a waiver that already settled the claim."""
    from dataclasses import replace

    file = replace(customer_file, policy_certificate="Waiting period for kidney stones waived.")
    answers["waiver"] = Answer("yes", "Waiting period for kidney stones waived", "policy_certificate")
    answers["cover_start"] = Answer.not_found()

    review = review_claim(file, RecordedReader(answers))

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "no_waiver"


def test_review_shows_every_condition(customer_file, answers):
    review = review_claim(customer_file, RecordedReader(answers))

    assert {c.id for c in review.conditions} == {"no_waiver", "no_exception", "illness_under_clause", "period_not_ended"}
    assert all(c.truth is Truth.TRUE for c in review.conditions)


def test_an_exception_in_the_clause_means_the_reason_is_not_supported(customer_file, answers):
    from dataclasses import replace

    file = replace(customer_file, policy_wording=customer_file.policy_wording + " This does not apply if it arises from an Accident.")
    answers["clause_exception"] = Answer("yes", "This does not apply if it arises from an Accident", "policy_wording")

    review = review_claim(file, RecordedReader(answers))

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "no_exception"


def test_an_unclear_exception_blocks_reason_supported(customer_file, answers):
    answers["clause_exception"] = Answer.unclear()

    review = review_claim(customer_file, RecordedReader(answers))

    assert review.verdict is Verdict.CANNOT_TELL


def test_a_second_reason_stops_a_reason_not_supported(customer_file, answers):
    from dataclasses import replace

    file = replace(
        customer_file,
        rejection_letter=customer_file.rejection_letter + " The claim was also intimated late.",
        policy_certificate="Cover start date: 15 January 2023. Credit: 12 months.",
    )
    answers["continuity_credit_months"] = Answer("12", "Credit: 12 months", "policy_certificate")
    answers["other_reason"] = Answer("yes", "The claim was also intimated late", "rejection_letter")

    review = review_claim(file, RecordedReader(answers))

    assert review.verdict is Verdict.CANNOT_TELL
    assert review.decided_by == "other_reason"
    assert "The claim was also intimated late" in review.next_step
    assert "The claim was also intimated late" == review.other_reason


def test_a_second_reason_leaves_reason_supported_alone(customer_file, answers):
    from dataclasses import replace

    file = replace(customer_file, rejection_letter=customer_file.rejection_letter + " The claim was also intimated late.")
    answers["other_reason"] = Answer("yes", "The claim was also intimated late", "rejection_letter")

    review = review_claim(file, RecordedReader(answers))

    assert review.verdict is Verdict.REASON_SUPPORTED
    assert review.other_reason == "The claim was also intimated late"


def test_an_invented_second_reason_is_ignored(customer_file, answers):
    answers["other_reason"] = Answer("yes", "The policy had lapsed", "rejection_letter")

    review = review_claim(customer_file, RecordedReader(answers))

    assert review.other_reason is None


LATE_LETTER = "Your claim is rejected under clause 9.1 because it was intimated late."


def any_reason_answers():
    return {
        "rejection_reason": Answer("other", "it was intimated late", "rejection_letter"),
        "other_reason": Answer.not_found(),
        "cited_clause": Answer("9.1", "9.1 Intimation", "policy_wording"),
        "fraud_alleged": Answer.not_found(),
        "waiver": Answer.not_found(),
        "clause_exception": Answer.not_found(),
        "illness_treated": Answer("Fever", "Diagnosis: fever", "hospital_summary"),
        "rejection_conditions": Answer("Claim was intimated | Delay had no good reason", "9.1 Intimation", "policy_wording"),
        "generated_1": Answer("yes", "Intimated on 9 May", "hospital_summary"),
        "generated_2": Answer("yes", "Diagnosis: fever", "hospital_summary"),
    }


def any_reason_file():
    from claim_review.models import CustomerFile

    return CustomerFile(
        rejection_letter=LATE_LETTER,
        policy_wording="9.1 Intimation. Claims must be intimated within 30 days. This does not apply if you were unconscious.",
        policy_certificate="Cover start date: 15 January 2023.",
        hospital_summary="Diagnosis: fever. Intimated on 9 May. Patient was unconscious.",
    )


def test_any_reason_gets_a_review(customer_file):
    review = review_claim(any_reason_file(), RecordedReader(any_reason_answers()))

    assert {c.id for c in review.conditions} == {"no_waiver", "no_exception", "generated_1", "generated_2"}
    assert review.checks_generated is True


def test_generated_checks_can_never_say_reason_supported():
    review = review_claim(any_reason_file(), RecordedReader(any_reason_answers()))

    assert review.verdict is Verdict.CANNOT_TELL
    assert review.decided_by == "no_problem_found"


def test_a_generated_check_that_fails_means_reason_not_supported():
    answers = any_reason_answers()
    answers["generated_2"] = Answer("no", "Patient was unconscious", "hospital_summary")

    review = review_claim(any_reason_file(), RecordedReader(answers))

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "generated_2"


def test_the_letter_cannot_prove_its_own_claim():
    answers = any_reason_answers()
    answers["generated_1"] = Answer("yes", "it was intimated late", "rejection_letter")

    review = review_claim(any_reason_file(), RecordedReader(answers))

    assert next(c for c in review.conditions if c.id == "generated_1").truth is Truth.UNKNOWN


def test_an_exception_defeats_any_reason():
    answers = any_reason_answers()
    answers["clause_exception"] = Answer("yes", "This does not apply if you were unconscious", "policy_wording")

    review = review_claim(any_reason_file(), RecordedReader(answers))

    assert review.verdict is Verdict.REASON_NOT_SUPPORTED
    assert review.decided_by == "no_exception"


def test_no_generated_checks_gives_cannot_tell():
    answers = any_reason_answers()
    answers["rejection_conditions"] = Answer.unclear()

    review = review_claim(any_reason_file(), RecordedReader(answers))

    assert review.verdict is Verdict.CANNOT_TELL
    assert review.decided_by == "unknown_conditions"


def test_fraud_stays_with_a_person_for_any_reason():
    answers = any_reason_answers()
    answers["fraud_alleged"] = Answer("yes", "it was intimated late", "rejection_letter")
    answers["generated_2"] = Answer("no", "Patient was unconscious", "hospital_summary")

    review = review_claim(any_reason_file(), RecordedReader(answers))

    assert review.verdict is Verdict.CANNOT_TELL
    assert review.decided_by == "fraud_alleged"


def test_generated_checks_are_capped():
    answers = any_reason_answers()
    answers["rejection_conditions"] = Answer(" | ".join(f"Fact {n}" for n in range(1, 9)), "9.1 Intimation", "policy_wording")
    for n in range(1, 9):
        answers[f"generated_{n}"] = Answer("yes", "Diagnosis: fever", "hospital_summary")

    review = review_claim(any_reason_file(), RecordedReader(answers))

    assert len(review.conditions) == 7
