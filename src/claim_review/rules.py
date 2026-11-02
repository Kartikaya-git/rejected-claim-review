from dataclasses import dataclass
from datetime import date

CIRCULAR_2024 = "https://mail.caalley.com/irda24/Master_Circular_on_Health_Insurance_Business_29052024.pdf"
INSURER_NOTE_2024 = "https://royalsundaram.in/assets/Websiteupdate-Healthregulations.pdf"
CIRCULAR_2020 = "https://taxguru.in/corporate-law/master-circular-standardization-health-insurance-products.html"
PRESS_2024 = "https://www.businesstoday.in/amp/personal-finance/insurance/story/irdai-reduces-pre-existing-disease-waiting-period-from-4-to-3-years-here-is-what-existing-policyholders-should-know-425325-2024-04-12"

NEW_RULES_FROM = date(2024, 4, 1)
EXISTING_PRODUCTS_DEADLINE = date(2024, 9, 30)


@dataclass(frozen=True)
class RuleVersion:
    id: str
    value: int
    valid_from: date | None
    valid_until: date | None
    source: str
    evidence: str


RULE_VERSIONS = (
    RuleVersion("ped_look_back_months", 48, None, date(2024, 3, 31), CIRCULAR_2020, "circular text, reproduced"),
    RuleVersion("ped_look_back_months", 36, NEW_RULES_FROM, None, INSURER_NOTE_2024, "insurer compliance note"),
    RuleVersion("moratorium_months", 96, None, date(2024, 3, 31), PRESS_2024, "press"),
    RuleVersion("moratorium_months", 60, NEW_RULES_FROM, None, CIRCULAR_2024, "circular text, reproduced"),
)


def rule_set(on: date, versions: tuple[RuleVersion, ...] = RULE_VERSIONS) -> dict[str, RuleVersion]:
    return {
        rule.id: rule
        for rule in versions
        if (rule.valid_from is None or rule.valid_from <= on) and (rule.valid_until is None or on <= rule.valid_until)
    }


def active_rule_sets(admission_date: date) -> list[dict[str, RuleVersion]]:
    """Existing products had until the deadline to comply, so both versions may apply in that window. Latest is last."""
    if NEW_RULES_FROM <= admission_date <= EXISTING_PRODUCTS_DEADLINE:
        return [rule_set(date(2024, 3, 31)), rule_set(admission_date)]
    return [rule_set(admission_date)]
