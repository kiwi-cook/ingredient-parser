import pytest

from ingredient_parser import PostProcessor
from ingredient_parser.postprocess import (
    IngredientAmount,
)


@pytest.fixture
def p():
    """Define a PostProcessor object to use for testing the PostProcessor
    class methods.
    """
    sentence = "2 14 ounce cans coconut milk"
    tokens = ["2", "14", "ounce", "can", "coconut", "milk"]
    labels = ["QTY", "QTY", "UNIT", "UNIT", "NAME", "NAME"]
    scores = [
        0.9991370577083561,
        0.9725378063405858,
        0.9978510889596651,
        0.9922350007952175,
        0.9886087821704076,
        0.9969237827902526,
    ]

    return PostProcessor(sentence, tokens, labels, scores)


class TestPostProcessor_fallback_pattern:
    def test_basic(self, p):
        """
        Test that a single IngredientAmount object with quantity "3" and
        unit "large handfuls" is returned.
        """

        tokens = ["3", "large", "handful", "cherry", "tomatoes"]
        labels = ["QTY", "UNIT", "UNIT", "NAME", "NAME"]
        scores = [0] * len(tokens)
        skip = []

        expected = [IngredientAmount(quantity="3", unit="large handfuls", confidence=0)]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected

    def test_no_quantity(self, p):
        """
        Test that a single IngredientAmount object with no quantity and
        unit "large handfuls" is returned.
        """

        tokens = ["1", "green", ",", "large", "pepper"]
        labels = ["QTY", "NAME", "COMMA", "UNIT", "NAME"]
        scores = [0] * len(tokens)
        skip = []

        expected = [IngredientAmount(quantity="1", unit=", large", confidence=0)]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected

    def test_comma_before_unit(self, p):
        """
        Test that a single IngredientAmount object with no quantity and
        unit "large handfuls" is returned.
        """

        tokens = ["bunch", "of", "basil", "leaves"]
        labels = ["UNIT", "COMMENT", "NAME", "NAME"]
        scores = [0] * len(tokens)
        skip = []

        expected = [IngredientAmount(quantity="", unit="bunch", confidence=0)]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected

    def test_approximate(self, p):
        """
        Test that a single IngredientAmount object with the APPROXIMATE flag set
        is returned
        """
        tokens = ["About", "2", "cup", "flour"]
        labels = ["COMMENT", "QTY", "UNIT", "NAME"]
        scores = [0] * len(tokens)
        skip = []

        expected = [
            IngredientAmount(
                quantity="2",
                unit="cups",
                confidence=0,
                APPROXIMATE=True,
            )
        ]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected

    def test_singular(self, p):
        """
        Test that a single IngredientAmount object with the SINGULAR flag set
        is returned
        """
        tokens = ["1", "28", "ounce", "can", "or", "400", "g", "chickpeas"]
        labels = ["QTY", "QTY", "UNIT", "UNIT", "COMMENT", "QTY", "UNIT", "NAME"]
        scores = [0] * len(tokens)
        skip = [0, 1, 2, 3]

        expected = [
            IngredientAmount(
                quantity="400",
                unit="g",
                confidence=0,
            )
        ]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected

    def test_singular_and_approximate(self, p):
        """
        Test that a single IngredientAmount object with the APPROXIMATE and
        SINGULAR flags set is returned
        """
        tokens = ["2", "bananas", ",", "each", "about", "4", "ounce"]
        labels = ["QTY", "NAME", "COMMA", "COMMENT", "COMMENT", "QTY", "UNIT"]
        scores = [0] * len(tokens)
        skip = []

        expected = [
            IngredientAmount(
                quantity="2",
                unit="",
                confidence=0,
            ),
            IngredientAmount(
                quantity="4",
                unit="ounces",
                confidence=0,
                SINGULAR=True,
                APPROXIMATE=True,
            ),
        ]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected

    def test_dozen(self, p):
        """
        Test that the token "dozen" is combined with the preceding QTY token in a
        single IngredientAmount object.
        """
        tokens = ["2", "dozen", "bananas", ",", "each", "about", "4", "ounce"]
        labels = ["QTY", "QTY", "NAME", "COMMA", "COMMENT", "COMMENT", "QTY", "UNIT"]
        scores = [0] * len(tokens)
        skip = []

        expected = [
            IngredientAmount(
                quantity="2 dozen",
                unit="",
                confidence=0,
            ),
            IngredientAmount(
                quantity="4",
                unit="ounces",
                confidence=0,
                SINGULAR=True,
                APPROXIMATE=True,
            ),
        ]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected

    def test_skip(self, p):
        """
        Test that the token "dozen" is combined with the preceding QTY token in a
        single IngredientAmount object.
        """
        tokens = ["2", "dozen", "bananas", ",", "each", "about", "4", "ounce"]
        labels = ["QTY", "QTY", "NAME", "COMMA", "COMMENT", "COMMENT", "QTY", "UNIT"]
        scores = [0] * len(tokens)
        skip = []

        expected = [
            IngredientAmount(
                quantity="2 dozen",
                unit="",
                confidence=0,
            ),
            IngredientAmount(
                quantity="4",
                unit="ounces",
                confidence=0,
                SINGULAR=True,
                APPROXIMATE=True,
            ),
        ]

        assert p._fallback_pattern(tokens, labels, scores, skip) == expected
