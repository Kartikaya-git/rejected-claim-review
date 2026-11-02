from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from claim_review.rules import RuleVersion


class Verdict(str, Enum):
    REASON_SUPPORTED = "Reason Supported"
    REASON_NOT_SUPPORTED = "Reason Not Supported"
    CANNOT_TELL = "Cannot Tell"


class RejectionReason(str, Enum):
    WAITING_PERIOD = "waiting_period"
    PRE_EXISTING_DISEASE = "pre_existing_disease"
    OTHER = "other"


class Truth(str, Enum):
    TRUE = "True"
    FALSE = "False"
    UNKNOWN = "Unknown"


class ItemStatus(str, Enum):
    FOUND = "Found"
    NOT_FOUND = "Not Found"
    UNCLEAR = "Unclear"


class AnswerType(str, Enum):
    DATE = "date"
    MONTHS = "months"
    YES_NO = "yes_no"
    TEXT = "text"


@dataclass(frozen=True)
class CustomerFile:
    rejection_letter: str = ""
    policy_wording: str = ""
    policy_certificate: str = ""
    hospital_summary: str = ""
    application_form: str = ""
    unreadable: tuple[str, ...] = ()

    def documents(self) -> dict[str, str]:
        return {
            "rejection_letter": self.rejection_letter,
            "policy_wording": self.policy_wording,
            "policy_certificate": self.policy_certificate,
            "hospital_summary": self.hospital_summary,
            "application_form": self.application_form,
        }


@dataclass(frozen=True)
class Passage:
    source: str
    text: str
    location: str = ""


@dataclass(frozen=True)
class Answer:
    value: str | None = None
    quote: str | None = None
    source: str | None = None
    status: str = "found"

    @classmethod
    def not_found(cls) -> "Answer":
        return cls(status="not_found")

    @classmethod
    def unclear(cls) -> "Answer":
        return cls(status="unclear")

    @property
    def is_not_found(self) -> bool:
        return self.status == "not_found"

    @property
    def is_unclear(self) -> bool:
        return self.status == "unclear"


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    label: str
    question: str
    answer_type: AnswerType
    sources: tuple[str, ...]
    required: bool = True
    choices: tuple[str, ...] = ()
    context: tuple[str, ...] = ()
    search_query: str = ""
    keywords: str = ""
    codes: tuple[str, ...] = ()
    uses_illness: bool = False
    retries: bool = False


@dataclass(frozen=True)
class ItemResult:
    id: str
    label: str
    status: ItemStatus
    required: bool
    value: str | None = None
    quote: str | None = None
    source: str | None = None
    note: str | None = None
    location: str | None = None
    search_trace: tuple[str, ...] = ()


@dataclass(frozen=True)
class Condition:
    id: str
    label: str
    truth: Truth
    why: str
    next_step: str
    evidence: str | None = None


@dataclass(frozen=True)
class DateCheck:
    cover_start: date
    admission_date: date
    waiting_months: int | None
    credit_months: int
    period_ends: date | None
    period_passed: bool
    moratorium_months: int
    moratorium_ends: date
    moratorium_complete: bool


@dataclass(frozen=True)
class Review:
    verdict: Verdict | None
    rejection_reason: RejectionReason | None
    next_step: str
    items: list[ItemResult] = field(default_factory=list)
    date_check: DateCheck | None = None
    decided_by: str | None = None
    conditions: list[Condition] = field(default_factory=list)
    other_reason: str | None = None
    checks_generated: bool = False
    rule_versions: list[RuleVersion] = field(default_factory=list)
    transition_flag: str | None = None
