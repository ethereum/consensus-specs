"""Explicit coverage specifications, binding, observation, and review.

Expression trees are defined in the shared coverage_model tool. This adapter
adds observation, conditional coverage formulas, spec binding, and review text.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from tests.generators.state_transition.tools import conditional_factors as conditional
from tests.generators.state_transition.tools.coverage_model import (
    attribute,
    Boolean,
    Bytes,
    categorical,
    choose,
    comparison,
    constant,
    derived,
    Expr,
    expression,
    factor,
    Integer,
    maximum,
    MISSING,
)

from .coverage_dsl import _merge, Cmp, Enum, NA, Pred, rules

__all__ = [
    "Boolean",
    "Bytes",
    "Integer",
    "aspect",
    "attribute",
    "bind",
    "categorical",
    "choose",
    "comparison",
    "constant",
    "coverage_spec",
    "derived",
    "each",
    "exhaustive",
    "factor",
    "fix",
    "maximum",
    "nwise",
    "union",
]


@dataclass(frozen=True)
class Plan:
    kind: str
    parts: tuple
    strength: int = 0

    def __or__(self, other):
        return union(self, other)

    def __mul__(self, other):
        return Plan("product", (self, other))

    def run(self, *args, **kwargs):
        raise ValueError("bind the declaration target with for_spec(spec) before enumerating")


def nwise(factors, strength):
    factors = tuple(factors)
    if type(strength) is not int or not 1 <= strength <= len(factors):
        raise ValueError("strength must be in 1..number of selected factors")
    if len({f.name for f in factors}) != len(factors):
        raise ValueError("duplicate selected factor")
    return Plan("nwise", factors, strength)


def each(factors):
    return nwise(factors, 1)


def exhaustive(factors):
    factors = tuple(factors)
    return nwise(factors, len(factors))


def union(*parts):
    return Plan("union", tuple(parts))


def fix(**values):
    return Plan("fix", tuple(values.items()))


class Aspect:
    def __init__(self, name, factors):
        self.name = name
        self.declarations = tuple(factors)
        self.factors = tuple(_abstract(f) for f in self.declarations)

    def __getitem__(self, name):
        return next(f for f in self.factors if f.name == name)

    def each(self):
        return each(self.declarations)

    def nwise(self, strength):
        return nwise(self.declarations, strength)

    def exhaustive(self):
        return exhaustive(self.declarations)


def aspect(name, *factors):
    return Aspect(name, factors)


def _abstract(f):
    description = f.description or f.value.render()
    if f.kind == "comparison":
        return Cmp(f.name, description, f.op)
    if f.kind == "enum":
        return Enum(f.name, description, f.values)
    return Pred(f.name, description)


def _conditions(node):
    """Conjunctions of factor truth tests or equality to a categorical value."""
    if node.op in ("==", "!=") and node.args[0].op == "literal" and node.args[1].op == "factor":
        node = Expr(node.op, (node.args[1], node.args[0]))
    if node.op == "literal" and node.args[0] is True:
        return []
    if node.op == "&":
        return _conditions(node.args[0]) + _conditions(node.args[1])
    if node.op == "factor":
        return [(node.args[0], True, True)]
    if node.op == "~" and node.args[0].op == "factor":
        return [(node.args[0].args[0], False, True)]
    if node.op in ("==", "!=") and node.args[0].op == "factor" and node.args[1].op == "literal":
        parent, value = node.args[0].args[0], node.args[1].args[0]
        if parent.kind != "enum":
            # Comparison references denote predicate truth, even at cmp3/cmp5.
            return [(parent, value if node.op == "==" else not value, True)]
        return [(parent, value, False, node.op)]
    raise ValueError("activation supports conjunctions of factor truth/equality tests only")


def _walk(node):
    yield node
    for arg in node.args:
        if isinstance(arg, Expr):
            yield from _walk(arg)


class Specification:
    def __init__(
        self,
        name,
        *,
        focus,
        record,
        attributes,
        constants=(),
        aspects,
        profiles,
        applicable_when=True,
        feasible=lambda a, g: True,
        constant_feasibility=None,
    ):
        self.name, self.focus, self.record = name, focus, record
        self.attributes, self.constants = tuple(attributes), tuple(constants)
        self.aspects, self.profiles = tuple(aspects), dict(profiles)
        self.applicable_when = expression(applicable_when)
        if self.applicable_when.result_type() is not bool:
            raise TypeError("applicability must be boolean")
        self.feasible, self.constant_feasibility = feasible, constant_feasibility
        self.declarations = tuple(f for a in self.aspects for f in a.declarations)
        self.by_name = {f.name: f for f in self.declarations}
        inputs = self.attributes + self.constants
        names = [i.name for i in inputs] + [f.name for f in self.declarations]
        if len(names) != len(set(names)):
            raise ValueError("duplicate input or factor name")
        if len({a.name for a in self.aspects}) != len(self.aspects):
            raise ValueError("duplicate aspect name")
        for node in self.attributes:
            if node.op != "attribute":
                raise ValueError("attributes must be attribute declarations")
        for node in self.constants:
            if node.op != "constant":
                raise ValueError("constants must be constant declarations")
        for node in inputs:
            if not isinstance(node.domain, (Integer, Boolean, Bytes)):
                raise TypeError("unsupported input domain")
        expressions = [self.applicable_when]
        for f in self.declarations:
            expressions.extend((f.value, f.when, f.available_when))
            for parent, *_ in _conditions(f.when):
                if self.by_name.get(parent.name) is not parent:
                    raise ValueError("undeclared activation factor")
        for expr in expressions:
            for node in expr.inputs():
                if not any(node is declared for declared in inputs):
                    raise ValueError(f"undeclared input: {node.name}")
        # Factor references are reserved for activation; values are defined over inputs.
        for expr in [self.applicable_when] + [
            e for f in self.declarations for e in (f.value, f.available_when)
        ]:
            if any(n.op == "factor" for n in _walk(expr)):
                raise ValueError("factor references are only supported in activation")
        self.model("predicate")  # Validate dependencies, including cycles.
        for plan in self.profiles.values():
            self._validate_plan(plan)

    def _validate_plan(self, plan):
        if not isinstance(plan, Plan):
            raise TypeError("expected a declaration coverage formula")
        if plan.kind == "nwise":
            for f in plan.parts:
                if self.by_name.get(f.name) is not f:
                    raise ValueError("profile selects undeclared factor")
        elif plan.kind == "fix":
            for name, _ in plan.parts:
                if name not in self.by_name:
                    raise ValueError(f"unknown fixed factor: {name}")
        elif plan.kind in ("union", "product"):
            for p in plan.parts:
                self._validate_plan(p)
        else:
            raise ValueError(f"unknown formula: {plan.kind}")

    def model(self, granularity):
        factors = []
        for f in self.declarations:
            allowed = []
            for condition in _conditions(f.when):
                parent, value, truth, *op = condition
                abstraction = _abstract(parent)
                if truth and parent.kind == "enum":
                    raise ValueError("categorical activation needs an explicit value")
                values = tuple(
                    v
                    for v in abstraction.domain(granularity)
                    if (
                        abstraction.holds(v, granularity) == value
                        if truth
                        else ((v == value) if op[0] == "==" else (v != value))
                    )
                )
                if not truth and value not in abstraction.domain(granularity):
                    raise ValueError(f"activation value outside domain of {parent.name}")
                allowed.append((parent.name, values))
            factors.append(
                conditional.Factor(f.name, _abstract(f).domain(granularity), allowed=tuple(allowed))
            )
        return conditional.Model(factors)


coverage_spec = Specification


class BoundFormula:
    def __init__(self, owner, plan):
        self.owner, self.plan = owner, plan

    def run(self, granularity, *, filtered=True):
        model, configurations = self.owner._configurations(granularity, filtered)

        def run(plan):
            if plan.kind == "nwise":
                return model.project([f.name for f in plan.parts], plan.strength, configurations)
            if plan.kind == "fix":
                for name, value in plan.parts:
                    if value not in _abstract(self.owner.definition.by_name[name]).domain(
                        granularity
                    ):
                        raise ValueError(f"invalid fixed value: {name}={value!r}")
                fixed = frozenset(plan.parts)
                if not fixed:
                    return {fixed}
                names = [name for name, _ in plan.parts]
                return {o for o in model.project(names, len(names), configurations) if fixed <= o}
            if plan.kind == "union":
                return set().union(*(run(p) for p in plan.parts))
            result = {frozenset()}
            for part in plan.parts:
                result = {
                    merged
                    for a, b in product(result, run(part))
                    if (merged := _merge(a, b)) is not None
                }
            return result

        obligations = run(self.plan)
        # Product/fix may introduce conflicts or force an inactive factor.
        # Index projections by their selected names instead of scanning all
        # configurations separately for every obligation.
        groups = {}
        for obligation in obligations:
            names = frozenset(name for name, _ in obligation)
            groups.setdefault(names, set()).add(obligation)
        supported = set()
        for names, candidates in groups.items():
            projections = {
                frozenset((name, value) for name, value in c if name in names)
                for c in configurations
            }
            supported.update(candidates & projections)
        return supported


class DeclarationTarget:
    def __init__(self, definition, observer, constants, *, spec=None):
        self.name = definition.name
        self.aspects = definition.aspects
        self.profiles = dict(definition.profiles)
        self.feasible = definition.feasible
        self.constants = constants
        self.definition, self.observer = definition, observer
        self._bound_spec = spec
        self._cache = {}
        self.bound_constants = {}
        if spec is not None:
            self.bound_constants = {name: getter(spec) for name, getter in constants.items()}
            for node in definition.constants:
                node.domain.validate(self.bound_constants[node.name])
            if definition.constant_feasibility is not None:
                self.feasible = rules(
                    definition.feasible, definition.constant_feasibility(self.bound_constants)
                )
            self.profiles = {
                name: BoundFormula(self, plan) for name, plan in definition.profiles.items()
            }

    @property
    def factors(self):
        return tuple(f for aspect in self.aspects for f in aspect.factors)

    def record(self, observation, granularity):
        return {f.name: f.value(observation, granularity) for f in self.factors}

    def for_spec(self, spec):
        if self._bound_spec is not None:
            if self._bound_spec is not spec:
                raise ValueError("bind a fresh target template to use a different spec")
            return self
        return DeclarationTarget(self.definition, self.observer, self.constants, spec=spec)

    def _configurations(self, granularity, filtered):
        key = (granularity, filtered)
        if key not in self._cache:
            model = self.definition.model(granularity)
            configurations = model.configurations()
            if filtered:
                configurations = {c for c in configurations if self.feasible(dict(c), granularity)}
            self._cache[key] = model, configurations
        return self._cache[key]

    def observation(self, ctx):
        if self._bound_spec is None:
            return self.for_spec(ctx.spec).observation(ctx)
        if ctx.spec is not self._bound_spec:
            raise ValueError("observation spec differs from the target's bound spec")
        attributes = dict(self.observer(ctx))
        expected = {a.name for a in self.definition.attributes}
        if attributes.keys() != expected:
            raise ValueError(
                f"observation attributes mismatch: expected {sorted(expected)}, got {sorted(attributes)}"
            )
        env = {n: MISSING if v is NA else v for n, v in attributes.items()}
        for node in self.definition.attributes:
            if env[node.name] is not MISSING:
                node.domain.validate(env[node.name])
        constants = self.bound_constants
        applicable = self.definition.applicable_when.evaluate(env, constants)
        if type(applicable) is not bool:
            raise ValueError("applicability must be an observed boolean")
        raw = {}

        def evaluate(f):
            if f.name in raw:
                return raw[f.name]
            active = applicable and f.when.evaluate(env, constants, truth)
            available = f.available_when.evaluate(env, constants) if active is True else False
            value = f.value.evaluate(env, constants) if available is True else MISSING
            if value is not MISSING:
                if f.kind == "boolean":
                    Boolean().validate(value)
                elif f.kind == "comparison":
                    Integer().validate(value)
                else:
                    _abstract(f).abstract(value, "predicate")
            raw[f.name] = value
            return value

        def truth(f):
            value = evaluate(f)
            if value is MISSING:
                return MISSING
            return _abstract(f).abstract(value, "predicate")

        for f in self.definition.declarations:
            evaluate(f)
        return {
            **attributes,
            **{n: NA if v is MISSING else v for n, v in raw.items()},
        }

    def review(self, granularity="predicate", *, examples=3):
        if self._bound_spec is None:
            raise ValueError("bind with for_spec(spec) before review")
        d = self.definition
        lines = [
            f"target {d.name}",
            f"focus: {d.focus}",
            f"record: {d.record}",
            f"applicable when: {d.applicable_when.render()}",
        ]
        for node in d.constants:
            lines.append(
                f"constant {node.name} = {self.bound_constants[node.name]!r} ({node.domain})"
            )
        for node in d.attributes:
            lines.append(f"attribute {node.name}: {node.domain}")
        derived_nodes = {
            n.name: n for f in d.declarations for n in _walk(f.value) if n.op == "derived"
        }
        for name, node in derived_nodes.items():
            lines.append(f"derived {name} = {node.args[0].render()}")
        for a in d.aspects:
            lines.append(f"aspect {a.name}")
            for f in a.declarations:
                lines.append(
                    f"  {f.name}: {_abstract(f).domain(granularity)}; kind={f.kind}"
                    f"{(' ' + f.op + ' 0') if f.kind == 'comparison' else ''}; "
                    f"expression={f.value.render()}; when={f.when.render()}; available={f.available_when.render()}"
                )
                if f.description:
                    lines.append(f"    reason: {f.description}")
        lines.append("feasibility: Python callbacks (not solver-translated)")
        for name, formula in self.profiles.items():
            obligations = formula.run(granularity)
            pruned = formula.run(granularity, filtered=False) - obligations
            lines.append(f"profile {name}: {len(obligations)} obligations; {len(pruned)} pruned")
            for o in sorted(obligations, key=lambda o: repr(sorted(o)))[:examples]:
                lines.append(f"  {dict(sorted(o))}")
            for f in d.declarations:
                if _conditions(f.when):
                    for present in (False, True):
                        candidates = [o for o in obligations if (f.name in dict(o)) is present]
                        if candidates:
                            example = min(candidates, key=lambda o: repr(sorted(o)))
                            label = "included" if present else "omitted"
                            lines.append(f"  {f.name} {label}: {dict(sorted(example))}")
        return "\n".join(lines)


def bind(definition, *, observe_attributes, constants=None):
    constants = dict(constants or {})
    if set(constants) != {c.name for c in definition.constants}:
        raise ValueError("constant bindings must exactly match declarations")
    return DeclarationTarget(definition, observe_attributes, constants)
