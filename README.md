# Checking Rejected Health Insurance Claims

**Given a rejected Indian health insurance claim, this tool checks whether the insurer's stated reason holds up, and shows the clause and evidence behind its result.**

A claims advisor gives it the rejection letter, policy wording, certificate, hospital record and application form. It returns **Reason Supported**, **Reason Not Supported** or **Cannot Tell**, with quotes and a next step. It gives a first review, and the advisor decides.

It covers India, and uses only public and made-up data.

## What a review looks like

Real output from sample case 1:

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

## How to run it

You need Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev,app]"
```

Run the tests. They use saved answers, so they need no API key:

```bash
.venv/bin/python -m pytest
```

To run live reviews, add a free [Groq](https://console.groq.com) key to a file named `.groq_key`, which git ignores:

```bash
echo "your-key-here" > .groq_key
```

Open the review screen, then upload the PDFs from any folder in `examples/sample_cases`:

```bash
PYTHONPATH=src .venv/bin/streamlit run app.py
```

Or review one claim from the command line. Add `--json` to see every checklist item:

```bash
PYTHONPATH=src .venv/bin/python -m claim_review examples/waiting_period_synthetic.json
```

Rerun all the sample cases:

```bash
CLAIM_REVIEW_MODEL=qwen/qwen3.8-27b PYTHONPATH=src .venv/bin/python examples/run_sample_cases.py
```

**Model:** `openai/gpt-oss-120b` on Groq's free tier by default, falling back to smaller models when its daily allowance runs out. A review makes about 15 LLM calls and takes a few minutes. The free tier allows only a few reviews a day per model. The first run on a long policy also embeds it, which can take several minutes. To use another provider, set `CLAIM_REVIEW_PROVIDER` to `gemini`, `cerebras` or `openrouter`, with a matching `.gemini_key`, `.cerebras_key` or `.openrouter_key`. Those were not fully tested.

## Examples tested

[examples/sample_cases](examples/sample_cases) has nine complete claim files. Each folder holds the PDFs an advisor would have, plus the tool's saved review in `review_output.txt`, so you can read the results without a key. **All of them are made up:** the insurer, hospital, doctors and customers are fictional.

| Case | What happens | Expected | Tool | Match |
|---|---|---|---|---|
| [1](examples/sample_cases/case_1_waiting_period_with_credit) | Kidney stone surgery rejected under a 24 month wait. The certificate has a 12 month credit the letter ignores | Reason Not Supported | Reason Not Supported | Yes |
| [2](examples/sample_cases/case_2_pre_existing_supported) | Diabetic foot ulcer inside the 36 month wait | Reason Supported | Reason Supported | Yes |
| [3](examples/sample_cases/case_3_waiver_in_certificate) | A certificate endorsement waives the wait for this condition | Reason Not Supported | Reason Not Supported | Yes |
| [4](examples/sample_cases/case_4_unrelated_illness) | Appendicitis rejected because the patient has diabetes | Reason Not Supported | Cannot Tell | **No** |
| [5](examples/sample_cases/case_5_missing_application_form) | Non-disclosure rejection with no application form | Cannot Tell | Cannot Tell | Yes |
| [6](examples/sample_cases/case_6_accident_exception) | Hip replacement rejected, but the clause does not apply to an accident | Reason Not Supported | Reason Not Supported | Yes |
| [7](examples/sample_cases/case_7_second_reason) | The Waiting Period fails on credit, but the letter also says late intimation | Cannot Tell | Cannot Tell | Yes |
| [8](examples/sample_cases/case_8_any_reason_exception) | No fixed checklist. Plastic surgery rejected, but it follows burns | Reason Not Supported | Reason Not Supported | Yes |
| [9](examples/sample_cases/case_9_any_reason_no_problem) | No fixed checklist. Cosmetic surgery, and the rejection looks right | Cannot Tell, no problem found | Cannot Tell, no problem found | Yes |

**Result: 8 of 9, one live run each.** Cases 1 to 6 ran on `qwen/qwen3.8-27b` and cases 7 to 9 on `openai/gpt-oss-120b`, because the free limit ran out. I wrote these cases and their expected results, so they are not an unseen test.

Other tests, whose data is not in this repo:

| Test | Result |
|---|---|
| 6 planted traps on real public policy wordings, search only | This pipeline 6 of 6, plain chunk retrieval 2 of 6 |
| 30 clause searches on 6 real policies | Hybrid search 30 of 30, single methods about 28 |
| 5 real 2015 ombudsman awards, names removed, on free models | All Cannot Tell: none wrong, none answered |

## How it works

This is a **modified multi-hop RAG pipeline**. The LLM answers only from retrieved source text, and code makes the decision.

1. Policies are split by numbered clause, keeping clause and page.
2. Common rejection reasons have a fixed, tested checklist. Any other reason gets up to 5 checks the LLM generates from the cited clause.
3. Each check searches for evidence: exact lookup of cited clauses and codes, one hop to clauses they refer to, then BM25 and embeddings merged by Reciprocal Rank Fusion. A required item not found gets one retry.
4. The LLM answers one narrow question at a time with a quote, or says "unclear". Code rejects any quote not found in its source, and reads dates and months from the quote itself.
5. Code sets each condition to True, False or Unknown. Any False gives Reason Not Supported, all True gives Reason Supported, and anything else gives Cannot Tell.
6. Generated checks can raise a problem, but can never say Reason Supported, because they are not tested.
7. The advisor accepts or corrects the review.

## Where it fails

- **No correct result on a real award yet,** and no accuracy figure.
- **Medical judgement can come back unclear,** as in case 4, where it refused a case a person would settle easily.
- **Weaker models fail.** They reword quotes, the check rejects them, and reviews end in Cannot Tell.
- **A real quote can be misread.** A wrong answer can still look tidy and cited, so a person reviews each result.
- **Generated checks are barely tested:** two cases, on one clause. They can also leave something out with no sign of the gap.
- **The same question can give different answers,** even at temperature 0.
- **Some stored rules rest on secondary sources,** and a qualified person should confirm them.
- **Rulings on fairness are missed,** and scanned documents do not work.
