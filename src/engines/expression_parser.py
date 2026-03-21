"""Expression Parser for Custom Data Environment.

A recursive descent parser that evaluates arithmetic expressions with
field references and built-in functions.
All functions are pure computation — no database access.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    NUMBER = auto()
    IDENTIFIER = auto()
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    GT = auto()
    LT = auto()
    GTE = auto()
    LTE = auto()
    EQ = auto()
    NEQ = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    position: int


class ParseError(Exception):
    """Raised when expression parsing fails."""
    def __init__(self, message: str, position: int = -1):
        self.position = position
        super().__init__(message)


class EvalError(Exception):
    """Raised when expression evaluation fails."""
    pass


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_PATTERNS = [
    (r'\d+\.?\d*', TokenType.NUMBER),
    (r'[A-Za-z_][A-Za-z0-9_]*', TokenType.IDENTIFIER),
    (r'>=', TokenType.GTE),
    (r'<=', TokenType.LTE),
    (r'==', TokenType.EQ),
    (r'!=', TokenType.NEQ),
    (r'>', TokenType.GT),
    (r'<', TokenType.LT),
    (r'\+', TokenType.PLUS),
    (r'-', TokenType.MINUS),
    (r'\*', TokenType.MULTIPLY),
    (r'/', TokenType.DIVIDE),
    (r'\(', TokenType.LPAREN),
    (r'\)', TokenType.RPAREN),
    (r',', TokenType.COMMA),
]


def tokenize(expression: str) -> list[Token]:
    """Tokenize an expression string into a list of tokens."""
    tokens = []
    pos = 0
    while pos < len(expression):
        # Skip whitespace
        if expression[pos].isspace():
            pos += 1
            continue

        matched = False
        for pattern, token_type in _TOKEN_PATTERNS:
            m = re.match(pattern, expression[pos:])
            if m:
                tokens.append(Token(type=token_type, value=m.group(), position=pos))
                pos += len(m.group())
                matched = True
                break

        if not matched:
            raise ParseError(f"Unexpected character '{expression[pos]}'", position=pos)

    tokens.append(Token(type=TokenType.EOF, value="", position=pos))
    return tokens


# ---------------------------------------------------------------------------
# Built-in functions
# ---------------------------------------------------------------------------

BUILTINS = {"ABS", "MAX", "MIN", "SQRT", "LOG", "IF"}


def _call_builtin(name: str, args: list[float]) -> float:
    """Evaluate a built-in function call."""
    name_upper = name.upper()
    if name_upper == "ABS":
        if len(args) != 1:
            raise EvalError(f"ABS() takes 1 argument, got {len(args)}")
        return abs(args[0])
    elif name_upper == "MAX":
        if len(args) < 2:
            raise EvalError(f"MAX() takes at least 2 arguments, got {len(args)}")
        return max(args)
    elif name_upper == "MIN":
        if len(args) < 2:
            raise EvalError(f"MIN() takes at least 2 arguments, got {len(args)}")
        return min(args)
    elif name_upper == "SQRT":
        if len(args) != 1:
            raise EvalError(f"SQRT() takes 1 argument, got {len(args)}")
        if args[0] < 0:
            raise EvalError("SQRT() of negative number")
        return math.sqrt(args[0])
    elif name_upper == "LOG":
        if len(args) != 1:
            raise EvalError(f"LOG() takes 1 argument, got {len(args)}")
        if args[0] <= 0:
            raise EvalError("LOG() of non-positive number")
        return math.log(args[0])
    elif name_upper == "IF":
        if len(args) != 3:
            raise EvalError(f"IF() takes 3 arguments, got {len(args)}")
        return args[1] if args[0] != 0 else args[2]
    else:
        raise EvalError(f"Unknown function: {name}")


# ---------------------------------------------------------------------------
# Recursive Descent Parser + Evaluator
# ---------------------------------------------------------------------------

class Parser:
    """Recursive descent parser that evaluates expressions."""

    def __init__(self, tokens: list[Token], context: dict[str, float] | None = None):
        self.tokens = tokens
        self.pos = 0
        self.context = context or {}

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _eat(self, expected_type: TokenType) -> Token:
        token = self._current()
        if token.type != expected_type:
            raise ParseError(
                f"Expected {expected_type.name}, got {token.type.name} ('{token.value}')",
                position=token.position,
            )
        self.pos += 1
        return token

    def parse(self) -> float:
        """Parse and evaluate the full expression."""
        result = self._comparison()
        if self._current().type != TokenType.EOF:
            raise ParseError(
                f"Unexpected token '{self._current().value}'",
                position=self._current().position,
            )
        return result

    def _comparison(self) -> float:
        """Handle comparison operators (lowest precedence)."""
        left = self._expression()
        while self._current().type in (
            TokenType.GT, TokenType.LT, TokenType.GTE,
            TokenType.LTE, TokenType.EQ, TokenType.NEQ,
        ):
            op = self._current()
            self.pos += 1
            right = self._expression()
            if op.type == TokenType.GT:
                left = 1.0 if left > right else 0.0
            elif op.type == TokenType.LT:
                left = 1.0 if left < right else 0.0
            elif op.type == TokenType.GTE:
                left = 1.0 if left >= right else 0.0
            elif op.type == TokenType.LTE:
                left = 1.0 if left <= right else 0.0
            elif op.type == TokenType.EQ:
                left = 1.0 if abs(left - right) < 1e-10 else 0.0
            elif op.type == TokenType.NEQ:
                left = 1.0 if abs(left - right) >= 1e-10 else 0.0
        return left

    def _expression(self) -> float:
        """Handle addition and subtraction."""
        left = self._term()
        while self._current().type in (TokenType.PLUS, TokenType.MINUS):
            op = self._current()
            self.pos += 1
            right = self._term()
            if op.type == TokenType.PLUS:
                left = left + right
            else:
                left = left - right
        return left

    def _term(self) -> float:
        """Handle multiplication and division."""
        left = self._unary()
        while self._current().type in (TokenType.MULTIPLY, TokenType.DIVIDE):
            op = self._current()
            self.pos += 1
            right = self._unary()
            if op.type == TokenType.MULTIPLY:
                left = left * right
            else:
                if abs(right) < 1e-15:
                    raise EvalError("Division by zero")
                left = left / right
        return left

    def _unary(self) -> float:
        """Handle unary minus."""
        if self._current().type == TokenType.MINUS:
            self.pos += 1
            return -self._unary()
        return self._atom()

    def _atom(self) -> float:
        """Handle atoms: numbers, identifiers, function calls, parenthesized expressions."""
        token = self._current()

        if token.type == TokenType.NUMBER:
            self.pos += 1
            return float(token.value)

        if token.type == TokenType.IDENTIFIER:
            self.pos += 1
            name = token.value.upper()
            # Check if it's a function call
            if self._current().type == TokenType.LPAREN:
                return self._function_call(name)
            # Otherwise it's a field reference
            if name in self.context:
                return self.context[name]
            raise EvalError(f"Unknown field: {name}")

        if token.type == TokenType.LPAREN:
            self.pos += 1
            result = self._comparison()
            self._eat(TokenType.RPAREN)
            return result

        raise ParseError(
            f"Unexpected token '{token.value}'",
            position=token.position,
        )

    def _function_call(self, name: str) -> float:
        """Parse and evaluate a function call."""
        self._eat(TokenType.LPAREN)
        args = []
        if self._current().type != TokenType.RPAREN:
            args.append(self._comparison())
            while self._current().type == TokenType.COMMA:
                self.pos += 1
                args.append(self._comparison())
        self._eat(TokenType.RPAREN)
        return _call_builtin(name, args)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(expression: str, context: dict[str, float] | None = None) -> float:
    """Parse and evaluate an expression with the given variable context.

    Parameters
    ----------
    expression : The expression string to evaluate.
    context : Mapping of field names (uppercase) to their numeric values.

    Returns
    -------
    float result of the evaluation.

    Raises
    ------
    ParseError : If the expression has syntax errors.
    EvalError : If evaluation fails (division by zero, unknown field, etc.)
    """
    tokens = tokenize(expression)
    parser = Parser(tokens, context)
    return parser.parse()


def validate(expression: str) -> dict:
    """Validate an expression without evaluating it.

    Returns
    -------
    dict with keys:
        - is_valid: bool
        - error: str | None (error message if invalid)
        - dependencies: list[str] (field names referenced)
    """
    try:
        tokens = tokenize(expression)
        deps = extract_dependencies(tokens)
        # Try to parse with dummy context (all deps = 1.0)
        dummy_context = {d: 1.0 for d in deps}
        parser = Parser(tokens, dummy_context)
        parser.parse()
        return {"is_valid": True, "error": None, "dependencies": deps}
    except (ParseError, EvalError) as e:
        deps = []
        try:
            deps = extract_dependencies(tokenize(expression))
        except ParseError:
            pass
        return {"is_valid": False, "error": str(e), "dependencies": deps}


def extract_dependencies(tokens: list[Token]) -> list[str]:
    """Extract field name dependencies from tokenized expression.

    Returns list of uppercase field names referenced in the expression,
    excluding built-in function names.
    """
    deps = set()
    for i, token in enumerate(tokens):
        if token.type == TokenType.IDENTIFIER:
            name = token.value.upper()
            # Check if next token is LPAREN (function call) — skip builtins
            if name in BUILTINS:
                continue
            deps.add(name)
    return sorted(deps)
