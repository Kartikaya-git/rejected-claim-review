from claim_review.models import AnswerType, ChecklistItem, RejectionReason

POLICY = ("policy_wording", "policy_certificate")

WAITING_PERIOD_CHECKLIST = (
    ChecklistItem(
        "illness_treated",
        "Illness treated",
        "What illness was treated in this admission?",
        AnswerType.TEXT,
        ("hospital_summary",),
    ),
    ChecklistItem(
        "waiting_clause",
        "Waiting Period clause",
        "Which clause sets the waiting period cited in the rejection letter? Give its number or title.",
        AnswerType.TEXT,
        POLICY,
        search_query="specific waiting period excluded until months of continuous cover",
        keywords="specific waiting period months excluded list",
        uses_illness=True,
        context=("rejection_letter",),
        codes=("Excl02",),
    ),
    ChecklistItem(
        "waiting_months",
        "Length of the Waiting Period",
        "How many months is the waiting period set by that clause? Report the length as stated. "
        "Do not subtract any credit for earlier cover.",
        AnswerType.MONTHS,
        POLICY,
        search_query="specific waiting period months excluded list of illnesses",
        keywords="waiting period months exclusion",
        uses_illness=True,
        context=("rejection_letter",),
        codes=("Excl02",),
    ),
    ChecklistItem(
        "continuity_credit_months",
        "Continuity benefit from earlier cover",
        "Does the certificate credit this customer with months of earlier continuous cover? Give only the months "
        "credited. If it states none, answer not_found.",
        AnswerType.MONTHS,
        ("policy_certificate",),
        required=False,
    ),
    ChecklistItem(
        "waiver",
        "Waiver or reduction",
        "Does the certificate or an add-on waive this waiting period for this customer? Answer yes only for a waiver "
        "that names this customer's illness or plan. Otherwise answer not_found.",
        AnswerType.YES_NO,
        POLICY,
        required=False,
        search_query="waiver of waiting period reduced optional cover add-on",
        keywords="waiver reduction waiting period optional cover",
    ),
    ChecklistItem(
        "cover_start",
        "Cover start date",
        "What cover start date does the certificate state? Report that date as written.",
        AnswerType.DATE,
        ("policy_certificate",),
    ),
    ChecklistItem(
        "break_in_cover",
        "Break in cover",
        "Was there any break or lapse in cover between the start date and admission? Answer yes or no.",
        AnswerType.YES_NO,
        ("policy_certificate", "rejection_letter"),
        required=False,
    ),
    ChecklistItem(
        "admission_date",
        "Admission date",
        "On what date was the patient admitted?",
        AnswerType.DATE,
        ("hospital_summary",),
    ),
    ChecklistItem(
        "clause_exception",
        "Exception in the clause",
        "Does the policy state an exception that stops the clause cited in the rejection letter applying, such as a "
        "cause or circumstance it says the clause does not cover, and do the records show this claim meets that "
        "exception? Answer yes only if both are true, and quote the exception. Answer unclear if the records do not "
        "settle whether it is met. Otherwise answer not_found.",
        AnswerType.YES_NO,
        POLICY,
        required=False,
        search_query="waiting period does not apply if except unless arising from",
        keywords="waiting period exception does not apply unless except",
        uses_illness=True,
        context=("rejection_letter", "hospital_summary"),
        codes=("Excl02",),
    ),
    ChecklistItem(
        "illness_under_clause",
        "Illness falls under the clause",
        "Does the treated illness fall under the waiting period clause cited in the rejection letter? "
        "Answer yes or no, or unclear if the documents do not settle it.",
        AnswerType.YES_NO,
        ("policy_wording", "hospital_summary"),
        context=("rejection_letter",),
        search_query="specific waiting period list of illnesses and treatments",
        keywords="waiting period list illnesses treatments",
        uses_illness=True,
        codes=("Excl02",),
    ),
)

SHARED_ITEM_IDS = ("continuity_credit_months", "waiver", "cover_start", "break_in_cover", "illness_treated", "admission_date")
_SHARED = {item.id: item for item in WAITING_PERIOD_CHECKLIST if item.id in SHARED_ITEM_IDS}

PRE_EXISTING_DISEASE_CHECKLIST = (
    ChecklistItem(
        "rejection_basis",
        "Basis of the rejection",
        "Does the letter rely on the pre-existing disease waiting period, on non-disclosure or misrepresentation, "
        "or on fraud? Answer waiting_period, non_disclosure or fraud.",
        AnswerType.TEXT,
        ("rejection_letter",),
        choices=("waiting_period", "non_disclosure", "fraud"),
    ),
    ChecklistItem(
        "ped_definition",
        "Definition of Pre-Existing Disease",
        "Which clause defines pre-existing disease? Give its number or title.",
        AnswerType.TEXT,
        ("policy_wording",),
        required=False,
        retries=True,
        search_query="pre-existing disease means condition diagnosed by a physician months prior to commencement",
        keywords="pre-existing condition disease means diagnosed physician",
    ),
    ChecklistItem(
        "ped_exclusion",
        "Pre-Existing Disease exclusion clause",
        "Which clause excludes pre-existing diseases? Give its number or title.",
        AnswerType.TEXT,
        POLICY,
        required=False,
        retries=True,
        search_query="pre-existing diseases excluded until expiry of months of continuous coverage",
        codes=("Excl01",),
    ),
    ChecklistItem(
        "waiting_months",
        "Pre-Existing Disease Waiting Period",
        "How many months is the pre-existing disease waiting period? Report the length as stated. "
        "Do not subtract any credit for earlier cover.",
        AnswerType.MONTHS,
        POLICY,
        required=False,
        retries=True,
        search_query="pre-existing diseases excluded until expiry of months of continuous coverage",
        codes=("Excl01",),
    ),
    ChecklistItem(
        "moratorium_clause",
        "Moratorium clause",
        "Which clause describes the moratorium period? Give its number or title.",
        AnswerType.TEXT,
        ("policy_wording",),
        required=False,
        search_query="moratorium period continuous coverage no look back",
        keywords="moratorium",
    ),
    _SHARED["continuity_credit_months"],
    _SHARED["waiver"],
    _SHARED["cover_start"],
    _SHARED["break_in_cover"],
    _SHARED["illness_treated"],
    _SHARED["admission_date"],
    ChecklistItem(
        "clause_exception",
        "Exception in the clause",
        "Does the policy state an exception that stops the clause cited in the rejection letter applying, such as a "
        "cause or circumstance it says the clause does not cover, and do the records show this claim meets that "
        "exception? Answer yes only if both are true, and quote the exception. Answer unclear if the records do not "
        "settle whether it is met. Otherwise answer not_found.",
        AnswerType.YES_NO,
        POLICY,
        required=False,
        search_query="pre-existing disease exclusion does not apply if except unless arising from",
        keywords="pre-existing exception does not apply unless except",
        uses_illness=True,
        context=("rejection_letter", "hospital_summary"),
        codes=("Excl01",),
    ),
    ChecklistItem(
        "condition_before_cover",
        "Condition existed before cover",
        "Do the records show that the condition relied on in the rejection letter was diagnosed or treated before "
        "the cover start date? Answer yes or no, or unclear if they do not settle it.",
        AnswerType.YES_NO,
        ("hospital_summary",),
        required=False,
        context=("rejection_letter", "policy_certificate"),
    ),
    ChecklistItem(
        "prior_condition_date",
        "Latest diagnosis or treatment before cover",
        "On what date before the cover start date was that condition most recently diagnosed or treated?",
        AnswerType.DATE,
        ("hospital_summary",),
        required=False,
        context=("rejection_letter", "policy_certificate"),
    ),
    ChecklistItem(
        "same_condition",
        "Illness is that condition or its complication",
        "Is the illness treated in this admission the same as, or a complication of, the condition relied on in the "
        "rejection letter? Answer yes or no, or unclear if the documents do not settle it.",
        AnswerType.YES_NO,
        ("hospital_summary",),
        required=False,
        context=("rejection_letter", "policy_certificate"),
    ),
    ChecklistItem(
        "declared_on_application",
        "Declared on the application",
        "Was this condition declared on the application form? Answer yes or no.",
        AnswerType.YES_NO,
        ("application_form",),
        required=False,
        context=("rejection_letter",),
    ),
)

CLAIM_DOCUMENTS = ("policy_wording", "policy_certificate", "hospital_summary", "application_form")

ANY_REASON_CHECKLIST = (
    _SHARED["illness_treated"],
    ChecklistItem(
        "cited_clause",
        "Clause relied on",
        "Which clause does the rejection letter rely on? Give its number or title.",
        AnswerType.TEXT,
        POLICY,
        required=False,
        retries=True,
        context=("rejection_letter",),
        search_query="clause cited in the rejection letter exclusion condition",
        keywords="exclusion condition clause",
        uses_illness=True,
    ),
    ChecklistItem(
        "fraud_alleged",
        "Fraud alleged",
        "Does the letter allege fraud or forged documents? Answer yes and quote it. Otherwise answer not_found.",
        AnswerType.YES_NO,
        ("rejection_letter",),
        required=False,
    ),
    ChecklistItem(
        "waiver",
        "Waiver or change to the clause",
        "Does the certificate or an add-on waive or change the clause relied on in the rejection letter for this "
        "customer? Answer yes only for a term that covers this claim, and quote it. Otherwise answer not_found.",
        AnswerType.YES_NO,
        POLICY,
        required=False,
        context=("rejection_letter",),
        search_query="waiver endorsement add-on optional cover changes this term",
        keywords="waiver endorsement add-on",
    ),
    ChecklistItem(
        "clause_exception",
        "Exception in the clause",
        "Does the policy state an exception that stops the clause cited in the rejection letter applying, such as a "
        "cause or circumstance it says the clause does not cover, and do the records show this claim meets that "
        "exception? Answer yes only if both are true, and quote the exception. Answer unclear if the records do not "
        "settle whether it is met. Otherwise answer not_found.",
        AnswerType.YES_NO,
        POLICY,
        required=False,
        search_query="does not apply if except unless arising from",
        keywords="exception does not apply unless except",
        uses_illness=True,
        context=("rejection_letter", "hospital_summary"),
    ),
)


def generated_item(number: int, fact: str) -> ChecklistItem:
    """The letter is context only, so an insurer's claim cannot prove itself."""
    return ChecklistItem(
        f"generated_{number}",
        fact,
        f"Do the documents show that this is true: {fact} Answer yes or no, and quote what shows it. Answer unclear "
        "if they do not settle it.",
        AnswerType.YES_NO,
        CLAIM_DOCUMENTS,
        required=False,
        context=("rejection_letter",),
        search_query=fact,
        keywords=fact,
        may_calculate=True,
    )


CHECKLISTS = {
    RejectionReason.WAITING_PERIOD: WAITING_PERIOD_CHECKLIST,
    RejectionReason.PRE_EXISTING_DISEASE: PRE_EXISTING_DISEASE_CHECKLIST,
}
