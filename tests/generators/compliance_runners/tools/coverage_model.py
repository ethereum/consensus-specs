"""Structured coverage expressions. No source parsing, eval, spec, or runner imports."""

from __future__ import annotations

import operator
from dataclasses import dataclass, replace


class _Missing:
    def __bool__(self):
        raise TypeError("missing observations have no truth value")


MISSING = _Missing()


class Domain:
    """A set of values; ``value_type`` determines the legal operations."""

    def __or__(self, other):
        return DomainUnion((self, other))


@dataclass(frozen=True)
class Integer(Domain):
    value_type = int
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

    def values(self, *, limit=1024):
        if self.min is None or self.max is None or self.max - self.min + 1 > limit:
            raise ValueError("domain is too large for exact coverage; declare a partition")
        return tuple(range(self.min, self.max + 1))

    def contains(self, value):
        value = expression(value)
        if value.result_type() is not int:
            raise TypeError("integer expression required")
        return all_of(
            *((value >= self.min,) if self.min is not None else ()),
            *((value <= self.max,) if self.max is not None else ()),
        )


@dataclass(frozen=True)
class Boolean(Domain):
    value_type = bool

    def validate(self, value):
        if type(value) is not bool:
            raise ValueError(f"expected bool, got {value!r}")

    def values(self, *, limit=1024):
        if limit < 2:
            raise ValueError("domain is too large for exact coverage")
        return (True, False)

    def contains(self, value):
        value = expression(value)
        if value.result_type() is not bool:
            raise TypeError("boolean expression required")
        return expression(value=True)


@dataclass(frozen=True)
class Bytes(Domain):
    """Opaque bytes, optionally constrained to a fixed length; equality only."""

    value_type = bytes
    length: int | None = None

    def __post_init__(self):
        if self.length is not None and (type(self.length) is not int or self.length < 0):
            raise ValueError("byte length must be a nonnegative integer")

    def validate(self, value):
        if type(value) is not bytes or (self.length is not None and len(value) != self.length):
            raise ValueError(f"expected {self}, got {value!r}")


@dataclass(frozen=True)
class Finite(Domain):
    """An exact finite set, including singleton sentinel domains."""

    members: tuple

    def __post_init__(self):
        object.__setattr__(self, "members", tuple(self.members))
        if not self.members or any(type(v) not in (bool, int, str) for v in self.members):
            raise ValueError("expected a nonempty finite scalar domain")
        if any(type(v) is not type(self.members[0]) for v in self.members):
            raise TypeError("finite domain values must have the same type")
        if len(set(self.members)) != len(self.members):
            raise ValueError("duplicate finite domain value")

    @property
    def value_type(self):
        return type(self.members[0])

    def validate(self, value):
        if type(value) is not self.value_type or value not in self.members:
            raise ValueError(f"{value!r} is outside {self}")

    def values(self, *, limit=1024):
        if len(self.members) > limit:
            raise ValueError("domain is too large for exact coverage; declare a partition")
        return self.members

    def contains(self, value):
        return any_of(*(expression(value) == member for member in self.members))


@dataclass(frozen=True)
class DomainUnion(Domain):
    parts: tuple

    def __post_init__(self):
        parts = tuple(
            p
            for part in self.parts
            for p in (part.parts if isinstance(part, DomainUnion) else (part,))
        )
        if not parts or any(not isinstance(p, (Integer, Boolean, Finite)) for p in parts):
            raise TypeError("union requires scalar domains")
        if any(p.value_type is not parts[0].value_type for p in parts):
            raise TypeError("union domains must have the same type")
        object.__setattr__(self, "parts", parts)

    @property
    def value_type(self):
        return self.parts[0].value_type

    def validate(self, value):
        for part in self.parts:
            try:
                part.validate(value)
                return
            except ValueError:
                pass
        raise ValueError(f"{value!r} is outside {self}")

    def values(self, *, limit=1024):
        values = tuple(dict.fromkeys(v for part in self.parts for v in part.values(limit=limit)))
        if len(values) > limit:
            raise ValueError("domain is too large for exact coverage; declare a partition")
        return values

    def contains(self, value):
        return any_of(*(part.contains(value) for part in self.parts))


def _integer_hull(domain):
    if isinstance(domain, Integer):
        return domain
    if isinstance(domain, Finite):
        return Integer(min(domain.members), max(domain.members))
    bounds = tuple(_integer_hull(part) for part in domain.parts)
    return Integer(
        min(b.min for b in bounds) if all(b.min is not None for b in bounds) else None,
        max(b.max for b in bounds) if all(b.max is not None for b in bounds) else None,
    )


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
    domain: Domain | None = None

    def __post_init__(self):
        arity = {
            **dict.fromkeys(_BINARY, 2),
            "&": 2,
            "|": 2,
            "~": 1,
            "choose": 3,
            "literal": 1,
            "factor": 1,
            "coverage": 1,
            "present": 1,
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
            if not isinstance(self.domain, (Integer, Boolean, Bytes, Finite, DomainUnion)):
                raise TypeError("unsupported input domain")
            return self.domain.value_type
        if self.op == "literal":
            if type(self.args[0]) not in (bool, int, str):
                raise TypeError("unsupported literal")
            return type(self.args[0])
        if self.op == "factor":
            return self.args[0].value.result_type() if self.args[0].kind == "enum" else bool
        if self.op == "coverage":
            f = self.args[0]
            return (
                str
                if f.kind == "comparison" and f.granularity != "predicate"
                else (f.value.result_type() if f.kind == "enum" else bool)
            )
        if self.op == "present":
            return bool
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

    def integer_domain(self, constants=None):
        """Conservative interval; correlations between operands are not inferred."""
        if self.result_type() is not int:
            raise TypeError("integer expression required")
        if self.op in ("attribute", "constant"):
            if self.op == "constant" and constants is not None and self.name in constants:
                value = constants[self.name]
                self.domain.validate(value)
                return Integer(value, value)
            return _integer_hull(self.domain)
        if self.op == "literal":
            return Integer(self.args[0], self.args[0])
        if self.op == "derived":
            return self.args[0].integer_domain(constants)
        if self.op == "choose":
            a, b = (arg.integer_domain(constants) for arg in self.args[1:])
            return Integer(
                min(a.min, b.min) if a.min is not None and b.min is not None else None,
                max(a.max, b.max) if a.max is not None and b.max is not None else None,
            )
        a, b = (arg.integer_domain(constants) for arg in self.args)
        if self.op == "%" and b.min is not None and b.min > 0:
            return Integer(0, b.max - 1 if b.max is not None else None)
        if self.op == "+":
            return Integer(
                a.min + b.min if a.min is not None and b.min is not None else None,
                a.max + b.max if a.max is not None and b.max is not None else None,
            )
        if self.op == "-":
            return Integer(
                a.min - b.max if a.min is not None and b.max is not None else None,
                a.max - b.min if a.max is not None and b.min is not None else None,
            )
        if self.op == "max":
            lower = [v for v in (a.min, b.min) if v is not None]
            return Integer(
                max(lower) if lower else None,
                max(a.max, b.max) if a.max is not None and b.max is not None else None,
            )
        return Integer()

    def evaluate(self, attributes, constants, factors=None):
        if self.op in ("coverage", "present"):
            raise ValueError("coverage and presence references require feasibility evaluation")
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
        if self.op in ("factor", "coverage", "present"):
            return ()
        return tuple(node for arg in self.args if isinstance(arg, Expr) for node in arg.inputs())

    def render(self):
        if self.op == "literal":
            return repr(self.args[0])
        if self.op in ("attribute", "constant", "derived"):
            return self.name
        if self.op == "factor":
            return self.args[0].name
        if self.op in ("coverage", "present"):
            return f"{self.op}({self.args[0].name})"
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


def choose(condition, yes, no=MISSING, *branches):
    """Choose the first matching branch, with a final fallback.

    Accepts ``choose((condition, value), ..., fallback)`` or alternating
    conditions and values. The three-argument form and its keyword arguments
    remain supported.
    """
    values = (condition, yes) if no is MISSING else (condition, yes, no, *branches)
    if isinstance(condition, tuple):
        if isinstance(values[-1], tuple):
            raise ValueError("choose requires a final fallback after its pairs")
        if any(not isinstance(pair, tuple) or len(pair) != 2 for pair in values[:-1]):
            raise ValueError("choose requires (condition, value) pairs")
        values = tuple(item for pair in values[:-1] for item in pair) + (values[-1],)
    elif no is MISSING or len(branches) % 2:
        raise ValueError("choose requires condition/value pairs and a final fallback")
    result = expression(values[-1])
    for i in range(len(values) - 3, -1, -2):
        result = Expr("choose", (expression(values[i]), expression(values[i + 1]), result))
    return result


def maximum(left, right):
    return Expr("max", (expression(left), expression(right)))


def _junction(op, conditions, *, identity):
    nodes = tuple(expression(condition) for condition in conditions)
    if any(node.result_type() is not bool for node in nodes):
        raise TypeError("boolean operands required")
    if not nodes:
        return expression(identity)
    while len(nodes) > 1:
        nodes = tuple(
            Expr(op, (nodes[i], nodes[i + 1])) if i + 1 < len(nodes) else nodes[i]
            for i in range(0, len(nodes), 2)
        )
    return nodes[0]


def all_of(*conditions):
    return _junction("&", conditions, identity=True)


def any_of(*conditions):
    return _junction("|", conditions, identity=False)


def implies(condition, consequence):
    return ~expression(condition) | consequence


def coverage_value(declaration):
    """Reference a factor's abstract value in a feasibility constraint."""
    if not isinstance(declaration, Factor):
        raise TypeError("coverage_value requires a factor declaration")
    return Expr("coverage", (declaration,))


def present(declaration):
    """Whether a factor is included in the abstract configuration."""
    if not isinstance(declaration, Factor):
        raise TypeError("present requires a factor declaration")
    return Expr("present", (declaration,))


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
    granularity: str = "predicate"
    modulus: Expr | None = None
    exact_dimension: bool = False

    def __post_init__(self):
        if not self.name or self.kind not in ("boolean", "comparison", "enum"):
            raise ValueError("invalid factor name or kind")
        if self.granularity not in ("predicate", "cmp3", "cmp5"):
            raise ValueError(f"unknown granularity {self.granularity!r}")
        if self.kind != "comparison" and self.granularity != "predicate":
            raise ValueError("granularity is only configurable for comparison factors")
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


def comparison(
    name,
    lhs,
    rhs,
    *,
    op=">",
    granularity="predicate",
    when=True,
    available_when=True,
    description="",
):
    if op not in ("<", "<=", "==", "!=", ">=", ">"):
        raise ValueError(f"unsupported comparison: {op}")
    return Factor(
        name,
        expression(lhs) - rhs,
        kind="comparison",
        op=op,
        granularity=granularity,
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


@dataclass(frozen=True)
class Mapping:
    """An unnamed coverage view, applied by ``dimension``."""

    kind: str
    operands: tuple
    domain: Domain | None = None
    op: str = ">"


def identity(value, *, domain=None):
    return Mapping("identity", (expression(value),), domain=domain)


def cmp5(lhs, rhs, *, op=">"):
    """Five distance buckets with an explicit predicate meaning for constraints."""
    return Mapping("cmp5", (expression(lhs), expression(rhs)), op=op)


def predicate(lhs, rhs, *, op=">"):
    """Boolean coverage of an integer comparison, retaining its raw difference."""
    return Mapping("predicate", (expression(lhs), expression(rhs)), op=op)


def count(value):
    value = expression(value)
    return identity(
        choose((value == 0, "ZERO"), (value == 1, "ONE"), "MANY"),
        domain=Finite(("ZERO", "ONE", "MANY")),
    )


def modulo_boundary(lhs, modulus):
    return Mapping("modulo", (expression(lhs), expression(modulus)))


def _dimension_domain(value, limit):
    if value.op in ("attribute", "constant"):
        return value.domain
    if value.result_type() is bool:
        return Boolean()
    if value.op == "literal":
        return Finite((value.args[0],))
    if value.op == "derived":
        return _dimension_domain(value.args[0], limit)
    if value.op == "choose":
        values = tuple(
            dict.fromkeys(
                member
                for branch in value.args[1:]
                for member in _dimension_domain(branch, limit).values(limit=limit)
            )
        )
        domain = Finite(values)
        domain.values(limit=limit)
        return domain
    if value.result_type() is int:
        return value.integer_domain()
    raise ValueError("declare a finite domain for this expression")


def dimension(name, value, *, domain=None, limit=1024, **kwargs):
    """Cover a finite expression exactly, using its input domain by default."""
    if isinstance(value, Mapping):
        if domain is not None:
            raise ValueError("declare the coverage domain on the mapping")
        if value.kind in ("predicate", "cmp5"):
            return comparison(name, *value.operands, op=value.op, granularity=value.kind, **kwargs)
        if value.kind == "modulo":
            return modulo(name, *value.operands, **kwargs)
        if value.kind != "identity":
            raise ValueError(f"unsupported mapping: {value.kind}")
        domain, value = value.domain, value.operands[0]
    value = expression(value)
    if domain is None:
        domain = _dimension_domain(value, limit)
    if domain.value_type is not value.result_type():
        raise TypeError("coverage domain must match the expression type")
    if isinstance(domain, Boolean):
        result = factor(name, value, **kwargs)
    else:
        result = categorical(name, value, domain.values(limit=limit), **kwargs)
    return replace(result, exact_dimension=True)


def modulo(name, lhs, modulus, *, when=True, available_when=True, description=""):
    """Cover zero, one, last, and interior remainders of a positive constant.

    For periods 1 and 2, coincident boundaries use ZERO and ONE respectively.
    """
    modulus = expression(modulus)
    if modulus.op not in ("literal", "constant") or modulus.result_type() is not int:
        raise ValueError("modulus must be a positive integer literal or constant")
    domain = modulus.integer_domain()
    if domain.min is None or domain.min < 1:
        raise ValueError("modulus must have a positive integer domain")
    remainder = expression(lhs) % modulus
    value = choose(
        (remainder == 0, "ZERO"),
        (remainder == 1, "ONE"),
        (remainder == modulus - 1, "LAST"),
        "INTERIOR",
    )
    return Factor(
        name,
        value,
        kind="enum",
        values=("ZERO", "ONE", "LAST", "INTERIOR"),
        modulus=modulus,
        when=expression(when),
        available_when=expression(available_when),
        description=description,
    )
