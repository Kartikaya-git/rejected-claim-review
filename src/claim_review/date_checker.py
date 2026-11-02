import calendar
from datetime import date

from claim_review.models import DateCheck


def add_months(start: date, months: int) -> date:
    total = start.month - 1 + months
    year, month = start.year + total // 12, total % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def check_cover(
    cover_start: date,
    admission_date: date,
    waiting_months: int | None,
    credit_months: int,
    moratorium_months: int,
) -> DateCheck:
    period_ends = None if waiting_months is None else add_months(cover_start, max(waiting_months - credit_months, 0))
    moratorium_ends = add_months(cover_start, max(moratorium_months - credit_months, 0))
    return DateCheck(
        cover_start=cover_start,
        admission_date=admission_date,
        waiting_months=waiting_months,
        credit_months=credit_months,
        period_ends=period_ends,
        period_passed=period_ends is not None and admission_date >= period_ends,
        moratorium_months=moratorium_months,
        moratorium_ends=moratorium_ends,
        moratorium_complete=admission_date >= moratorium_ends,
    )


def within_look_back(condition_date: date, cover_start: date, look_back_months: int) -> bool:
    return condition_date >= add_months(cover_start, -look_back_months)
