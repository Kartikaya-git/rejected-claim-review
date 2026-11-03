# Checking Rejected Health Insurance Claims

Upload the documents of a rejected Indian health insurance claim, and this app checks whether the insurer's stated reason holds up, with the clause and evidence behind its result. It returns **Reason Supported**, **Reason Not Supported** or **Cannot Tell**. It gives a first review, and a claims advisor decides.

## Run the app

You need Python 3.12 or newer, and a free API key from [console.groq.com](https://console.groq.com).

```bash
git clone https://github.com/Kartikaya-git/rejected-claim-review.git
cd rejected-claim-review
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/streamlit run app.py
```

## Test it

1. Pick a folder in [test_cases](test_cases).
2. Upload its PDFs into the matching boxes:

| Box in the app | File |
|---|---|
| Rejection letter | `rejection_letter.pdf` |
| Policy wording | [`test_cases/policy_wording.pdf`](test_cases/policy_wording.pdf), the same for every case |
| Policy certificate | `policy_certificate.pdf` |
| Hospital summary | `discharge_summary.pdf` |
| Application form | `application_form.pdf`, if the folder has one |

3. Paste your API key and click **Run Review**.
4. Compare the output with `result.txt` in that folder.

A review makes about 15 LLM calls and takes from under a minute to a few minutes, depending on rate limits. The first run also downloads a small embedding model. Groq's free tier allows only a few reviews a day per model, and the model's reading can vary between runs, so a result may differ from `result.txt`.

## Test cases and results

**All of these are made up:** the insurer, hospital, doctors and customers are fictional.

How to read the table:

| Column | Meaning |
|---|---|
| Expected | The right answer, decided when the case was written, before the tool ran on it |
| Tool | What the tool actually said in its live run, saved in that folder's `result.txt` |
| Match | **Yes:** the Verdict and the reason behind it both matched. **Verdict only:** the Verdict matched, but the tool reached it a different way. **No:** the Verdict was wrong |

| Case | What happens | Expected | Tool | Match |
|---|---|---|---|---|
| [1](test_cases/case_1_waiting_period_with_credit) | Kidney stone surgery rejected under a 24 month wait. The certificate has a 12 month credit the letter ignores | Reason Not Supported | Reason Not Supported | Yes |
| [2](test_cases/case_2_pre_existing_supported) | Diabetic foot ulcer inside the 36 month wait | Reason Supported | Reason Supported | Yes |
| [3](test_cases/case_3_waiver_in_certificate) | A certificate endorsement waives the wait for this condition | Reason Not Supported | Reason Not Supported | Yes |
| [4](test_cases/case_4_unrelated_illness) | Appendicitis rejected because the patient has diabetes | Reason Not Supported | Cannot Tell | **No** |
| [5](test_cases/case_5_missing_application_form) | Non-disclosure rejection with no application form | Cannot Tell | Cannot Tell | Yes |
| [6](test_cases/case_6_accident_exception) | Hip replacement rejected, but the clause does not apply to an accident | Reason Not Supported | Reason Not Supported | Yes |
| [7](test_cases/case_7_second_reason) | The Waiting Period fails on credit, but the letter also says late intimation | Cannot Tell | Cannot Tell | Yes |
| [8](test_cases/case_8_any_reason_exception) | No fixed checklist. Plastic surgery rejected, but it follows burns | Reason Not Supported | Reason Not Supported | Yes |
| [9](test_cases/case_9_any_reason_no_problem) | No fixed checklist. Cosmetic surgery, and the rejection looks right | Cannot Tell, no problem found | Cannot Tell, on unsettled checks | Verdict only |
| [10](test_cases/case_10_any_reason_date_check) | No fixed checklist. Rejected as late, but submitted 15 days after discharge. The LLM does the date arithmetic | Reason Not Supported | Reason Not Supported | Yes |

**Result: 9 of 10 Verdicts, one live run each,** and in case 9 the Verdict matched by a different route. Cases 1 to 6 ran on `qwen/qwen3.8-27b` and cases 7 to 10 on `openai/gpt-oss-120b`, because the free limit ran out. The app uses `openai/gpt-oss-120b` by default. I wrote these cases and their expected results, so they are not an unseen test.

Example output, from case 1:

```text
First-pass review, not advice or a decision.

Rejection reason: Waiting Period
Clause in question: 4.2 Specified Disease or Procedure Waiting Period (Code-Excl02)
Verdict: Reason Not Supported
Why: The Waiting Period is 24 months, with 12 months of credit, so it ends on 2026-01-15. Admission was on 2026-06-10, so it was complete.
Clause relied on: "excluded until the expiry of 24 months of continuous coverage" (clause 4.2, page 3)
Next step: The Waiting Period appears complete on these dates. Ask the insurer to confirm the dates it used.
Conditions for the rejection to hold:
  True: No waiver applies
  True: No exception in the clause applies
  True: The cited clause covers this illness
  False: The Waiting Period had not ended at admission
Decided by: period_not_ended
```

## Where it fails

- It has not yet given a correct result on a real ombudsman case, and there is no accuracy figure.
- Medical judgement can come back unclear, as in case 4.
- Weaker models reword quotes, the check rejects them, and reviews end in Cannot Tell.
- A real quote can be misread, so a person reviews every result.
- Checks generated for reasons with no fixed checklist have run on only three cases, and what they generate varies between runs. In those checks the LLM does its own date arithmetic, and its working is shown, so those results are not repeatable.
- Scanned PDFs do not work.
