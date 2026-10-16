"""Explicit coverage specifications, binding, observation, and review.

Expression trees are defined in the shared coverage_model tool. This adapter
adds observation, conditional coverage formulas, spec binding, and review text.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from itertools import chain, combinations, product

from tests.generators.compliance_runners.tools import conditional_factors as conditional
from tests.generators.compliance_runners.tools.coverage_model import (
    _BINARY,
    all_of,
    any_of,
    attribute,
    Boolean,
    Bytes,
    categorical,
    choose,
    cmp3,
    cmp5,
    comparison,
    constant,
    count,
    coverage_value,
    derived,
    dimension,
    DomainUnion,
    Expr,
    expression,
    Factor,
    factor,
    Finite,
    identity,
    implies,
    Integer,
    maximum,
    MISSING,
    modulo,
    modulo_boundary,
    predicate,
    present,
)

from .backend_config import BACKENDS, DEFAULT_BACKEND, DEFAULT_SOLVER
from .coverage_dsl import _merge, Cmp, Enum, NA, Pred, rules

__all__ = [
    "AssertionSet",
    "Boolean",
    "Bytes",
    "DomainUnion",
    "Finite",
    "Integer",
    "all_of",
    "any_of",
    "aspect",
    "assertion",
    "assertion_set",
    "attribute",
    "bind",
    "categorical",
    "choose",
    "cmp3",
    "cmp5",
    "comparison",
    "constant",
    "count",
    "coverage_spec",
    "coverage_value",
    "derived",
    "dimension",
    "each",
    "exhaustive",
    "factor",
    "fix",
    "identity",
    "implies",
    "maximum",
    "modulo",
    "modulo_boundary",
    "nwise",
    "predicate",
    "present",
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
    def __init__(self, name, factors, constants=None, *, applicable=True):
        self.name = name
        self.declarations = tuple(factors)
        self.factors = tuple(
            _abstract(f, constants, applicable=applicable) for f in self.declarations
        )

    def __getitem__(self, name):
        return next(f for f in self.factors if f.name == name)

    def ref(self, name):
        """Return the symbolic declaration for activation or feasibility."""
        return next(f for f in self.declarations if f.name == name)

    def each(self):
        return each(self.declarations)

    def nwise(self, strength):
        return nwise(self.declarations, strength)

    def exhaustive(self):
        return exhaustive(self.declarations)


def aspect(name, *factors):
    return Aspect(name, factors)


@dataclass(frozen=True, eq=False)
class Assertion(Factor):
    """A dimension whose predicate must hold for normal behavior."""


def assertion(name, value, **kwargs):
    declaration = dimension(name, value, **kwargs)
    if declaration.kind not in ("boolean", "comparison"):
        raise TypeError("assertions require a boolean predicate or comparison mapping")
    return Assertion(**{f.name: getattr(declaration, f.name) for f in fields(Factor)})


@dataclass(frozen=True)
class AssertionResult:
    failed: tuple[str, ...]
    unknown: tuple[str, ...]

    @property
    def fault_count(self):
        """Exact count, or None if any applicable assertion is unavailable."""
        return None if self.unknown else len(self.failed)

    @property
    def expected_accepted(self):
        if self.failed:
            return False
        return None if self.unknown else True


class AssertionSet:
    """Shared assertion semantics, independent of observed execution outcome.

    ``complete`` means these assertions fully characterize acceptance within
    the declared target scope. Otherwise passing them predicts only that this
    slice passes; a rejected execution is not necessarily a mismatch.
    """

    def __init__(self, *members, observed=None, complete=False):
        declarations = tuple(
            f
            for member in members
            for f in (member.declarations if isinstance(member, Aspect) else (member,))
            if isinstance(f, Assertion)
        )
        if not declarations or len({f.name for f in declarations}) != len(declarations):
            raise ValueError("assertion sets need nonempty, unique assertion declarations")
        if any(not isinstance(m, (Aspect, Assertion)) for m in members):
            raise TypeError("assertion sets accept assertions and aspects")
        if observed is not None and (
            not isinstance(observed, Factor) or observed.kind != "boolean"
        ):
            raise TypeError("observed outcome must be a boolean dimension")
        self.declarations = declarations
        self.observed = observed
        self.complete = complete

    def evaluate(self, assignment, constants=None):
        assignment = {k: v for k, v in assignment.items() if v is not NA and v is not MISSING}
        failed, unknown = [], []
        for f in self.declarations:
            active = _evaluate_constraint(f.when, assignment, constants or {})
            if active is False:
                continue
            value = _evaluate_constraint(expression(f), assignment, constants or {})
            if active is MISSING or value is MISSING:
                unknown.append(f.name)
            elif value is False:
                failed.append(f.name)
        return AssertionResult(tuple(failed), tuple(unknown))

    def agrees(self, assignment, constants=None):
        expected = self.evaluate(assignment, constants).expected_accepted
        observed = assignment.get(self.observed.name, NA) if self.observed is not None else NA
        if observed is NA or observed is MISSING or expected is None:
            return True
        return observed == expected if self.complete or expected is False else True

    def faults(self, plan, *, minimum=0, maximum=None):
        """Restrict both configuration enumeration and scoring to a fault range."""
        if (
            type(minimum) is not int
            or minimum < 0
            or (maximum is not None and (type(maximum) is not int or maximum < minimum))
        ):
            raise ValueError("fault limits must be nonnegative integers with minimum <= maximum")
        return Plan("faults", (self, plan, minimum, maximum))

    def normal(self, plan):
        return self.faults(plan, maximum=0)

    def exceptional(self, plan, *, faults=None):
        if faults is None:
            return self.faults(plan, minimum=1)
        if type(faults) is int:
            minimum = maximum = faults
        else:
            minimum, maximum = faults
        if minimum < 1:
            raise ValueError("exceptional profiles require at least one fault")
        return self.faults(plan, minimum=minimum, maximum=maximum)


assertion_set = AssertionSet


def _within_faults(scope, assignment, constants):
    assertions, minimum, maximum = scope
    result = assertions.evaluate(assignment, constants)
    # An unknown assertion cannot establish an exact count or an upper bound.
    return len(result.failed) >= minimum and (
        maximum is None or (not result.unknown and len(result.failed) <= maximum)
    )


def _constant_factor_value(f, constants):
    """Evaluate only values whose activation and availability are known true."""
    if not all(node.op == "constant" and node.name in constants for node in f.value.inputs()):
        return MISSING

    def truth(parent):
        value = _constant_factor_value(parent, constants)
        if value is MISSING:
            return MISSING
        if parent.kind == "comparison":
            return Cmp(parent.name, op=parent.op).abstract(value)
        return value

    if f.when.evaluate({}, constants, truth) is not True:
        return MISSING
    if not all(
        node.op == "constant" and node.name in constants for node in f.available_when.inputs()
    ):
        return MISSING
    if f.available_when.evaluate({}, constants) is not True:
        return MISSING
    return f.value.evaluate({}, constants)


def _abstract(f, constants=None, *, applicable=True):
    description = f.description or f.value.render()
    value = (
        _constant_factor_value(f, constants)
        if f.exact_dimension and constants is not None and applicable is True
        else MISSING
    )
    if value is not MISSING:
        if f.kind == "boolean":
            return Pred(f.name, description, (value,))
        if value not in f.values:
            raise ValueError(f"{f.name}: bound value {value!r} is outside the coverage domain")
        return Enum(f.name, description, (value,))
    if f.kind == "comparison":
        bounds = f.value.integer_domain(constants)
        return Cmp(
            f.name, description, f.op, granularity=f.granularity, bounds=(bounds.min, bounds.max)
        )
    if f.kind == "enum":
        values = f.values
        if f.modulus is not None:
            period = f.modulus.integer_domain(constants).max
            if period is not None:
                values = tuple(
                    v for v, minimum in zip(values, (1, 2, 3, 4), strict=True) if period >= minimum
                )
        return Enum(f.name, description, values)
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


def _collect_inputs(expressions, kind):
    """Collect declarations by identity in first-reference order."""
    inputs = {}
    for expr in expressions:
        for node in expr.inputs():
            if node.op == kind:
                inputs.setdefault(id(node), node)
    return tuple(inputs.values())


def _evaluate_constraint(node, assignment, constants):
    """Evaluate over abstract values, retaining unknown inactive references.

    Boolean connectives use three-valued logic: a known violation must not be
    hidden by an inactive reference elsewhere in a conjunction.
    """
    if node.op in ("factor", "coverage", "present"):
        f = node.args[0]
        if node.op == "present":
            return f.name in assignment
        value = assignment.get(f.name, MISSING)
        if value is NA:
            value = MISSING
        if value is MISSING or node.op == "coverage" or f.kind == "enum":
            return value
        if f.kind == "boolean":
            return bool(value)
        return Cmp(f.name, op=f.op, granularity=f.granularity).holds(value)
    if node.op in ("literal", "constant"):
        return node.evaluate({}, constants)
    first = _evaluate_constraint(node.args[0], assignment, constants)
    if node.op == "choose":
        if first is MISSING:
            return MISSING
        return _evaluate_constraint(node.args[1 if first else 2], assignment, constants)
    if node.op in ("&", "|") and first is (node.op == "|"):
        return first
    values = [first] + [_evaluate_constraint(arg, assignment, constants) for arg in node.args[1:]]
    if node.op in ("&", "|"):
        decisive = node.op == "|"
        if any(value is decisive for value in values):
            return decisive
        if any(value is MISSING for value in values):
            return MISSING
        return not decisive
    if any(value is MISSING for value in values):
        return MISSING
    if node.op == "derived":
        return values[0]
    if node.op == "~":
        return not values[0]
    return _BINARY[node.op](*values)


class Specification:
    def __init__(
        self,
        name,
        *,
        focus,
        record,
        attributes=None,
        constants=None,
        aspects,
        profiles,
        applicable_when=True,
        constraints=(),
        assertions=None,
        feasible=None,
        constant_feasibility=None,
    ):
        self.name, self.focus, self.record = name, focus, record
        self.aspects, self.profiles = tuple(aspects), dict(profiles)
        self.applicable_when = expression(applicable_when)
        if self.applicable_when.result_type() is not bool:
            raise TypeError("applicability must be boolean")
        self._feasible_callback, self.constant_feasibility = feasible, constant_feasibility
        self.constraints = tuple(expression(c) for c in constraints)
        self.declarations = tuple(f for a in self.aspects for f in a.declarations)
        expressions = [self.applicable_when]
        for f in self.declarations:
            expressions.extend((f.value, f.when, f.available_when))
        input_expressions = [*expressions, *self.constraints]
        self.attributes = (
            _collect_inputs(input_expressions, "attribute")
            if attributes is None
            else tuple(attributes)
        )
        self.constants = (
            _collect_inputs(input_expressions, "constant")
            if constants is None
            else tuple(constants)
        )
        self.by_name = {f.name: f for f in self.declarations}
        self.assertions = assertions
        if assertions is not None:
            if not isinstance(assertions, AssertionSet):
                raise TypeError("assertions must be an assertion set")
            for f in (
                *assertions.declarations,
                *((assertions.observed,) if assertions.observed is not None else ()),
            ):
                if self.by_name.get(f.name) is not f:
                    raise ValueError("assertion set references undeclared factor")
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
            if not isinstance(node.domain, (Integer, Boolean, Bytes, Finite, DomainUnion)):
                raise TypeError("unsupported input domain")
        for f in self.declarations:
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
            if any(n.op in ("factor", "coverage", "present") for n in _walk(expr)):
                raise ValueError("factor references are only supported in activation")
        for constraint in self.constraints:
            if constraint.result_type() is not bool:
                raise TypeError("feasibility constraints must be boolean")
            for node in _walk(constraint):
                if node.op == "attribute":
                    raise ValueError(
                        "feasibility constraints use factors and constants, not raw attributes"
                    )
                if node.op == "constant" and not any(node is c for c in self.constants):
                    raise ValueError(f"undeclared constraint constant: {node.name}")
                if node.op in ("factor", "coverage", "present"):
                    f = node.args[0]
                    if self.by_name.get(f.name) is not f:
                        raise ValueError(f"undeclared constraint factor: {f.name}")
        self.model()  # Validate dependencies, including cycles.
        for plan in self.profiles.values():
            self._validate_plan(plan)

    def feasible(self, assignment, constants=None):
        """Check declared constraints and any concrete-witness callback."""
        return (
            (self.assertions is None or self.assertions.agrees(assignment, constants))
            and (self._feasible_callback is None or self._feasible_callback(assignment))
            and all(
                _evaluate_constraint(rule, assignment, constants or {}) is not False
                for rule in self.constraints
            )
        )

    def _known_applicability(self, constants):
        if constants is None:
            return MISSING
        return self.applicable_when.evaluate(
            {node.name: MISSING for node in self.attributes}, constants
        )

    def abstraction(self, f, constants=None):
        return _abstract(f, constants, applicable=self._known_applicability(constants))

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
        elif plan.kind == "faults":
            assertions, inner, _, _ = plan.parts
            if assertions is not self.assertions:
                raise ValueError("profile uses an unregistered assertion set")
            self._validate_plan(inner)
        elif plan.kind in ("union", "product"):
            for p in plan.parts:
                self._validate_plan(p)
        else:
            raise ValueError(f"unknown formula: {plan.kind}")

    def model(self, constants=None):
        factors = []
        for f in self.declarations:
            allowed = []
            for condition in _conditions(f.when):
                parent, value, truth, *op = condition
                abstraction = self.abstraction(parent, constants)
                if truth and parent.kind == "enum":
                    raise ValueError("categorical activation needs an explicit value")
                values = tuple(
                    v
                    for v in abstraction.domain()
                    if (
                        abstraction.holds(v) == value
                        if truth
                        else ((v == value) if op[0] == "==" else (v != value))
                    )
                )
                if not truth and value not in parent.values:
                    raise ValueError(f"activation value outside domain of {parent.name}")
                allowed.append((parent.name, values))
            factors.append(
                conditional.Factor(
                    f.name, self.abstraction(f, constants).domain(), allowed=tuple(allowed)
                )
            )
        return conditional.Model(factors)


coverage_spec = Specification


class BoundFormula:
    def __init__(self, owner, plan):
        self.owner, self.plan = owner, plan
        self._compiled_cache = {}

    def _branches(self, plan):
        """Distribute scoped union/product branches, preserving record restrictions."""
        if plan.kind == "faults":
            assertions, inner, minimum, maximum = plan.parts
            return [
                (p, (*scopes, (assertions, minimum, maximum)))
                for p, scopes in self._branches(inner)
            ]
        if plan.kind == "union":
            return [branch for p in plan.parts for branch in self._branches(p)]
        if plan.kind == "product":
            return [
                (
                    Plan("product", tuple(p for p, _ in parts)),
                    tuple(s for _, scopes in parts for s in scopes),
                )
                for parts in product(*(self._branches(p) for p in plan.parts))
            ]
        return [(plan, ())]

    def _scoped(self, filtered=True):
        _, configurations = self.owner._configurations(filtered)
        for plan, scopes in self._branches(self.plan):
            selected = (
                {
                    c
                    for c in configurations
                    if all(_within_faults(s, dict(c), self.owner.bound_constants) for s in scopes)
                }
                if scopes
                else configurations
            )
            yield plan, scopes, selected

    def _compiled(self, filtered=True):
        if filtered not in self._compiled_cache:
            if self.owner.backend == "minizinc":
                backend = self.owner._solver_backend()
                self._compiled_cache[filtered] = [
                    (
                        scopes,
                        configurations := backend.configurations(filtered=filtered, scopes=scopes),
                        backend.obligations(plan, configurations),
                    )
                    for plan, scopes in self._solver_branches()
                ]
            else:
                self._compiled_cache[filtered] = [
                    (scopes, configurations, self._run(plan, configurations))
                    for plan, scopes, configurations in self._scoped(filtered)
                ]
        return self._compiled_cache[filtered]

    def _solver_branches(self):
        # Preserve shared subplans for the large-model Python projection
        # fallback; distributing unscoped products would duplicate their work.
        if (
            self.owner.definition.assertions is None
            and self.owner._solver_backend().python_projection
        ):
            return [(self.plan, ())]
        groups = {}
        for plan, scopes in self._branches(self.plan):
            groups.setdefault(scopes, []).append(plan)
        return [(union(*parts), scopes) for scopes, parts in groups.items()]

    def to_minizinc(self, *, filtered=True):
        """Export feasibility and projection sources for each distinct fault scope.

        Projection sources embed the solved finite rows from their feasibility
        stage. Exporting them therefore requires the selected MiniZinc solver.
        """
        from .minizinc_backend import Projection  # noqa: PLC0415 - optional backend

        backend = self.owner._solver_backend()
        return tuple(
            {
                "feasibility": backend.configuration_source(filtered=filtered, scopes=scopes),
                "coverage": Projection(
                    backend.model, backend.configurations(filtered=filtered, scopes=scopes)
                ).source(plan),
            }
            for plan, scopes in self._solver_branches()
        )

    def run(self, *, filtered=True):
        return set().union(*(obligations for _, _, obligations in self._compiled(filtered)))

    def covered(self, records, *, filtered=True):
        if not filtered:
            return self._observed_obligations(records)
        covered = set()
        for scopes, _, obligations in self._compiled(filtered):
            eligible = [
                r
                for r in records
                if all(_within_faults(s, r, self.owner.bound_constants) for s in scopes)
            ]
            covered.update(
                o
                for o in obligations
                if any(all(r.get(n, NA) is not NA and r[n] == v for n, v in o) for r in eligible)
            )
        return covered

    def _observed_obligations(self, records):
        """Project only obligations that supplied records can satisfy.

        Unexpected-record detection needs raw structural support, not every
        unfiltered configuration. Check existential completions of observed
        projections, retaining conditional activation and branch fault scopes.
        """
        model = self.owner.definition.model(self.owner.bound_constants)
        support_cache = {}
        branches = (
            [(self.plan, ())]
            if self.owner.definition.assertions is None
            else self._branches(self.plan)
        )
        covered = set()
        for plan, scopes in branches:
            required = {f.name for assertions, _, _ in scopes for f in assertions.declarations}

            def supported(obligation, inactive=frozenset(), scopes=scopes, required=required):
                key = obligation, inactive, scopes
                if key not in support_cache:
                    support_cache[key] = model.has_completion(
                        dict(obligation),
                        inactive=inactive,
                        required=required,
                        predicate=(
                            (
                                lambda values: all(
                                    _within_faults(s, values, self.owner.bound_constants)
                                    for s in scopes
                                )
                            )
                            if scopes
                            else None
                        ),
                    )
                return support_cache[key]

            for record in records:
                if not all(_within_faults(s, record, self.owner.bound_constants) for s in scopes):
                    continue
                cache = {}

                def projection(names, record=record):
                    included = model._closure(names)
                    if any(record.get(name, NA) is NA for name in included):
                        return None
                    return frozenset((name, record[name]) for name in included)

                def run(node, cache=cache):
                    key = id(node)
                    if key not in cache:
                        cache[key] = evaluate(node)
                    return cache[key]

                def evaluate(node, record=record):
                    if node.kind == "nwise":
                        names = [f.name for f in node.parts]
                        known = [name for name in names if record.get(name, NA) is not NA]
                        result = set()
                        # A short projection contains *all* active selected
                        # factors. Unconditional factors, and children enabled
                        # by their observed values, must therefore be present.
                        mandatory = {name for name in names if not model._by_name[name].conditions}
                        disabled = set()
                        pending = set(names) - mandatory
                        while pending:
                            previous = len(pending)
                            for name in tuple(pending):
                                conditions = model._by_name[name].conditions
                                if any(
                                    parent in disabled
                                    or (
                                        parent in mandatory and record.get(parent, NA) not in values
                                    )
                                    for parent, values in conditions
                                ):
                                    disabled.add(name)
                                elif all(
                                    parent in mandatory and record.get(parent, NA) in values
                                    for parent, values in conditions
                                ):
                                    mandatory.add(name)
                                else:
                                    continue
                                pending.remove(name)
                            if len(pending) == previous:
                                break
                        selections = combinations(known, node.strength)
                        if mandatory <= set(known):
                            optional = set(known) - mandatory - disabled
                            selections = chain(
                                selections,
                                (
                                    tuple(mandatory) + selected
                                    for size in range(
                                        max(1, len(mandatory)), min(node.strength, len(known) + 1)
                                    )
                                    for selected in combinations(
                                        sorted(optional), size - len(mandatory)
                                    )
                                ),
                            )
                        for selected in selections:
                            obligation = projection(selected)
                            inactive = (
                                frozenset(set(names) - set(selected))
                                if len(selected) < node.strength
                                else frozenset()
                            )
                            if obligation is not None and supported(obligation, inactive):
                                result.add(obligation)
                        return result
                    if node.kind == "fix":
                        for name, value in node.parts:
                            if value not in model._by_name[name].values:
                                raise ValueError(f"invalid fixed value: {name}={value!r}")
                        if any(record.get(name, NA) != value for name, value in node.parts):
                            return set()
                        obligation = projection(name for name, _ in node.parts)
                        return (
                            {obligation}
                            if obligation is not None and supported(obligation)
                            else set()
                        )
                    if node.kind == "union":
                        return set().union(*(run(part) for part in node.parts))
                    result = {frozenset()}
                    for part in node.parts:
                        result = {
                            merged
                            for left, right in product(result, run(part))
                            if (merged := _merge(left, right)) is not None and supported(merged)
                        }
                    return result

                covered.update(run(plan))
        return covered

    def generation_obligations(self):
        """Return complete feasible witnesses within each formula branch.

        Preserve fault scopes and explicit values, preferring consistent
        acceptance and fewer faults. Coverage projections remain available
        through ``run()`` and are independent of witness completion.
        """
        result = set()
        model = self.owner.definition.model(self.owner.bound_constants)
        for _scopes, configurations, obligations in self._compiled():
            assertions = self.owner.definition.assertions

            def preference(configuration, assertions=assertions):
                if assertions is None:
                    return False, (False, 0)
                values = dict(configuration)
                summary = assertions.evaluate(values, self.owner.bound_constants)
                expected = summary.expected_accepted
                observed = (
                    values.get(assertions.observed.name)
                    if assertions.observed is not None
                    else expected
                )
                faults = (summary.fault_count is None, summary.fault_count or 0)
                return observed != expected, faults

            result.update(model.complete(obligations, configurations, preference=preference))
        return result

    def _run(self, selected_plan, configurations):
        model = self.owner.definition.model(self.owner.bound_constants)
        cache = {}

        def run(plan):
            key = id(plan)
            if key not in cache:
                cache[key] = evaluate(plan)
            return cache[key]

        def evaluate(plan):
            if plan.kind == "nwise":
                return model.project([f.name for f in plan.parts], plan.strength, configurations)
            if plan.kind == "fix":
                for name, value in plan.parts:
                    if (
                        value
                        not in self.owner.definition.abstraction(
                            self.owner.definition.by_name[name], self.owner.bound_constants
                        ).domain()
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

        obligations = run(selected_plan)
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
    def __init__(
        self,
        definition,
        observer,
        constants,
        *,
        spec=None,
        backend=DEFAULT_BACKEND,
        solver=DEFAULT_SOLVER,
    ):
        if backend not in BACKENDS:
            raise ValueError(f"unknown backend: {backend}")
        self.backend, self.solver = backend, solver
        self.name = definition.name
        self.aspects = definition.aspects
        self.profiles = dict(definition.profiles)
        self.feasible = lambda assignment: definition.feasible(assignment, self.bound_constants)
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
                    self.feasible, definition.constant_feasibility(self.bound_constants)
                )
            self.aspects = tuple(
                Aspect(
                    a.name,
                    a.declarations,
                    self.bound_constants,
                    applicable=definition._known_applicability(self.bound_constants),
                )
                for a in definition.aspects
            )
            self.profiles = {
                name: BoundFormula(self, plan) for name, plan in definition.profiles.items()
            }

    @property
    def factors(self):
        return tuple(f for aspect in self.aspects for f in aspect.factors)

    def record(self, observation):
        return {f.name: f.value(observation) for f in self.factors}

    def assertion_result(self, record):
        """Expected outcome and faults computed independently of observed acceptance."""
        if self.definition.assertions is None:
            return None
        return self.definition.assertions.evaluate(record, self.bound_constants)

    def for_spec(self, spec, *, backend=None, solver=None):
        if self._bound_spec is not None:
            if self._bound_spec is not spec:
                raise ValueError("bind a fresh target template to use a different spec")
            if (backend is not None and backend != self.backend) or (
                solver is not None and solver != self.solver
            ):
                raise ValueError(
                    "bind a fresh target template to use a different backend or solver"
                )
            return self
        return DeclarationTarget(
            self.definition,
            self.observer,
            self.constants,
            spec=spec,
            backend=self.backend if backend is None else backend,
            solver=self.solver if solver is None else solver,
        )

    def _configurations(self, filtered):
        key = filtered
        if key not in self._cache:
            model = self.definition.model(self.bound_constants)
            if self.backend == "minizinc":
                configurations = self._solver_backend().configurations(filtered=filtered)
            else:
                configurations = model.configurations()
                if filtered:
                    configurations = {c for c in configurations if self.feasible(dict(c))}
            self._cache[key] = model, configurations
        return self._cache[key]

    def _solver_backend(self):
        from .minizinc_backend import Backend  # noqa: PLC0415 - optional backend

        if not hasattr(self, "_minizinc_backend"):
            self._minizinc_backend = Backend(self)
        return self._minizinc_backend

    def to_minizinc(self, *, filtered=True):
        """Export finite feasibility, including explicit legacy-callback tables."""
        if self._bound_spec is None:
            raise ValueError("bind the target with for_spec(spec) before exporting")
        return self._solver_backend().configuration_source(filtered=filtered)

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
                    self.definition.abstraction(f, constants).abstract(value)
            raw[f.name] = value
            return value

        def truth(f):
            value = evaluate(f)
            if value is MISSING:
                return MISSING
            abstraction = self.definition.abstraction(f, constants)
            abstract = abstraction.abstract(value)
            return abstraction.holds(abstract) if f.kind == "comparison" else abstract

        for f in self.definition.declarations:
            evaluate(f)
        return {
            **attributes,
            **{n: NA if v is MISSING else v for n, v in raw.items()},
        }

    def review(self, *, examples=3):
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
                    f"  {'assertion ' if isinstance(f, Assertion) else ''}{f.name}: {d.abstraction(f, self.bound_constants).domain()}; kind={f.kind}"
                    f"{(' ' + f.op + ' 0') if f.kind == 'comparison' else ''}; "
                    f"{('granularity=' + f.granularity + '; ') if f.kind == 'comparison' else ''}"
                    f"expression={f.value.render()}; when={f.when.render()}; available={f.available_when.render()}"
                )
                if f.description:
                    lines.append(f"    reason: {f.description}")
        if d.assertions is not None:
            lines.append(
                f"assertions: {[f.name for f in d.assertions.declarations]}; complete={d.assertions.complete}"
            )
            if d.assertions.observed is not None:
                lines.append(
                    f"observed outcome: {d.assertions.observed.name}; expected outcome: assertion predicate truth"
                )
        for constraint in d.constraints:
            lines.append(f"constraint: {constraint.render()}")
        lines.append(
            "feasibility: MiniZinc constraints and optional callback tables"
            if self.backend == "minizinc"
            else "feasibility: abstract constraints and optional Python callbacks"
        )
        for name, formula in self.profiles.items():
            for _, scopes in formula._branches(formula.plan):
                if scopes:
                    limits = [(minimum, maximum) for _, minimum, maximum in scopes]
                    lines.append(f"profile {name} branch fault limits (inclusive): {limits}")
            obligations = formula.run()
            pruned = formula.run(filtered=False) - obligations
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


def bind(
    definition,
    *,
    observe_attributes,
    constants=None,
    backend=DEFAULT_BACKEND,
    solver=DEFAULT_SOLVER,
):
    constants = dict(constants or {})
    if set(constants) != {c.name for c in definition.constants}:
        raise ValueError("constant bindings must exactly match declarations")
    return DeclarationTarget(
        definition, observe_attributes, constants, backend=backend, solver=solver
    )
