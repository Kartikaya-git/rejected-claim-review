from datetime import date

import pytest

from claim_review.models import Answer, CustomerFile


@pytest.fixture
def customer_file():
    return CustomerFile(
        rejection_letter="Your claim is rejected under clause 4.2, as kidney stones have a 24 month waiting period.",
        policy_wording=(
            "4.2 Specific illness waiting period. Kidney stones are excluded until 24 months "
            "of continuous cover have passed. "
            "7.1 Credit for prior cover. Months of earlier continuous cover reduce waiting periods."
        ),
        policy_certificate="Cover start date: 15 January 2023. Break in cover: None.",
        hospital_summary="Diagnosis: renal calculi. Date of admission: 10 June 2024.",
    )


def base_answers():
    """Reader answers for a claim inside its Waiting Period."""
    return {
        "rejection_reason": Answer("waiting_period", "kidney stones have a 24 month waiting period", "rejection_letter"),
        "waiting_clause": Answer(
            "4.2 Specific illness waiting period",
            "4.2 Specific illness waiting period. Kidney stones are excluded until 24 months",
            "policy_wording",
        ),
        "waiting_months": Answer("24", "excluded until 24 months of continuous cover", "policy_wording"),
        "continuity_credit_months": Answer.not_found(),
        "waiver": Answer.not_found(),
        "cover_start": Answer(date(2023, 1, 15).isoformat(), "Cover start date: 15 January 2023", "policy_certificate"),
        "break_in_cover": Answer.not_found(),
        "illness_treated": Answer("Kidney stones", "Diagnosis: renal calculi", "hospital_summary"),
        "admission_date": Answer(date(2024, 6, 10).isoformat(), "Date of admission: 10 June 2024", "hospital_summary"),
        "illness_under_clause": Answer("yes", "Diagnosis: renal calculi", "hospital_summary"),
        "clause_exception": Answer.not_found(),
        "other_reason": Answer.not_found(),
    }


@pytest.fixture
def answers():
    return base_answers()
