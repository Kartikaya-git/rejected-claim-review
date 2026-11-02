import zlib
from dataclasses import replace

import pytest
from pypdf import PdfWriter

from claim_review.documents import read_pdf
from claim_review.evidence import quote_in_source
from claim_review.models import Answer, ChecklistItem, AnswerType, CustomerFile, ItemStatus, Verdict
from claim_review.pipeline import review_claim
from claim_review.policy_index import build_index
from claim_review.reader import RecordedReader
from claim_review.search import PolicySearch, reciprocal_rank_fusion

FILLER = " ".join(f"General condition number {n} about premium payment and notices." for n in range(300))

POLICY = (
    "Table of contents\n1. Definitions ............ 3\n"
    "1. Definitions\n"
    "1.1 Hospital means an institution for inpatient care.\n"
    "Def. 15. Pre-Existing Disease means any condition diagnosed within 36 months before the policy began.\n"
    "\f2. Waiting Periods\n"
    "2.1 Specific waiting period (Code-Excl02): kidney stones are excluded for 24 months. Refer to Section 5.3 for credit.\n"
    "2.2 Pre-existing Diseases (Code-Excl01): expenses are excluded until the expiry of 36 months.\n"
    "\f3. Grievance\n"
    f"3.1 {FILLER}\n"
    "5.3 Credit for prior cover. Earlier continuous cover reduces waiting periods.\n"
    "X. Moratorium period: after sixty continuous months no look back would be applied.\n"
)


class WordEmbedder:
    """Stands in for the real model: shared words give similar vectors."""

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 256
            for word in text.lower().split():
                vector[zlib.crc32(word.encode()) % 256] += 1.0
            vectors.append(vector)
        return vectors


def clause_ids(clauses):
    return [c.id for c in clauses]


def test_index_splits_numbered_clauses_with_pages():
    index = build_index(POLICY)

    clause = index.by_id("2.1")
    assert "kidney stones" in clause.text
    assert clause.page == 2
    assert index.by_id("5.3").page == 3


def test_index_handles_other_heading_styles_and_skips_contents_lines():
    index = build_index(POLICY)

    assert "Pre-Existing Disease means" in index.by_id("Def. 15").text
    assert "Moratorium" in index.by_id("X").text
    assert not any("...." in c.text for c in index.clauses)


def test_index_keeps_long_roman_numerals():
    index = build_index("XX. Hospital means a place for treatment of patients.\nXXV. Pre-existing Disease means any earlier condition.\n")

    assert "Pre-existing" in index.by_id("XXV").text


def test_index_records_exclusion_codes():
    index = build_index(POLICY)

    assert index.by_code("Excl01").id == "2.2"
    assert index.by_code("excl 02").id == "2.1"


def test_long_clause_is_split_but_keeps_its_id():
    index = build_index(POLICY)

    parts = [c for c in index.clauses if c.id == "3.1"]
    assert len(parts) > 1
    assert all(len(c.text) <= 2200 for c in parts)


def search():
    return PolicySearch(build_index(POLICY), WordEmbedder())


def item(query, codes=()):
    return ChecklistItem("x", "X", "?", AnswerType.TEXT, ("policy_wording",), search_query=query, codes=codes)


def test_rrf_prefers_a_clause_ranked_well_in_both_lists():
    ranked = reciprocal_rank_fusion([["a", "b", "c"], ["c", "b", "a"], ["b", "x", "y"]])

    assert ranked[0] == "b"


def test_exact_code_is_found_first():
    found = search().find(item("anything at all", codes=("Excl01",)))

    assert found[0].id == "2.2"


def test_clause_cited_in_the_letter_is_found_first():
    found = search().find(item("premium", ()), letter="We rejected this under clause 2.1 of your policy.")

    assert found[0].id == "2.1"


def test_a_reference_inside_a_found_clause_is_followed():
    found = search().find(item("kidney stones waiting period", codes=("Excl02",)))

    assert "5.3" in clause_ids(found)


def test_search_finds_a_clause_without_any_code():
    found = search().find(item("moratorium period look back"))

    assert "X" in clause_ids(found)


def test_results_stay_within_the_size_limit():
    found = search().find(item("general condition premium payment notices"))

    assert sum(len(c.text) for c in found) <= 8000


def test_unreadable_pdf_is_reported(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    path = tmp_path / "scan.pdf"
    with open(path, "wb") as f:
        writer.write(f)

    assert read_pdf(path).readable is False


def test_broken_pdf_is_reported_not_raised(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")

    assert read_pdf(path).readable is False


def test_quotes_survive_ligatures_and_pdf_spacing():
    assert quote_in_source("waiting periods and beneﬁts", "waiting period s and\nbenefits")


def test_a_shortened_quote_passes_only_if_each_part_is_real():
    source = "Pre-Existing Diseases are excluded in full until the expiry of 36 months."

    assert quote_in_source("Pre-Existing Diseases ... until the expiry of 36 months", source)
    assert not quote_in_source("until the expiry ... Pre-Existing Diseases", source)
    assert not quote_in_source("Pre-Existing Diseases ... until the expiry of 12 months", source)
    assert not quote_in_source("...", source)


def test_a_changed_word_still_fails_the_quote_check():
    assert not quote_in_source("waiting periods apply", "waiting periods do not apply")


@pytest.fixture
def long_file():
    return CustomerFile(
        rejection_letter="Rejected under clause 2.1, as kidney stones have a 24 month waiting period.",
        policy_wording=POLICY,
        policy_certificate="Cover start date: 15 January 2023. Break in cover: None.",
        hospital_summary="Diagnosis: renal calculi. Date of admission: 10 June 2024.",
    )


class SearchSpy(RecordedReader):
    def __init__(self, answers):
        super().__init__(answers)
        self.passages = {}

    def answer(self, question, passages):
        self.passages[question.id] = passages
        return super().answer(question, passages)


def test_a_long_policy_sends_clauses_to_the_reader_and_shows_the_location(long_file, answers):
    answers["waiting_clause"] = Answer("2.1", "Specific waiting period (Code-Excl02)", "policy_wording")
    answers["waiting_months"] = Answer("24", "excluded for 24 months", "policy_wording")
    answers["rejection_reason"] = Answer("waiting_period", "kidney stones have a 24 month waiting period", "rejection_letter")
    answers["illness_aliases"] = Answer("kidney stones")
    reader = SearchSpy(answers)

    review = review_claim(long_file, reader, WordEmbedder())

    policy_text = "".join(p.text for p in reader.passages["waiting_months"] if p.source == "policy_wording")
    assert len(policy_text) < len(POLICY)
    assert "kidney stones" in policy_text
    found = next(i for i in review.items if i.id == "waiting_months")
    assert found.location == "clause 2.1, page 2"
    assert review.verdict is Verdict.REASON_SUPPORTED


def test_unreadable_document_is_named_on_the_review(customer_file, answers):
    file = replace(customer_file, hospital_summary="", unreadable=("hospital_summary",))
    answers.pop("illness_treated")
    answers.pop("admission_date")

    review = review_claim(file, RecordedReader(answers))

    admission = next(i for i in review.items if i.id == "admission_date")
    assert admission.status is ItemStatus.NOT_FOUND
    assert "no readable text" in admission.note


class ScriptedReader(RecordedReader):
    """Answers from a dict, but lets a test decide by what the Reader was shown."""

    def __init__(self, answers, waiting_answer):
        super().__init__(answers)
        self.waiting_answer = waiting_answer
        self.asked = []

    def answer(self, question, passages):
        self.asked.append(question.id)
        if question.id == "waiting_months":
            return self.waiting_answer(passages)
        return super().answer(question, passages)


def retry_answers(answers):
    answers["waiting_clause"] = Answer("2.1", "Specific waiting period (Code-Excl02)", "policy_wording")
    answers["rejection_reason"] = Answer("waiting_period", "kidney stones have a 24 month waiting period", "rejection_letter")
    answers["illness_aliases"] = Answer("kidney stones, urolithiasis")
    answers["refined_query"] = Answer("credit for prior cover earlier continuous cover")
    return answers


def found_on_second_search():
    calls = []

    def answer(passages):
        calls.append(passages)
        return Answer("24", "excluded for 24 months", "policy_wording") if len(calls) > 1 else Answer.not_found()

    return answer


def test_required_item_gets_one_retry_with_a_new_query(long_file, answers):
    reader = ScriptedReader(retry_answers(answers), found_on_second_search())

    review = review_claim(long_file, reader, WordEmbedder())

    result = next(i for i in review.items if i.id == "waiting_months")
    assert result.status is ItemStatus.FOUND
    assert reader.asked.count("waiting_months") == 2
    assert any("credit for prior cover" in step.lower() for step in result.search_trace)


def test_retry_with_no_new_clauses_stops_without_asking_again(long_file, answers):
    reader = ScriptedReader(retry_answers(answers), lambda passages: Answer.not_found())
    file = replace(long_file, policy_wording="1.1 Hospital means a place for inpatient care of ill people.\n" * 200)

    review = review_claim(file, reader, WordEmbedder())

    result = next(i for i in review.items if i.id == "waiting_months")
    assert result.status is ItemStatus.NOT_FOUND
    assert reader.asked.count("waiting_months") == 1
    assert any("no new clauses" in step.lower() for step in result.search_trace)


def test_only_one_retry_is_made(long_file, answers):
    reader = ScriptedReader(retry_answers(answers), lambda passages: Answer.not_found())

    review_claim(long_file, reader, WordEmbedder())

    assert reader.asked.count("waiting_months") <= 2


def test_optional_items_do_not_retry(long_file, answers):
    answers = retry_answers(answers)
    answers["waiting_months"] = Answer("24", "excluded for 24 months", "policy_wording")
    asked = []

    class Spy(RecordedReader):
        def answer(self, question, passages):
            asked.append(question.id)
            return super().answer(question, passages)

    review_claim(long_file, Spy(answers), WordEmbedder())

    assert asked.count("waiver") == 1


def test_illness_and_aliases_refine_dependent_searches(long_file, answers):
    answers = retry_answers(answers)
    answers["waiting_months"] = Answer("24", "excluded for 24 months", "policy_wording")

    review = review_claim(long_file, RecordedReader(answers), WordEmbedder())

    trace = next(i for i in review.items if i.id == "waiting_months").search_trace
    assert any("urolithiasis" in step for step in trace)
    assert any("clause 2.1" in step for step in trace)


def test_short_documents_need_no_aliases_or_search(customer_file, answers):
    answers.pop("rejection_basis", None)

    review = review_claim(customer_file, RecordedReader(answers))

    assert review.verdict is Verdict.REASON_SUPPORTED


def test_keyword_and_semantic_queries_are_separate():
    search_ = search()
    queries = []
    original = search_.keyword_ranking
    search_.keyword_ranking = lambda query: queries.append(query) or original(query)

    search_.find(ChecklistItem("x", "X", "?", AnswerType.TEXT, ("policy_wording",), search_query="meaning query", keywords="exact terms"))

    assert queries == ["exact terms"]


def test_clause_questions_can_see_the_letter_and_quotes_are_limited(long_file, answers):
    answers = retry_answers(answers)
    answers["waiting_months"] = Answer("24", "excluded for 24 months", "policy_wording")
    seen = {}

    class Spy(RecordedReader):
        def answer(self, question, passages):
            seen[question.id] = (question.text, {p.source for p in passages})
            return super().answer(question, passages)

    review_claim(long_file, Spy(answers), WordEmbedder())

    text, sources = seen["waiting_months"]
    assert "rejection_letter" in sources
    assert "Quote only from: policy_wording, policy_certificate." in text
