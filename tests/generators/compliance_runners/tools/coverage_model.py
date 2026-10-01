"""Structured coverage expressions. No source parsing, eval, spec, or runner imports."""

from __future__ import annotations

import operator
from dataclasses import dataclass


class _Missing:
    def __bool__(self):
        raise TypeError("missing observations have no truth value")


MISSING = _Missing()


@dataclass(frozen=True)
class Integer:
    min: int | None = None
    max: int | None = None

    def __post_init__(self):
        if any(v is not None and type(v) is not int for v in (self.min, self.max)):
            raise TypeError("integer bounds must be integers")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("empty integer domain")

    def validate(self, value):
        if (
            type(value) is not int
            or (self.min is not None and value < self.min)
            or (self.max is not None and value > self.max)
        ):
            raise ValueError(f"{value!r} is outside {self}")


@dataclass(frozen=True)
class Boolean:
    def validate(self, value):
        if type(value) is not bool:
            raise ValueError(f"expected bool, got {value!r}")


@dataclass(frozen=True)
class Bytes:
    """Opaque bytes, optionally constrained to a fixed length; equality only."""

    length: int | None = None

    def __post_init__(self):
        if self.length is not None and (type(self.length) is not int or self.length < 0):
            raise ValueError("byte length must be a nonnegative integer")

    def validate(self, value):
        if type(value) is not bytes or (self.length is not None and len(value) != self.length):
            raise ValueError(f"expected {self}, got {value!r}")


class Operators:
    def __bool__(self):
        raise TypeError("symbolic expressions have no truth value; use &, |, ~, and choose()")

    def _binary(self, op, other):
        return Expr(op, (expression(self), expression(other)))

    def __add__(self, other):
        return self._binary("+", other)

    def __radd__(self, other):
        return expression(other)._binary("+", self)

    def __sub__(self, other):
        return self._binary("-", other)

    def __rsub__(self, other):
        return expression(other)._binary("-", self)

    def __mod__(self, other):
        return self._binary("%", other)

    def __lt__(self, other):
        return self._binary("<", other)

    def __le__(self, other):
        return self._binary("<=", other)

    def __gt__(self, other):
        return self._binary(">", other)

    def __ge__(self, other):
        return self._binary(">=", other)

    def __eq__(self, other):
        return self._binary("==", other)

    def __ne__(self, other):
        return self._binary("!=", other)

    def __and__(self, other):
        return self._binary("&", other)

    def __or__(self, other):
        return self._binary("|", other)

    def __invert__(self):
        return Expr("~", (expression(self),))

    __hash__ = object.__hash__


_BINARY = {
    "+": operator.add,
    "-": operator.sub,
    "%": operator.mod,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
    "max": max,
}


@dataclass(frozen=True, eq=False)
class Expr(Operators):
    op: str
    args: tuple = ()
    name: str = ""
    domain: Integer | Boolean | Bytes | None = None

    def __post_init__(self):
        arity = {
            **dict.fromkeys(_BINARY, 2),
            "&": 2,
            "|": 2,
            "~": 1,
            "choose": 3,
            "literal": 1,
            "factor": 1,
            "derived": 1,
            "attribute": 0,
            "constant": 0,
        }
        if self.op not in arity or len(self.args) != arity[self.op]:
            raise ValueError(f"unsupported expression or arity: {self.op}")
        if self.op in ("attribute", "constant", "derived") and not self.name:
            raise ValueError("declarations need a name")
        self.result_type()  # Reject ill-typed expressions at declaration time.

    def result_type(self):
        if self.op in ("attribute", "constant"):
            if not isinstance(self.domain, (Integer, Boolean, Bytes)):
                raise TypeError("unsupported input domain")
            if isinstance(self.domain, Bytes):
                return bytes
            return int if isinstance(self.domain, Integer) else bool
        if self.op == "literal":
            if type(self.args[0]) not in (bool, int, str):
                raise TypeError("unsupported literal")
            return type(self.args[0])
        if self.op == "factor":
            return self.args[0].value.result_type() if self.args[0].kind == "enum" else bool
        types = tuple(arg.result_type() for arg in self.args)
        if self.op == "derived":
            return types[0]
        if self.op == "choose":
            if types[0] is not bool or types[1] is not types[2]:
                raise TypeError("choose requires a boolean condition and matching branch types")
            return types[1]
        if self.op in ("&", "|", "~"):
            if any(t is not bool for t in types):
                raise TypeError("boolean operands required")
            return bool
        if self.op in ("==", "!="):
            if types[0] is not types[1]:
                raise TypeError("equality requires matching types")
            return bool
        if any(t is not int for t in types):
            raise TypeError("integer operands required")
        return bool if self.op in ("<", "<=", ">", ">=") else int

    def evaluate(self, attributes, constants, factors=None):
        if self.op == "literal":
            return self.args[0]
        if self.op in ("attribute", "constant"):
            env = attributes if self.op == "attribute" else constants
            if self.name not in env:
                raise ValueError(f"missing {self.op}: {self.name}")
            value = env[self.name]
            if value is not MISSING:
                self.domain.validate(value)
            return value
        if self.op == "factor":
            return factors(self.args[0])
        if self.op == "derived":
            return self.args[0].evaluate(attributes, constants, factors)
        first = self.args[0].evaluate(attributes, constants, factors)
        if first is MISSING:
            return MISSING
        if self.op in ("choose", "&", "|", "~") and type(first) is not bool:
            raise TypeError(f"{self.op} requires a boolean condition")
        if self.op == "~":
            return not first
        if self.op == "choose":
            return self.args[1 if first else 2].evaluate(attributes, constants, factors)
        if self.op == "&" and not first:
            return False
        if self.op == "|" and first:
            return True
        second = self.args[1].evaluate(attributes, constants, factors)
        if second is MISSING:
            return MISSING
        if self.op in ("&", "|"):
            if type(second) is not bool:
                raise TypeError("boolean operand required")
            return second
        return _BINARY[self.op](first, second)

    def inputs(self):
        if self.op in ("attribute", "constant"):
            return (self,)
        if self.op == "factor":
            return ()
        return tuple(node for arg in self.args if isinstance(arg, Expr) for node in arg.inputs())

    def render(self):
        if self.op == "literal":
            return repr(self.args[0])
        if self.op in ("attribute", "constant", "derived"):
            return self.name
        if self.op == "factor":
            return self.args[0].name
        if self.op == "~":
            return f"~({self.args[0].render()})"
        if self.op in ("choose", "max"):
            return f"{self.op}({', '.join(a.render() for a in self.args)})"
        return f"({self.args[0].render()} {self.op} {self.args[1].render()})"


def expression(value):
    if isinstance(value, Expr):
        return value
    if isinstance(value, Factor):
        return Expr("factor", (value,))
    if type(value) not in (bool, int, str):
        raise TypeError(f"unsupported expression: {value!r}")
    return Expr("literal", (value,))


def attribute(name, domain):
    return Expr("attribute", name=name, domain=domain)


def constant(name, domain):
    return Expr("constant", name=name, domain=domain)


def derived(name, value):
    return Expr("derived", (expression(value),), name=name)


def choose(condition, yes, no):
    return Expr("choose", tuple(map(expression, (condition, yes, no))))


def maximum(left, right):
    return Expr("max", (expression(left), expression(right)))


@dataclass(frozen=True, eq=False)
class Factor(Operators):
    name: str
    value: Expr
    kind: str = "boolean"
    op: str = ">"
    values: tuple = ()
    when: Expr = Expr("literal", (True,))
    available_when: Expr = Expr("literal", (True,))
    description: str = ""

    def __post_init__(self):
        if not self.name or self.kind not in ("boolean", "comparison", "enum"):
            raise ValueError("invalid factor name or kind")
        if self.when.result_type() is not bool or self.available_when.result_type() is not bool:
            raise TypeError("activation and availability must be boolean")
        if self.kind == "boolean" and self.value.result_type() is not bool:
            raise TypeError("boolean factor requires a boolean expression")
        if self.kind == "comparison" and self.value.result_type() is not int:
            raise TypeError("comparison factor requires an integer difference")
        if self.kind == "enum" and any(
            type(v) is not self.value.result_type() for v in self.values
        ):
            raise TypeError("categorical domain must match the expression type")


def factor(name, value, *, when=True, available_when=True, description=""):
    return Factor(
        name,
        expression(value),
        when=expression(when),
        available_when=expression(available_when),
        description=description,
    )


def comparison(name, lhs, rhs, *, op=">", when=True, available_when=True, description=""):
    if op not in ("<", "<=", "==", "!=", ">=", ">"):
        raise ValueError(f"unsupported comparison: {op}")
    return Factor(
        name,
        expression(lhs) - rhs,
        kind="comparison",
        op=op,
        when=expression(when),
        available_when=expression(available_when),
        description=description,
    )


def categorical(name, value, values, *, when=True, available_when=True, description=""):
    values = tuple(values)
    if (
        not values
        or len(set(values)) != len(values)
        or any(type(v) not in (bool, int, str) for v in values)
    ):
        raise ValueError("expected a nonempty unique finite domain")
    return Factor(
        name,
        expression(value),
        kind="enum",
        values=values,
        when=expression(when),
        available_when=expression(available_when),
        description=description,
    )
