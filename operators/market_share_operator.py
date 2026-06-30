import re
from presidio_anonymizer.operators import Operator, OperatorType


def _fmt(v: float) -> str:
    """Format float: drop .0 suffix for whole numbers (47.5 → '47.5', 31.0 → '31')."""
    return str(int(v)) if v == int(v) else str(v)


class MarketShareRangeOperator(Operator):
    """Replace a market-share percentage with a ±2.5 pp range.

    Examples:
        '50%'                   → '[47.5-52.5]%'
        '1%'                    → '[0-3.5]%'   (clamped at 0)
        '99%'                   → '[96.5-100]%' (clamped at 100)
        'leader du marché'      → '[PART_DE_MARCHE]' (no numeric value found)

    Guardrails: range is always within [0, 100].
    Fallback: '[PART_DE_MARCHE]' when the matched text contains no percentage.
    """

    _PERCENT_RE = re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*%')
    _HALF_WIDTH = 2.5

    def operate(self, text: str, params: dict = None) -> str:
        match = self._PERCENT_RE.search(text)
        if not match:
            return "[PART_DE_MARCHE]"

        raw = match.group(1).replace(',', '.')
        try:
            value = float(raw)
        except ValueError:
            return "[PART_DE_MARCHE]"

        low = max(0.0, round(value - self._HALF_WIDTH, 4))
        high = min(100.0, round(value + self._HALF_WIDTH, 4))

        return f"[{_fmt(low)}-{_fmt(high)}]%"

    def validate(self, params: dict = None) -> None:
        pass

    def operator_name(self) -> str:
        return "market_share_range"

    def operator_type(self) -> OperatorType:
        return OperatorType.Anonymize
