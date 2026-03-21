"""Tests for the expression parser engine (Pillar 2 Supplement – Part 6)."""

import math

import pytest

from src.engines.expression_parser import (
    ParseError,
    EvalError,
    Token,
    TokenType,
    evaluate,
    extract_dependencies,
    tokenize,
    validate,
)


class TestTokenizer:
    def test_simple_addition(self):
        tokens = tokenize("1 + 2")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "1"
        assert tokens[1].type == TokenType.PLUS
        assert tokens[2].type == TokenType.NUMBER
        assert tokens[2].value == "2"
        assert tokens[3].type == TokenType.EOF

    def test_identifier(self):
        tokens = tokenize("PE_RATIO")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "PE_RATIO"

    def test_comparison_operators(self):
        tokens = tokenize("a >= b")
        assert tokens[1].type == TokenType.GTE

    def test_all_comparison_ops(self):
        tokens = tokenize("> < >= <= == !=")
        types = [t.type for t in tokens if t.type != TokenType.EOF]
        assert types == [
            TokenType.GT, TokenType.LT, TokenType.GTE,
            TokenType.LTE, TokenType.EQ, TokenType.NEQ,
        ]

    def test_invalid_character(self):
        with pytest.raises(ParseError, match="Unexpected character"):
            tokenize("1 @ 2")

    def test_decimal_number(self):
        tokens = tokenize("3.14")
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "3.14"

    def test_function_call_tokens(self):
        tokens = tokenize("ABS(x)")
        assert tokens[0].type == TokenType.IDENTIFIER
        assert tokens[0].value == "ABS"
        assert tokens[1].type == TokenType.LPAREN
        assert tokens[2].type == TokenType.IDENTIFIER
        assert tokens[3].type == TokenType.RPAREN


class TestEvaluate:
    def test_simple_number(self):
        assert evaluate("42") == 42.0

    def test_addition(self):
        assert evaluate("2 + 3") == 5.0

    def test_subtraction(self):
        assert evaluate("10 - 4") == 6.0

    def test_multiplication(self):
        assert evaluate("3 * 4") == 12.0

    def test_division(self):
        assert evaluate("10 / 4") == 2.5

    def test_operator_precedence(self):
        assert evaluate("2 + 3 * 4") == 14.0

    def test_parentheses(self):
        assert evaluate("(2 + 3) * 4") == 20.0

    def test_nested_parentheses(self):
        assert evaluate("((2 + 3) * (4 - 1))") == 15.0

    def test_unary_minus(self):
        assert evaluate("-5") == -5.0

    def test_unary_minus_expression(self):
        assert evaluate("-3 + 5") == 2.0

    def test_division_by_zero(self):
        with pytest.raises(EvalError, match="Division by zero"):
            evaluate("1 / 0")

    def test_field_reference(self):
        assert evaluate("PE_RATIO * 2", {"PE_RATIO": 15.0}) == 30.0

    def test_unknown_field(self):
        with pytest.raises(EvalError, match="Unknown field"):
            evaluate("UNKNOWN_FIELD")

    def test_multiple_fields(self):
        ctx = {"REVENUE": 1000.0, "COST": 600.0}
        assert evaluate("REVENUE - COST", ctx) == 400.0

    def test_complex_expression(self):
        ctx = {"EV": 1000.0, "EBITDA": 200.0}
        result = evaluate("EV / EBITDA", ctx)
        assert result == pytest.approx(5.0)


class TestComparisons:
    def test_greater_than(self):
        assert evaluate("5 > 3") == 1.0

    def test_greater_than_false(self):
        assert evaluate("3 > 5") == 0.0

    def test_less_than(self):
        assert evaluate("3 < 5") == 1.0

    def test_greater_equal(self):
        assert evaluate("5 >= 5") == 1.0

    def test_less_equal(self):
        assert evaluate("3 <= 5") == 1.0

    def test_equal(self):
        assert evaluate("5 == 5") == 1.0

    def test_not_equal(self):
        assert evaluate("5 != 3") == 1.0


class TestBuiltins:
    def test_abs_positive(self):
        assert evaluate("ABS(5)") == 5.0

    def test_abs_negative(self):
        assert evaluate("ABS(-5)") == 5.0

    def test_max(self):
        assert evaluate("MAX(3, 7)") == 7.0

    def test_min(self):
        assert evaluate("MIN(3, 7)") == 3.0

    def test_sqrt(self):
        assert evaluate("SQRT(16)") == 4.0

    def test_sqrt_negative(self):
        with pytest.raises(EvalError, match="negative"):
            evaluate("SQRT(-1)")

    def test_log(self):
        assert evaluate("LOG(1)") == pytest.approx(0.0)

    def test_log_e(self):
        assert evaluate("LOG(2.718281828)") == pytest.approx(1.0, abs=0.001)

    def test_log_non_positive(self):
        with pytest.raises(EvalError, match="non-positive"):
            evaluate("LOG(0)")

    def test_if_true(self):
        assert evaluate("IF(1, 10, 20)") == 10.0

    def test_if_false(self):
        assert evaluate("IF(0, 10, 20)") == 20.0

    def test_if_with_comparison(self):
        ctx = {"PE_RATIO": 25.0}
        result = evaluate("IF(PE_RATIO > 20, 1, 0)", ctx)
        assert result == 1.0

    def test_nested_functions(self):
        assert evaluate("ABS(MIN(-3, -7))") == 7.0

    def test_wrong_arg_count(self):
        with pytest.raises(EvalError, match="takes 1 argument"):
            evaluate("ABS(1, 2)")


class TestValidate:
    def test_valid_expression(self):
        result = validate("PE_RATIO * 2 + 1")
        assert result["is_valid"] is True
        assert result["error"] is None
        assert "PE_RATIO" in result["dependencies"]

    def test_invalid_expression(self):
        result = validate("1 + + 2")
        assert result["is_valid"] is False
        assert result["error"] is not None

    def test_dependencies_extraction(self):
        result = validate("REVENUE / EBITDA")
        assert "REVENUE" in result["dependencies"]
        assert "EBITDA" in result["dependencies"]

    def test_function_not_in_dependencies(self):
        result = validate("ABS(PE_RATIO)")
        assert "ABS" not in result["dependencies"]
        assert "PE_RATIO" in result["dependencies"]


class TestExtractDependencies:
    def test_simple_field(self):
        tokens = tokenize("PE_RATIO")
        deps = extract_dependencies(tokens)
        assert deps == ["PE_RATIO"]

    def test_multiple_fields(self):
        tokens = tokenize("A + B * C")
        deps = extract_dependencies(tokens)
        assert deps == ["A", "B", "C"]

    def test_excludes_builtins(self):
        tokens = tokenize("ABS(X) + MAX(Y, Z)")
        deps = extract_dependencies(tokens)
        assert "ABS" not in deps
        assert "MAX" not in deps
        assert set(deps) == {"X", "Y", "Z"}

    def test_no_duplicates(self):
        tokens = tokenize("X + X + X")
        deps = extract_dependencies(tokens)
        assert deps == ["X"]
