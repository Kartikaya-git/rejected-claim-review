"""Review Screen. Run with: streamlit run app.py"""
import os
import tempfile
from pathlib import Path

import streamlit as st

from claim_review.advisor import record_decision
from claim_review.documents import read_pdf
from claim_review.models import CustomerFile, ItemStatus, Verdict
from claim_review.pipeline import review_claim
from claim_review.summary import summarise
from claim_review.reader import DEFAULT_PROVIDER, PROVIDERS, LlmReader, ReaderError, load_api_key

DOCUMENTS = {
    "rejection_letter": ("Rejection letter", True),
    "policy_wording": ("Policy wording", True),
    "policy_certificate": ("Policy certificate", True),
    "hospital_summary": ("Hospital summary", True),
    "application_form": ("Application form (optional)", False),
}
STATUS_MARK = {ItemStatus.FOUND: "Found", ItemStatus.NOT_FOUND: "Not Found", ItemStatus.UNCLEAR: "Unclear"}
VERDICT_STYLE = {Verdict.REASON_SUPPORTED: st.success, Verdict.REASON_NOT_SUPPORTED: st.warning, Verdict.CANNOT_TELL: st.info}


def read_upload(upload) -> tuple[str, bool]:
    if upload.name.lower().endswith(".pdf"):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary:
            temporary.write(upload.getvalue())
            temporary.flush()
            document = read_pdf(Path(temporary.name))
        return document.text, document.readable
    return upload.getvalue().decode("utf-8", "ignore"), True


def collect_customer_file() -> CustomerFile:
    texts, unreadable = {}, []
    for name, (label, _) in DOCUMENTS.items():
        with st.expander(label, expanded=name == "rejection_letter"):
            upload = st.file_uploader(f"Upload {label}", type=["pdf", "txt"], key=f"file_{name}")
            pasted = st.text_area(f"Or paste {label}", key=f"text_{name}", height=100)
        if upload:
            text, readable = read_upload(upload)
            if not readable:
                unreadable.append(name)
                st.error(f"{label} has no readable text. It may be a scan, so it will show as Not Found.")
            texts[name] = text
        else:
            texts[name] = pasted
    return CustomerFile(**texts, unreadable=tuple(unreadable))


def show_summary(review) -> None:
    summary = summarise(review)
    show = VERDICT_STYLE.get(review.verdict, st.info)
    show(f"**{summary.verdict}**")
    st.write(f"**Rejection reason:** {summary.rejection_reason}")
    if summary.clause_cited:
        st.write(f"**Clause in question:** {summary.clause_cited}")
    st.write(f"**Why:** {summary.why}")
    if summary.clause_quote:
        st.markdown(f"**Clause relied on:**\n\n> {summary.clause_quote}")
        st.caption(summary.clause_location)
    st.write(f"**Next step:** {summary.next_step}")


def show_review(review) -> None:
    show_summary(review)
    if review.transition_flag:
        st.warning(f"Transition Flag: {review.transition_flag}")
    if review.other_reason:
        st.warning(f'Other reason in the letter, not checked: "{review.other_reason}"')
    if review.conditions:
        st.subheader("Conditions for the rejection to hold")
        for condition in review.conditions:
            st.write(f"**{condition.truth.value}:** {condition.label}")

    if review.date_check:
        check = review.date_check
        st.subheader("Date check")
        st.write(
            f"Cover start {check.cover_start}, admission {check.admission_date}. "
            f"Waiting Period: {check.waiting_months} months, "
            f"credit: {check.credit_months}. Ends: {check.period_ends}. Passed: {check.period_passed}. "
            f"Moratorium complete: {check.moratorium_complete}."
        )

    st.subheader("Evidence Checklist")
    for item in review.items:
        with st.expander(f"{STATUS_MARK[item.status]}: {item.label}"):
            if item.value:
                st.write(f"**Value:** {item.value}")
            if item.quote:
                st.markdown(f"> {item.quote}")
                st.caption(f"{item.source}{', ' + item.location if item.location else ''}")
            if item.note:
                st.caption(item.note)
            for step in item.search_trace:
                st.caption(step)

    if review.rule_versions:
        st.subheader("Rule Versions used")
        for rule in review.rule_versions:
            st.caption(f"{rule.id}: {rule.value}, evidence: {rule.evidence}. {rule.source}")


def main() -> None:
    st.set_page_config(page_title="Rejected Claim Review", layout="centered")
    st.title("Rejected Claim Review")
    st.warning("First-pass review, not advice or a decision. The Claims Advisor decides, and only public or synthetic data belongs here.")

    customer_file = collect_customer_file()
    if st.button("Run Review", type="primary"):
        missing = [label for name, (label, required) in DOCUMENTS.items() if required and not customer_file.documents()[name].strip()]
        if missing:
            st.info("Not provided: " + ", ".join(missing) + ". Their Checklist Items will show as Not Found.")
        try:
            provider = PROVIDERS[os.environ.get("CLAIM_REVIEW_PROVIDER", DEFAULT_PROVIDER)]
            reader = LlmReader(provider, load_api_key(provider))
            with st.spinner("Checking each Checklist Item. A long policy takes a few minutes."):
                st.session_state["review"] = review_claim(customer_file, reader)
        except ReaderError as error:
            st.error(str(error))

    review = st.session_state.get("review")
    if review:
        show_review(review)
        st.subheader("Advisor Decision")
        decision = st.radio("Your decision", ["Accept", "Correct"], horizontal=True)
        comment = st.text_input("Comment or correction")
        if st.button("Record decision"):
            record_decision(review.verdict.value if review.verdict else None, decision, comment)
            st.success("Advisor Decision recorded.")


if __name__ == "__main__":
    main()
