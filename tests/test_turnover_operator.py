import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from operators.turnover_operator import TurnoverRangeOperator


@pytest.fixture
def op():
    return TurnoverRangeOperator()


class TestTurnoverRangeOperator:

    # --- Cas standard ---

    def test_one_million_eur(self, op):
        """Cas du cahier des charges: 1 000 000 EUR → [900 000 - 1 100 000] EUR"""
        assert op.operate("1 000 000 EUR") == "[900 000 - 1 100 000] EUR"

    def test_one_million_symbol(self, op):
        """Symbole € accepté à la place de EUR"""
        assert op.operate("1 000 000 €") == "[900 000 - 1 100 000] €"

    def test_five_million_abbreviated(self, op):
        """5M EUR → [4 500 000 - 5 500 000] EUR"""
        assert op.operate("5M EUR") == "[4 500 000 - 5 500 000] EUR"

    def test_500k_abbreviated(self, op):
        """500K EUR → [450 000 - 550 000] EUR"""
        assert op.operate("500K EUR") == "[450 000 - 550 000] EUR"

    def test_500k_plain(self, op):
        """500 000 EUR → [450 000 - 550 000] EUR"""
        assert op.operate("500 000 EUR") == "[450 000 - 550 000] EUR"

    def test_100k(self, op):
        """100 000 EUR → ±10% exact → [90 000 - 110 000] EUR"""
        assert op.operate("100 000 EUR") == "[90 000 - 110 000] EUR"

    def test_10k(self, op):
        """10 000 EUR → ±10% exact → [9 000 - 11 000] EUR"""
        assert op.operate("10 000 EUR") == "[9 000 - 11 000] EUR"

    # --- Valeurs non rondes : la fourchette reste un ±10% exact ---

    def test_1_5m_exact_margin(self, op):
        """1,5M EUR: ±10% exact = [1 350 000 - 1 650 000]"""
        assert op.operate("1,5M EUR") == "[1 350 000 - 1 650 000] EUR"

    def test_1_5m_dot_decimal(self, op):
        """1.5M (point comme séparateur décimal) identique à virgule"""
        assert op.operate("1.5M EUR") == "[1 350 000 - 1 650 000] EUR"

    # --- Montant dans une phrase (le keyword est inclus dans le span) ---

    def test_amount_in_phrase_fr(self, op):
        """Quand la phrase complète est matchée, l'opérateur extrait le montant"""
        assert op.operate("chiffre d'affaires de 1 000 000 EUR") == "[900 000 - 1 100 000] EUR"

    def test_amount_in_phrase_en(self, op):
        """turnover keyword variant"""
        assert op.operate("turnover: 2 000 000 EUR") == "[1 800 000 - 2 200 000] EUR"

    # --- Formats numériques alternatifs ---

    def test_dots_as_thousands_sep(self, op):
        """Format européen: 1.000.000 EUR (points séparateurs de milliers)"""
        assert op.operate("1.000.000 EUR") == "[900 000 - 1 100 000] EUR"

    def test_decimal_comma(self, op):
        """1 500 000,00 EUR (virgule décimale française)"""
        assert op.operate("1 500 000,00 EUR") == "[1 350 000 - 1 650 000] EUR"

    # --- Fallback ---

    def test_no_amount_returns_placeholder(self, op):
        """Aucun montant numérique → [CHIFFRE_AFFAIRES]"""
        assert op.operate("chiffre d'affaires en hausse") == "[CHIFFRE_AFFAIRES]"

    def test_empty_string(self, op):
        assert op.operate("") == "[CHIFFRE_AFFAIRES]"

    # --- Métadonnées de l'opérateur ---

    def test_operator_name(self, op):
        assert op.operator_name() == "turnover_range"

    def test_operator_type(self, op):
        from presidio_anonymizer.operators import OperatorType
        assert op.operator_type() == OperatorType.Anonymize
