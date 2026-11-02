"""Writes synthetic sample cases as PDFs. The insurer, hospital, doctors and customers are all fictional."""
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).parent / "sample_cases"
INSURER = "Sahyog Health Insurance Co. Ltd."
NOTICE = "SYNTHETIC SAMPLE. Fictional insurer and people, made for a student assignment. Not a real document."
STYLES = getSampleStyleSheet()
BODY = ParagraphStyle("Body2", parent=STYLES["BodyText"], fontSize=10, leading=14, spaceAfter=7)
HEADING = ParagraphStyle("Heading", parent=STYLES["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=6)
TITLE = ParagraphStyle("Title2", parent=STYLES["Title"], fontSize=16, spaceAfter=10)


def footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(A4[0] / 2, 1.1 * cm, f"{NOTICE} Page {document.page}")
    canvas.restoreState()


def write_pdf(path: Path, title: str, blocks: list) -> None:
    story = [Paragraph(title, TITLE)]
    for block in blocks:
        if block == "PAGE":
            story.append(PageBreak())
        elif block.startswith("# "):
            story.append(Paragraph(block[2:], HEADING))
        else:
            story.append(Paragraph(block, BODY))
    SimpleDocTemplate(str(path), pagesize=A4, title=title, author="Synthetic sample").build(
        story, onFirstPage=footer, onLaterPages=footer
    )


POLICY = [
    "UIN: SAHHLIP00000V012526 (fictional). Issued by " + INSURER,
    "# 1. Preamble",
    "This Policy is a contract between You and Us. It is based on the Proposal and declaration You gave Us, which form part of this contract. "
    "We will pay for covered Hospitalisation expenses, subject to the terms, conditions and exclusions of this Policy, up to the Sum Insured shown in the Schedule.",
    "# 2. Definitions",
    "2.1 Accident means a sudden, unforeseen and involuntary event caused by external, visible and violent means.",
    "2.2 Any One Illness means a continuous period of illness, including relapse within 45 days from the date of last consultation with the Hospital.",
    "2.3 Cashless Facility means a facility extended by Us where payment for treatment is made directly to the Network Provider.",
    "2.4 Continuous Coverage means uninterrupted coverage under a health insurance policy, including any renewal within the Grace Period, without a break in cover.",
    "2.5 Day Care Treatment means medical treatment or surgery undertaken under general or local anaesthesia in less than 24 hours because of technological advancement.",
    "2.6 Grace Period means the specified period immediately following the premium due date during which premium may be paid to renew the Policy without loss of continuity benefits.",
    "2.7 Hospital means an institution established for inpatient care and day care treatment, registered with the local authorities, with qualified nursing staff and a qualified medical practitioner in charge round the clock.",
    "2.8 Hospitalisation means admission in a Hospital for a minimum period of 24 consecutive in-patient care hours, except for Day Care Treatment.",
    "2.9 Illness means a sickness or disease or pathological condition leading to the impairment of normal physiological function which manifests itself during the Policy Period and requires medical treatment.",
    "2.10 Medically Necessary Treatment means any treatment required for the medical management of the Illness, which is prescribed by a medical practitioner and conforms to professional standards.",
    "2.11 Migration means the right of a policyholder to transfer the credit gained for pre-existing diseases and specific waiting periods from one policy to another with the same insurer.",
    "2.12 Network Provider means a Hospital enlisted by Us to provide medical services through a Cashless Facility.",
    "2.13 Policy Period means the period between the commencement date and the expiry date shown in the Schedule.",
    "2.14 Portability means the right of a policyholder to transfer the credit gained for pre-existing diseases and specific waiting periods from one insurer to another.",
    "2.15 Pre-Existing Disease means any condition, ailment, injury or disease that is diagnosed by a physician not more than 36 months prior to the date of commencement of the Policy, "
    "or for which medical advice or treatment was recommended by, or received from, a physician not more than 36 months prior to the date of commencement of the Policy.",
    "2.16 Schedule means the Policy Schedule and Certificate issued to You, which includes any endorsement.",
    "2.17 Sum Insured means the amount stated in the Schedule, which is Our maximum liability for all claims in a Policy Year.",
    "PAGE",
    "# 3. Benefits",
    "3.1 In-patient Hospitalisation. We will pay for room rent, nursing, intensive care, surgeon and specialist fees, anaesthesia, medicines, diagnostics and operation theatre charges during Hospitalisation.",
    "3.2 Pre-Hospitalisation Expenses. We will pay relevant medical expenses incurred in the 60 days before admission, if the claim for Hospitalisation is admitted.",
    "3.3 Post-Hospitalisation Expenses. We will pay relevant medical expenses incurred in the 90 days after discharge, if the claim for Hospitalisation is admitted.",
    "3.4 Day Care Treatment. We will pay for Day Care Treatment listed on Our website.",
    "3.5 Road Ambulance. We will pay up to Rs. 3,000 per Hospitalisation for road ambulance transfer to a Hospital.",
    "3.6 Room Rent. Room rent is covered up to a single private room. There is no percentage limit on room rent under this Policy.",
    "# 4. Waiting Periods and Exclusions",
    "We shall not be liable to make any payment under this Policy for any claim directly or indirectly caused by, based on, or arising out of the following.",
    "4.1 Pre-Existing Diseases (Code-Excl01). Expenses related to the treatment of a Pre-Existing Disease and its direct complications shall be excluded until the expiry of 36 months of continuous coverage after the date of inception of the first Policy with Us. "
    "This exclusion applies afresh to any increase in Sum Insured, to the extent of the increase. If continuous coverage is maintained, coverage for the Pre-Existing Disease will start after the expiry of 36 months. "
    "Coverage after expiry of 36 months is subject to the Pre-Existing Disease being declared at the time of application and accepted by Us.",
    "4.2 Specified Disease or Procedure Waiting Period (Code-Excl02). Expenses related to the treatment of the listed conditions, surgeries and treatments shall be excluded until the expiry of 24 months of continuous coverage after the date of inception of the first Policy with Us. "
    "This does not apply if the condition arises from an Accident. The listed conditions are: benign enlargement of prostate; calculus diseases of the gall bladder and urogenital system, including kidney stones; cataract; hernia of all types; hydrocele; "
    "non-infective arthritis; piles, fissure and fistula in anus; polycystic ovarian disease; sinusitis; varicose veins; and joint replacement other than following an Accident.",
    "4.3 First 30 Days Waiting Period (Code-Excl03). Expenses related to the treatment of any Illness within 30 days from the first Policy commencement date shall be excluded, except claims arising due to an Accident.",
    "4.4 Investigation and Evaluation (Code-Excl04). Expenses related to any admission primarily for diagnostics and evaluation purposes are excluded.",
    "4.5 Rest Cure, Rehabilitation and Respite Care (Code-Excl05). Expenses related to any admission primarily for enforced bed rest and not for receiving treatment are excluded.",
    "4.6 Obesity and Weight Control (Code-Excl06). Expenses related to surgical treatment of obesity are excluded unless the conditions of Our underwriting guidelines are met.",
    "4.7 Cosmetic or Plastic Surgery (Code-Excl08). Expenses for cosmetic or plastic surgery are excluded unless required for reconstruction following an Accident, burns or cancer.",
    "4.8 Hazardous or Adventure Sports (Code-Excl09). Expenses related to any treatment necessitated due to participation as a professional in hazardous or adventure sports are excluded.",
    "4.9 Refractive Error (Code-Excl15). Expenses related to the treatment for correction of eyesight due to refractive error less than 7.5 dioptres are excluded.",
    "PAGE",
    "# 5. General Conditions",
    "5.1 Disclosure of Information. The Policy shall be void and all premium paid forfeited to Us in the event of misrepresentation, misdescription or non-disclosure of any material fact by You. "
    "A material fact includes any Pre-Existing Disease for which You have received treatment or advice.",
    "5.2 Moratorium Period. After completion of 60 continuous months of coverage, no policy and claim of health insurance shall be contestable on any grounds of non-disclosure or misrepresentation, except for established fraud. "
    "The moratorium applies to the Sum Insured of the first Policy, and the 60 months restart from the date of enhancement on any enhanced limit. Accrued credits gained under ported and migrated policies count for this period.",
    "5.3 Portability and Migration. You may port or migrate this Policy. Credits gained for Sum Insured, No Claim Bonus, specific waiting periods, the waiting period for Pre-Existing Diseases and the Moratorium Period in the previous policy shall be transferred. "
    "Any credit We accept is stated on Your Schedule.",
    "5.4 Renewal. The Policy shall ordinarily be renewable for life, except for established fraud or non-disclosure by You. A Grace Period of 30 days is allowed for premium payment. Coverage is not available during the period for which no premium is received.",
    "5.5 Endorsements. Any change to this Policy, including any waiver or reduction of a waiting period, is valid only if stated by Us on the Schedule or by written endorsement.",
    "5.6 Free Look Period. You have 30 days from the date of receipt of the Policy to review its terms and return it if You disagree.",
    "# 6. Claim Procedure",
    "6.1 Notification. You must notify Us within 48 hours of an emergency admission, or at least 48 hours before a planned admission.",
    "6.2 Reimbursement Claims. You must submit the claim form, discharge summary, bills, investigation reports and prescriptions within 30 days of discharge.",
    "6.3 Claim Decision. We shall settle or reject a claim within 15 days of receiving the last necessary document. Any rejection will be in writing and will state the specific clause relied on.",
    "# 7. Grievance Redressal",
    "7.1 You may contact Our Grievance Officer at the address on Your Schedule. If You are not satisfied, You may approach the Insurance Ombudsman of Your jurisdiction.",
]


def certificate(number: str, name: str, start: str, end: str, extra: list[str]) -> list:
    return [
        f"Policy number: {number}",
        f"Insurer: {INSURER}",
        "Product: Sahyog Family Health Plan",
        f"Policyholder and insured person: {name}",
        f"Cover start date: {start}",
        f"Current policy period ends: {end}",
        "Sum Insured: Rs. 5,00,000",
        "Premium paid: Rs. 21,480",
        "Break in cover: None",
        "# Special conditions and endorsements",
        *(extra or ["No special conditions or endorsements apply to this policy."]),
    ]


def letter(claim: str, policy: str, name: str, hospital_dates: str, body: list[str]) -> list:
    return [
        f"Claim number: {claim}", f"Policy number: {policy}", f"Dear {name},",
        f"We have reviewed your reimbursement claim for hospitalisation at City Care Hospital, Pune, {hospital_dates}.",
        *body,
        "If you are not satisfied, you may write to our Grievance Officer or approach the Insurance Ombudsman of your jurisdiction.",
        "Yours sincerely, Claims Department, " + INSURER,
    ]


def discharge(name: str, age: str, admitted: str, discharged: str, diagnosis: str, history: str, course: str) -> list:
    return [
        "City Care Hospital, Pune (fictional)",
        f"Patient: {name}, {age}", f"Date of admission: {admitted}", f"Date of discharge: {discharged}",
        f"Final diagnosis: {diagnosis}", f"Past history: {history}", f"Hospital course: {course}",
        "Advice on discharge: Continue medicines as prescribed. Review in outpatient clinic after 7 days.",
        "Treating doctor: Dr. A. Rao (fictional), Consultant",
    ]


def application(name: str, answers: list[str]) -> list:
    return [
        f"Proposer: {name}", "Product applied for: Sahyog Family Health Plan",
        "# Declaration of health",
        *answers,
        "I declare that the above statements are true and complete.",
    ]


CASES = {
    "case_1_waiting_period_with_credit": {
        "scenario": "Kidney stone surgery rejected under the 24 month Specified Disease waiting period. The certificate carries a 12 month portability credit that the letter ignores.",
        "expected": ("Reason Not Supported", "period_not_ended"),
        "certificate": certificate("SH/2025/100231", "Rohan Mehta", "15 January 2025", "14 January 2027", ["Portability credit accepted: 12 months of earlier continuous cover."]),
        "letter": letter("CLM-2026-55871", "SH/2025/100231", "Rohan Mehta", "from 10 June 2026 to 12 June 2026", [
            "Your claim is rejected under clause 4.2 of the policy, Code-Excl02. Kidney stones are subject to a 24 month waiting period, and your policy began on 15 January 2025. The admission therefore falls within the waiting period."]),
        "hospital": discharge("Rohan Mehta", "41 years, male", "10 June 2026", "12 June 2026", "Right renal calculus (10 mm) with hydronephrosis",
                              "No known chronic illness. No previous stone disease.", "Admitted with right flank pain. Underwent right ureteroscopic lithotripsy under spinal anaesthesia. Recovery uneventful."),
        "application": application("Rohan Mehta", ["Have you been diagnosed with or treated for any illness in the last 4 years? No.", "Previous health insurance: Yes, 12 months of continuous cover with an earlier insurer."]),
    },
    "case_2_pre_existing_supported": {
        "scenario": "Diabetic foot ulcer in the second policy year. Diabetes was diagnosed before cover and the 36 month period is not over, so the rejection holds.",
        "expected": ("Reason Supported", "all_conditions_true"),
        "certificate": certificate("SH/2025/100877", "Meera Iyer", "15 January 2025", "14 January 2027", []),
        "letter": letter("CLM-2026-56120", "SH/2025/100877", "Meera Iyer", "from 10 June 2026 to 16 June 2026", [
            "Your claim is rejected under clause 4.1 of the policy, Code-Excl01. Diabetes mellitus is a pre-existing disease, and the 36 month waiting period has not been completed."]),
        "hospital": discharge("Meera Iyer", "58 years, female", "10 June 2026", "16 June 2026", "Diabetic foot ulcer, left foot, with cellulitis",
                              "Type 2 diabetes mellitus, diagnosed on 5 March 2024, on oral medication.", "Admitted with a non-healing ulcer of the left foot, a complication of poorly controlled diabetes. Treated with debridement, intravenous antibiotics and insulin."),
        "application": application("Meera Iyer", ["Have you been diagnosed with or treated for any illness in the last 4 years? Yes. Type 2 diabetes mellitus."]),
    },
    "case_3_waiver_in_certificate": {
        "scenario": "Same type of rejection, but a written endorsement on the certificate waives the waiting period for this condition. A plain search on the letter would miss it.",
        "expected": ("Reason Not Supported", "no_waiver"),
        "certificate": certificate("SH/2025/101345", "Arjun Nair", "15 January 2025", "14 January 2027", ["Endorsement E-2: The pre-existing disease waiting period is waived for hypertension for this insured person, after underwriter review."]),
        "letter": letter("CLM-2026-56388", "SH/2025/101345", "Arjun Nair", "from 2 May 2026 to 5 May 2026", [
            "Your claim is rejected under clause 4.1 of the policy, Code-Excl01. Hypertension is a pre-existing disease, and the 36 month waiting period has not been completed."]),
        "hospital": discharge("Arjun Nair", "52 years, male", "2 May 2026", "5 May 2026", "Hypertensive urgency",
                              "Hypertension, diagnosed on 12 August 2023, on regular treatment.", "Admitted with severe headache and blood pressure of 210/120 mmHg. Controlled with intravenous medication, and medicines were adjusted."),
        "application": application("Arjun Nair", ["Have you been diagnosed with or treated for any illness in the last 4 years? Yes. Hypertension."]),
    },
    "case_4_unrelated_illness": {
        "scenario": "Appendicitis rejected because the patient has diabetes. The earlier condition is real but has no link to this illness.",
        "expected": ("Reason Not Supported", "same_illness"),
        "certificate": certificate("SH/2025/101902", "Farah Khan", "15 January 2025", "14 January 2027", []),
        "letter": letter("CLM-2026-56702", "SH/2025/101902", "Farah Khan", "from 10 June 2026 to 13 June 2026", [
            "Your claim is rejected under clause 4.1 of the policy, Code-Excl01. Diabetes mellitus is a pre-existing disease, and the 36 month waiting period has not been completed."]),
        "hospital": discharge("Farah Khan", "47 years, female", "10 June 2026", "13 June 2026", "Acute appendicitis",
                              "Type 2 diabetes mellitus, diagnosed on 5 March 2024, well controlled on medication.", "Admitted with acute right lower abdominal pain. Ultrasound confirmed acute appendicitis. Underwent laparoscopic appendicectomy. Recovery uneventful."),
        "application": application("Farah Khan", ["Have you been diagnosed with or treated for any illness in the last 4 years? Yes. Type 2 diabetes mellitus."]),
    },
    "case_5_missing_application_form": {
        "scenario": "Rejected for non-disclosure, but the application form is not in the Customer File, so the tool should say what is missing rather than guess.",
        "expected": ("Cannot Tell", "unknown_conditions"),
        "certificate": certificate("SH/2025/102260", "Vikram Singh", "15 January 2025", "14 January 2027", []),
        "letter": letter("CLM-2026-57015", "SH/2025/102260", "Vikram Singh", "from 20 June 2026 to 24 June 2026", [
            "Your claim is rejected under clause 5.1 of the policy, for non-disclosure of a material fact. Hospital records show that you had ischaemic heart disease before the policy began, and this was not disclosed in your proposal."]),
        "hospital": discharge("Vikram Singh", "61 years, male", "20 June 2026", "24 June 2026", "Unstable angina, ischaemic heart disease",
                              "Ischaemic heart disease, diagnosed on 9 November 2023, on medication.", "Admitted with chest pain on exertion. Coronary angiography showed disease of two vessels. Treated medically and discharged in stable condition."),
        "application": None,
    },
    "case_6_accident_exception": {
        "scenario": "Hip replacement rejected under the 24 month waiting period. Clause 4.2 says the waiting period does not apply to a condition arising from an Accident, and the records show a road accident.",
        "expected": ("Reason Not Supported", "no_exception"),
        "certificate": certificate("SH/2025/102611", "Sunita Rao", "15 January 2025", "14 January 2027", []),
        "letter": letter("CLM-2026-57340", "SH/2025/102611", "Sunita Rao", "from 3 August 2026 to 9 August 2026", [
            "Your claim is rejected under clause 4.2 of the policy, Code-Excl02. Joint replacement is subject to a 24 month waiting period, and your policy began on 15 January 2025. The admission therefore falls inside the waiting period."]),
        "hospital": discharge("Sunita Rao", "55 years, female", "3 August 2026", "9 August 2026", "Displaced fracture of the right neck of femur after a road traffic accident",
                              "No known chronic illness. No previous joint disease.", "Brought to emergency after a two wheeler collision on 3 August 2026. Underwent right total hip replacement. Recovery uneventful."),
        "application": application("Sunita Rao", ["Have you been diagnosed with or treated for any illness in the last 4 years? No."]),
    },
    "case_7_second_reason": {
        "scenario": "The Waiting Period reason fails on a 12 month credit, but the letter also rejects the claim for late intimation, which this tool does not check. The result must not read as a win.",
        "expected": ("Cannot Tell", "other_reason"),
        "certificate": certificate("SH/2025/103004", "Kabir Das", "15 January 2025", "14 January 2027", ["Portability credit accepted: 12 months of earlier continuous cover."]),
        "letter": letter("CLM-2026-57702", "SH/2025/103004", "Kabir Das", "from 12 June 2026 to 14 June 2026", [
            "Your claim is rejected under clause 4.2 of the policy, Code-Excl02. Kidney stones are subject to a 24 month waiting period, and your policy began on 15 January 2025. The admission therefore falls inside the waiting period.",
            "Separately, the claim was intimated to us 45 days after discharge, which is beyond the time limit in the policy."]),
        "hospital": discharge("Kabir Das", "39 years, male", "12 June 2026", "14 June 2026", "Left ureteric calculus (8 mm)",
                              "No known chronic illness. No previous stone disease.", "Admitted with left flank pain. Underwent left ureteroscopic lithotripsy. Recovery uneventful."),
        "application": application("Kabir Das", ["Have you been diagnosed with or treated for any illness in the last 4 years? No.", "Previous health insurance: Yes, 12 months of continuous cover."]),
    },
    "case_8_any_reason_exception": {
        "scenario": "A reason with no fixed checklist. Plastic surgery is rejected as cosmetic, but the clause allows reconstruction after burns, and the records show burns.",
        "expected": ("Reason Not Supported", "no_exception"),
        "certificate": certificate("SH/2025/103390", "Neha Kulkarni", "15 January 2025", "14 January 2027", []),
        "letter": letter("CLM-2026-58015", "SH/2025/103390", "Neha Kulkarni", "from 5 July 2026 to 11 July 2026", [
            "Your claim is rejected under clause 4.7 of the policy, as cosmetic or plastic surgery is excluded."]),
        "hospital": discharge("Neha Kulkarni", "34 years, female", "5 July 2026", "11 July 2026", "Post-burn contracture of the neck, needing reconstruction",
                              "Second degree burns to the neck from a kitchen fire on 2 February 2026.", "Admitted for release of the burn contracture with skin grafting. Recovery uneventful."),
        "application": application("Neha Kulkarni", ["Have you been diagnosed with or treated for any illness in the last 4 years? No."]),
    },
    "case_9_any_reason_no_problem": {
        "scenario": "A reason with no fixed checklist, where the rejection looks right. The generated checks may find no problem, but the tool must not say Reason Supported.",
        "expected": ("Cannot Tell", "no_problem_found"),
        "certificate": certificate("SH/2025/103712", "Rahul Bose", "15 January 2025", "14 January 2027", []),
        "letter": letter("CLM-2026-58290", "SH/2025/103712", "Rahul Bose", "from 18 July 2026 to 19 July 2026", [
            "Your claim is rejected under clause 4.7 of the policy, as cosmetic or plastic surgery is excluded."]),
        "hospital": discharge("Rahul Bose", "29 years, male", "18 July 2026", "19 July 2026", "Rhinoplasty for cosmetic reasons",
                              "No known illness. No injury. No burns.", "Elective rhinoplasty done at the patient's request to change the shape of the nose. Recovery uneventful."),
        "application": application("Rahul Bose", ["Have you been diagnosed with or treated for any illness in the last 4 years? No."]),
    },
}


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    policy = ROOT / "Sahyog_Family_Health_Plan_policy_wording.pdf"
    write_pdf(policy, "Sahyog Family Health Plan: Policy Wording", POLICY)
    manifest = []
    for name, case in CASES.items():
        folder = ROOT / name
        folder.mkdir(exist_ok=True)
        write_pdf(folder / "rejection_letter.pdf", "Claim Rejection Letter", case["letter"])
        write_pdf(folder / "policy_certificate.pdf", "Policy Schedule and Certificate", case["certificate"])
        write_pdf(folder / "discharge_summary.pdf", "Discharge Summary", case["hospital"])
        if case["application"]:
            write_pdf(folder / "application_form.pdf", "Proposal Form", case["application"])
        customer_file = {
            "_note": "Synthetic sample. Fictional insurer and people.",
            "rejection_letter": str(folder.relative_to(ROOT.parent.parent) / "rejection_letter.pdf"),
            "policy_wording": str(policy.relative_to(ROOT.parent.parent)),
            "policy_certificate": str(folder.relative_to(ROOT.parent.parent) / "policy_certificate.pdf"),
            "hospital_summary": str(folder.relative_to(ROOT.parent.parent) / "discharge_summary.pdf"),
            "application_form": str(folder.relative_to(ROOT.parent.parent) / "application_form.pdf") if case["application"] else "",
        }
        (folder / "customer_file.json").write_text(json.dumps(customer_file, indent=2))
        manifest.append({"case": name, "scenario": case["scenario"], "expected_verdict": case["expected"][0], "expected_decided_by": case["expected"][1]})
    (ROOT / "cases.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {len(manifest)} cases")


if __name__ == "__main__":
    main()
