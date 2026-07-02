import re
import math
from presidio_anonymizer.operators import Operator, OperatorType

# Abbreviated form: "5M EUR", "1,5M €", "500K EUR"
_AMOUNT_MULT_RE = re.compile(
    r'\b(\d+(?:[.,]\d+)?)\s*(M|K|Md|G)\b',
    re.IGNORECASE,
)

# Plain integer/decimal with optional currency: "1 000 000 EUR", "1.000.000,50 €"
# First alternative handles thousands separators (space or dot); second handles bare numbers.
_AMOUNT_PLAIN_RE = re.compile(
    r'(\d{1,3}(?:[\s.]\d{3})+|\d+)(?:[,.](\d{1,2}))?\s*(EUR|USD|GBP|CHF|€|\$|£)?'
)

_CURRENCY_RE = re.compile(r'\b(EUR|USD|GBP|CHF)\b|([€\$£])')

_MULTIPLIERS = {
    'k': 1_000,
    'm': 1_000_000,
    'md': 1_000_000_000,
    'g': 1_000_000_000,
}


def _parse_amount(text: str):
    """Return (value: float, currency: str) or (None, '') if no amount found."""
    # Abbreviated form takes priority (avoids misreading "1.5" from "1.5M")
    m = _AMOUNT_MULT_RE.search(text)
    if m:
        raw = m.group(1).replace(',', '.')
        mult = _MULTIPLIERS.get(m.group(2).lower(), 1)
        try:
            value = float(raw) * mult
        except ValueError:
            return None, ''
        return value, _extract_currency(text)

    m = _AMOUNT_PLAIN_RE.search(text)
    if m:
        # Strip spaces and dots used as thousands separators
        int_clean = re.sub(r'[\s.]', '', m.group(1))
        dec_part = m.group(2) or ''
        raw = int_clean + ('.' + dec_part if dec_part else '')
        try:
            value = float(raw)
        except ValueError:
            return None, ''
        currency = m.group(3) or _extract_currency(text)
        return value, currency

    return None, ''


def _extract_currency(text: str) -> str:
    m = _CURRENCY_RE.search(text)
    return (m.group(1) or m.group(2)) if m else ''


def _fmt(n: int) -> str:
    """Format integer with space as thousands separator: 1000000 → '1 000 000'."""
    return f"{n:,}".replace(",", " ")


class TurnoverRangeOperator(Operator):
    """Replace a turnover / revenue amount with an exact ±10% range (total width 20%).

    Bounds are floor/ceil-ed to the nearest integer only, to absorb float
    precision noise — no rounding to a "clean" magnitude step, so the range
    always reflects exactly ±10% of the parsed value.

    Examples:
        '1 000 000 EUR'              → '[900 000 - 1 100 000] EUR'
        '5M EUR'                     → '[4 500 000 - 5 500 000] EUR'
        '500K €'                     → '[450 000 - 550 000] €'
        '1,5M EUR'                   → '[1 350 000 - 1 650 000] EUR'
        'chiffre d affaires de 2M'   → '[1 800 000 - 2 200 000]'
        'pas de montant'             → '[CHIFFRE_AFFAIRES]'
    """

    def operate(self, text: str, params: dict = None) -> str:
        value, currency = _parse_amount(text)
        if value is None or value <= 0:
            return "[CHIFFRE_AFFAIRES]"

        margin = value * 0.10
        low = int(math.floor(value - margin))
        high = int(math.ceil(value + margin))

        suffix = f" {currency}" if currency else ""
        return f"[{_fmt(low)} - {_fmt(high)}]{suffix}"

    def validate(self, params: dict = None) -> None:
        pass

    def operator_name(self) -> str:
        return "turnover_range"

    def operator_type(self) -> OperatorType:
        return OperatorType.Anonymize
