import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from operators.market_share_operator import MarketShareRangeOperator


@pytest.fixture
def op():
    return MarketShareRangeOperator()


class TestMarketShareRangeOperator:

    # --- Range calculation ---

    def test_midrange_value(self, op):
        """Standard case: 50% → [47.5-52.5]%"""
        assert op.operate("50%") == "[47.5-52.5]%"

    def test_integer_result(self, op):
        """When bounds are whole numbers they have no decimal part."""
        assert op.operate("30%") == "[27.5-32.5]%"

    def test_decimal_comma(self, op):
        """French comma decimal separator: 33,5% → [31-36]%"""
        assert op.operate("33,5%") == "[31-36]%"

    def test_decimal_dot(self, op):
        """English dot decimal separator: 33.5% → [31-36]%"""
        assert op.operate("33.5%") == "[31-36]%"

    def test_three_digit_percentage(self, op):
        """100% is a valid market share value."""
        assert op.operate("100%") == "[97.5-100]%"

    # --- Guardrails ---

    def test_lower_clamp_zero(self, op):
        """0% cannot go below 0: [0-2.5]%"""
        assert op.operate("0%") == "[0-2.5]%"

    def test_lower_clamp_near_zero(self, op):
        """1% − 2.5 < 0 → clamped to 0"""
        assert op.operate("1%") == "[0-3.5]%"

    def test_upper_clamp_hundred(self, op):
        """99% + 2.5 > 100 → clamped to 100"""
        assert op.operate("99%") == "[96.5-100]%"

    # --- Fallback behaviour ---

    def test_no_percentage_returns_placeholder(self, op):
        """When matched text has no numeric %, return [PART_DE_MARCHE]."""
        assert op.operate("leader du marché") == "[PART_DE_MARCHE]"

    def test_explicit_market_share_text(self, op):
        """Keyword-only match (e.g. 'part de marché') → placeholder."""
        assert op.operate("part de marché") == "[PART_DE_MARCHE]"

    # --- Percentage embedded in a phrase ---

    def test_percentage_in_phrase(self, op):
        """When the full phrase is matched, the % is still extracted."""
        assert op.operate("50% de part de marché") == "[47.5-52.5]%"

    def test_percentage_with_verb(self, op):
        """Verb + percentage phrase → range."""
        assert op.operate("détient 27%") == "[24.5-29.5]%"

    # --- Operator metadata ---

    def test_operator_name(self, op):
        assert op.operator_name() == "market_share_range"

    def test_operator_type(self, op):
        from presidio_anonymizer.operators import OperatorType
        assert op.operator_type() == OperatorType.Anonymize
