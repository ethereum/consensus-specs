"""A small coverage DSL for scoring generated vectors against a spec slice.

Layers, bottom up:

attributes  Raw values recovered from a decoded vector (``current_epoch``,
            ``validator.activation_epoch``, a BLS verify result, a queue
            length, ...). ``NA`` marks a value that cannot be recovered.

factors     Coverage dimensions with a finite abstract domain. They are
            *declared inside capture functions* as annotated assignments and
            extracted by parsing the function source:

                @coverage_aspect("epochs")
                def capture_epochs(
                    validator_found: CGate,
                    current_epoch: CAttribute[int],
                    activation_epoch: CAttribute[int],
                    far_future_epoch: CAttribute[int],
                    exit_epoch: CAttribute[int],
                ):
                    if validator_found:
                        activation_le_current: CFactor = activation_epoch <= current_epoch
                        exit_not_initiated: CPred = exit_epoch == far_future_epoch
                    queue: CEnum[Literal["ZERO", "ONE", "MANY"]] = count_class(n)

              CFactor   a comparison ``lhs op rhs`` becomes a comparison factor
                        observed as ``lhs - rhs`` and abstracted by granularity:
                          predicate {True, False}
                          cmp3      {LT, EQ, GT}
                          cmp5      {LT_FAR, LT_1, EQ, GT_1, GT_FAR}
                        any other expression becomes a boolean factor
              CPred     always a boolean factor {True, False}
              CEnum[D]  a categorical factor; ``D`` is ``Literal[...]`` or the
                        name of a module-level tuple of values
            Capture modules should carry ``# ruff: noqa: F841``: factor
            declarations are assignments the function body never reads.
            A factor under an ``if`` is conditional: when the test is false the
            factor is ``NA`` and never satisfies an obligation that mentions it.
            Parameters (``CGate``, ``CAttribute[T]``) and plain assignments in
            the body are recorded as attributes.

            Calling a capture function inside ``recording()`` interprets its body
            with the actual values; ``capture_observations(a, b, ...)`` records
            extra attributes by their variable names.

aspects     A capture function *is* an aspect: a named group of factors with
            ``each`` / ``nwise`` / ``exhaustive`` and ``aspect["factor"]``.

formulas    Lazy set-valued programs over *obligations* (partial assignments
            ``{factor: value}``):
              each(factors)   nwise(factors, t)   exhaustive(factors)   fix(**v)
              f | g (union)   f * g (product)     nwise_of([f, g, ...], t)
              f.where(feasible)                   (prune obligations)
            Filtering by behaviour is a product with ``fix(accepted=True)``.

feasibility Any callable ``(assignment, granularity) -> bool``; Python rules
            here, a MiniZinc satisfiability check would plug into the same hook.

profiles    Named formulas of a target.

Scoring abstracts each vector to a record ``{factor: value | NA}``, runs the
formula, and reports covered / uncovered obligations. Obligations pruned as
infeasible that some vector nevertheless realised are reported as *unexpected*.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import sys
import textwrap
from collections.abc import Callable, Iterable, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from importlib import import_module
from itertools import combinations, product
from pathlib import Path
from typing import Any

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.runner import test_run

# --- attributes ---------------------------------------------------------------


class _NA:
    def __repr__(self) -> str:
        return "NA"

    def __bool__(self) -> bool:
        raise TypeError("NA has no truth value")


NA = _NA()
Observation = dict[str, Any]

GRANULARITIES = ("predicate", "cmp3", "cmp5")
_OPS: dict[str, Callable[[int], bool]] = {
    "<": lambda d: d < 0,
    "<=": lambda d: d <= 0,
    "==": lambda d: d == 0,
    "!=": lambda d: d != 0,
    ">=": lambda d: d >= 0,
    ">": lambda d: d > 0,
}
_AST_OPS = {ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!=", ast.GtE: ">=", ast.Gt: ">"}
_CMP_REPRESENTATIVE = {
    "LT": -1,
    "LT_FAR": -2,
    "LT_1": -1,
    "EQ": 0,
    "GT": 1,
    "GT_1": 1,
    "GT_FAR": 2,
}


# --- factors ------------------------------------------------------------------


@dataclass(frozen=True)
class Factor:
    """A coverage dimension. Its raw observation is stored under ``name``."""

    name: str
    description: str = ""
    gate: str = ""  # source of the enclosing conditions, "" if unconditional

    def domain(self, granularity: str) -> tuple:
        raise NotImplementedError

    def abstract(self, raw: Any, granularity: str) -> Any:
        raise NotImplementedError

    def value(self, obs: Observation, granularity: str) -> Any:
        raw = obs.get(self.name, NA)
        return NA if raw is NA else self.abstract(raw, granularity)

    def holds(self, value: Any, granularity: str) -> bool | None:
        """Truth of the underlying spec predicate for an abstract value, if any."""
        return None


@dataclass(frozen=True)
class Pred(Factor):
    def domain(self, granularity: str) -> tuple:
        return (True, False)

    def abstract(self, raw: Any, granularity: str) -> Any:
        return bool(raw)

    def holds(self, value: Any, granularity: str) -> bool | None:
        return bool(value)


@dataclass(frozen=True)
class Cmp(Factor):
    """``lhs op rhs``, observed as the integer ``lhs - rhs``."""

    op: str = ""
    lhs: str = ""
    rhs: str = ""
    granularity: str | None = None  # pin, overriding the global granularity

    def _g(self, granularity: str) -> str:
        g = self.granularity or granularity
        if g not in GRANULARITIES:
            raise ValueError(f"unknown granularity {g!r}")
        return g

    def domain(self, granularity: str) -> tuple:
        g = self._g(granularity)
        if g == "predicate":
            return (True, False)
        if g == "cmp3":
            return ("LT", "EQ", "GT")
        return ("LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR")

    def abstract(self, raw: Any, granularity: str) -> Any:
        delta = int(raw)
        g = self._g(granularity)
        if g == "predicate":
            return _OPS[self.op](delta)
        if g == "cmp3":
            return "LT" if delta < 0 else "EQ" if delta == 0 else "GT"
        if delta < -1:
            return "LT_FAR"
        if delta > 1:
            return "GT_FAR"
        return {-1: "LT_1", 0: "EQ", 1: "GT_1"}[delta]

    def holds(self, value: Any, granularity: str) -> bool | None:
        if self._g(granularity) == "predicate":
            return bool(value)
        return _OPS[self.op](_CMP_REPRESENTATIVE[value])

    def far(self, value: Any, granularity: str) -> bool | None:
        """Whether ``value`` denotes ``|lhs - rhs| > 1``; None if unknowable."""
        g = self._g(granularity)
        if g == "predicate":
            return None
        if g == "cmp3":
            return None if value != "EQ" else False
        return value in ("LT_FAR", "GT_FAR")


@dataclass(frozen=True)
class Enum(Factor):
    values: tuple = ()

    def domain(self, granularity: str) -> tuple:
        return self.values

    def abstract(self, raw: Any, granularity: str) -> Any:
        if raw not in self.values:
            raise ValueError(f"{self.name}: {raw!r} not in {self.values}")
        return raw


def count_class(n: int) -> str:
    return "ZERO" if n == 0 else "ONE" if n == 1 else "MANY"


# --- capture DSL --------------------------------------------------------------

CGate = bool


class CAttribute[T]:
    """Marker annotation for a capture-function parameter recorded as attribute."""


class CFactor:
    """Marker annotation: comparison factor if the expression is a comparison, else boolean."""


class CPred:
    """Marker annotation: boolean factor."""


class CEnum:
    """Marker annotation ``CEnum[Literal["A", "B"]]`` or ``CEnum[VALUES]``: categorical factor."""

    def __class_getitem__(cls, item):
        return cls


@dataclass
class Recorder:
    attributes: dict[str, Any] = field(default_factory=dict)
    factors: dict[str, Any] = field(default_factory=dict)

    def observation(self) -> Observation:
        return {**self.attributes, **self.factors}


_RECORDER: ContextVar[Recorder | None] = ContextVar("coverage_recorder", default=None)


@contextmanager
def recording():
    rec = Recorder()
    token = _RECORDER.set(rec)
    try:
        yield rec
    finally:
        _RECORDER.reset(token)


def _recorder() -> Recorder:
    rec = _RECORDER.get()
    if rec is None:
        raise RuntimeError("capture_* called outside recording()")
    return rec


def _callee(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


_SOURCE_CACHE: dict[Any, tuple[ast.AST, int]] = {}


def _parsed(code) -> tuple[ast.AST, int]:
    if code not in _SOURCE_CACHE:
        tree = ast.parse(textwrap.dedent(inspect.getsource(code)))
        _SOURCE_CACHE[code] = (tree, code.co_firstlineno - 1)
    return _SOURCE_CACHE[code]


def _positional_names(frame, callee: str) -> list[str]:
    tree, base = _parsed(frame.f_code)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _callee(node.func) == callee):
            continue
        if not node.lineno + base <= frame.f_lineno <= (node.end_lineno or node.lineno) + base:
            continue
        names = []
        for arg in node.args:
            if not isinstance(arg, ast.Name):
                raise TypeError(
                    f"{callee}: positional arguments must be plain names, got "
                    f"{ast.unparse(arg)!r}; use the keyword form"
                )
            names.append(arg.id)
        return names
    raise RuntimeError(f"cannot locate the {callee}(...) call site")


def capture_observations(*values: Any, **named: Any) -> None:
    """Record attributes: ``capture_observations(a, b)`` records ``a`` and ``b`` by name."""
    rec = _recorder()
    if values:
        names = _positional_names(sys._getframe(1), "capture_observations")
        if len(names) != len(values):
            raise RuntimeError("capture_observations: argument count mismatch")
        rec.attributes.update(zip(names, values, strict=True))
    rec.attributes.update(named)


def _enum_values(domain: ast.expr, env: dict) -> tuple:
    if isinstance(domain, ast.Subscript) and _callee(domain.value) == "Literal":
        values = ast.literal_eval(domain.slice)
    elif isinstance(domain, ast.Name):
        values = env[domain.id]
    else:
        raise SyntaxError(f"CEnum[...] takes Literal[...] or a name, got {ast.unparse(domain)}")
    return tuple(values) if isinstance(values, (tuple, list)) else (values,)


def _marker(annotation: ast.expr, env: dict | None = None) -> tuple[str, tuple] | None:
    """Return (kind, enum_values) if ``annotation`` is a factor marker."""
    if isinstance(annotation, ast.Subscript) and _callee(annotation.value) == "CEnum":
        return "enum", _enum_values(annotation.slice, env or {}) if env is not None else ()
    name = _callee(annotation)
    if name == "CFactor":
        return "factor", ()
    if name == "CPred":
        return "pred", ()
    return None


@dataclass
class _Spec:
    factor: Factor
    kind: str  # "cmp" | "pred" | "enum"
    codes: tuple  # compiled (lhs, rhs) for cmp, (expr,) otherwise


class Aspect:
    """A named group of factors."""

    def __init__(self, name: str, factors: Iterable[Factor], description: str = ""):
        self.name = name
        self.factors = tuple(factors)
        self.description = description

    def __getitem__(self, name: str) -> Factor:
        for f in self.factors:
            if f.name == name:
                return f
        raise KeyError(f"{self.name}: no factor {name!r}")

    def each(self) -> Formula:
        return each(self.factors)

    def nwise(self, t: int) -> Formula:
        return nwise(self.factors, t)

    def exhaustive(self) -> Formula:
        return exhaustive(self.factors)


class CapturedAspect(Aspect):
    """An aspect defined by a capture function; parses the body once, interprets on call."""

    def __init__(self, name: str, fn: Callable, description: str = ""):
        self.fn = fn
        self.signature = inspect.signature(fn)
        self.filename = inspect.getsourcefile(fn) or "<capture>"
        tree, self.base = _parsed(fn.__code__)
        fdef = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        self.body = fdef.body
        self.attributes = tuple(a.arg for a in fdef.args.args)
        self.gates = tuple(
            a.arg for a in fdef.args.args if a.annotation and _callee(a.annotation) == "CGate"
        )
        self.specs: dict[str, _Spec] = {}
        self._extract(self.body, [])
        super().__init__(name, (s.factor for s in self.specs.values()), description or fn.__doc__)

    # static extraction ---------------------------------------------------------

    def _compile(self, node: ast.expr):
        expr = ast.Expression(body=node)
        ast.fix_missing_locations(expr)
        ast.increment_lineno(expr, self.base)
        return compile(expr, self.filename, "eval")

    def _extract(self, stmts: list[ast.stmt], gates: list[str]) -> None:
        for stmt in stmts:
            if isinstance(stmt, ast.If):
                test = ast.unparse(stmt.test)
                self._extract(stmt.body, [*gates, test])
                self._extract(stmt.orelse, [*gates, f"not ({test})"])
                continue
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if (marker := _marker(stmt.annotation, self.fn.__globals__)) is None:
                continue
            if not isinstance(stmt.target, ast.Name) or stmt.value is None:
                raise SyntaxError(
                    f"{self.filename}:{stmt.lineno + self.base}: bad factor declaration"
                )
            name, kind, values = stmt.target.id, *marker
            if name in self.specs:
                raise SyntaxError(f"duplicate factor {name!r} in {self.fn.__name__}")
            gate = " and ".join(gates)
            src = ast.unparse(stmt.value)
            value = stmt.value
            if kind == "factor" and isinstance(value, ast.Compare):
                if len(value.ops) != 1 or type(value.ops[0]) not in _AST_OPS:
                    raise SyntaxError(f"{name}: split chained comparisons into separate factors")
                op = _AST_OPS[type(value.ops[0])]
                lhs, rhs = value.left, value.comparators[0]
                factor = Cmp(name, src, gate, op, ast.unparse(lhs), ast.unparse(rhs))
                self.specs[name] = _Spec(factor, "cmp", (self._compile(lhs), self._compile(rhs)))
            elif kind == "enum":
                self.specs[name] = _Spec(
                    Enum(name, src, gate, values), "enum", (self._compile(value),)
                )
            else:
                self.specs[name] = _Spec(Pred(name, src, gate), "pred", (self._compile(value),))

    # interpretation ------------------------------------------------------------

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        bound = self.signature.bind(*args, **kwargs)
        bound.apply_defaults()
        rec = _recorder()
        rec.attributes.update(bound.arguments)
        ns = {**self.fn.__globals__, **bound.arguments}
        self._run(self.body, ns, rec, active=True)

    def _eval(self, code, ns: dict) -> Any:
        return eval(code, ns)  # the DSL body is trusted project source

    def _run(self, stmts: list[ast.stmt], ns: dict, rec: Recorder, *, active: bool) -> None:
        for stmt in stmts:
            if isinstance(stmt, ast.AnnAssign) and _marker(stmt.annotation) is not None:
                spec = self.specs[stmt.target.id]  # type: ignore[union-attr]
                rec.factors[spec.factor.name] = self._observe(spec, ns) if active else NA
            elif isinstance(stmt, ast.If):
                test = bool(self._eval(self._compile(stmt.test), ns)) if active else False
                self._run(stmt.body, ns, rec, active=active and test)
                self._run(stmt.orelse, ns, rec, active=active and not test)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Pass)):
                if active:
                    module = ast.Module(body=[stmt], type_ignores=[])
                    ast.increment_lineno(module, self.base)
                    exec(compile(module, self.filename, "exec"), ns)
            else:
                raise SyntaxError(
                    f"{self.filename}:{stmt.lineno + self.base}: unsupported statement in "
                    f"capture function: {type(stmt).__name__}"
                )

    def _observe(self, spec: _Spec, ns: dict) -> Any:
        if spec.kind == "cmp":
            lhs, rhs = (self._eval(c, ns) for c in spec.codes)
            return NA if lhs is NA or rhs is NA else int(lhs) - int(rhs)
        raw = self._eval(spec.codes[0], ns)
        if raw is NA:
            return NA
        if spec.kind == "pred":
            return bool(raw)
        spec.factor.abstract(raw, "")  # validates the enum domain eagerly
        return raw


def coverage_aspect(name: str, description: str = "") -> Callable[[Callable], CapturedAspect]:
    def decorate(fn: Callable) -> CapturedAspect:
        return CapturedAspect(name, fn, description)

    return decorate


@coverage_aspect("outcome")
def capture_outcome(post_present: CAttribute[bool]):
    """Whether the vector expects a post state (accepted) or a rejection."""
    accepted: CPred = post_present  # noqa: F841


ACCEPTED = capture_outcome["accepted"]


# --- formulas -----------------------------------------------------------------

Assignment = dict[str, Any]
Obligation = frozenset[tuple[str, Any]]
Feasible = Callable[[Assignment, str], bool]


def _merge(a: Obligation, b: Obligation) -> Obligation | None:
    da, db = dict(a), dict(b)
    for k, v in db.items():
        if k in da and da[k] != v:
            return None
    return frozenset({**da, **db}.items())


class Formula:
    """A lazy set of obligations. ``run`` evaluates it at a granularity."""

    def run(self, granularity: str, *, filtered: bool = True) -> set[Obligation]:
        raise NotImplementedError

    def where(self, feasible: Feasible) -> Formula:
        return _Where(self, feasible)

    def __or__(self, other: Formula) -> Formula:
        return _Union((self, other))

    def __mul__(self, other: Formula) -> Formula:
        return _Product((self, other))


@dataclass(frozen=True)
class _NWise(Formula):
    factors: tuple[Factor, ...]
    t: int

    def run(self, granularity: str, *, filtered: bool = True) -> set[Obligation]:
        if not 1 <= self.t <= len(self.factors):
            raise ValueError(f"t must be in 1..{len(self.factors)}")
        out: set[Obligation] = set()
        for subset in combinations(self.factors, self.t):
            for values in product(*(f.domain(granularity) for f in subset)):
                out.add(frozenset(zip((f.name for f in subset), values, strict=True)))
        return out


@dataclass(frozen=True)
class _Fix(Formula):
    values: tuple[tuple[str, Any], ...]

    def run(self, granularity: str, *, filtered: bool = True) -> set[Obligation]:
        return {frozenset(self.values)}


@dataclass(frozen=True)
class _Where(Formula):
    inner: Formula
    feasible: Feasible

    def run(self, granularity: str, *, filtered: bool = True) -> set[Obligation]:
        obligations = self.inner.run(granularity, filtered=filtered)
        if not filtered:
            return obligations
        return {o for o in obligations if self.feasible(dict(o), granularity)}


@dataclass(frozen=True)
class _Union(Formula):
    parts: tuple[Formula, ...]

    def run(self, granularity: str, *, filtered: bool = True) -> set[Obligation]:
        return set().union(*(p.run(granularity, filtered=filtered) for p in self.parts))


@dataclass(frozen=True)
class _Product(Formula):
    parts: tuple[Formula, ...]

    def run(self, granularity: str, *, filtered: bool = True) -> set[Obligation]:
        acc: set[Obligation] = {frozenset()}
        for part in self.parts:
            nxt: set[Obligation] = set()
            for a in acc:
                for b in part.run(granularity, filtered=filtered):
                    m = _merge(a, b)
                    if m is not None:
                        nxt.add(m)
            acc = nxt
        return acc


@dataclass(frozen=True)
class _NWiseOf(Formula):
    parts: tuple[Formula, ...]
    t: int

    def run(self, granularity: str, *, filtered: bool = True) -> set[Obligation]:
        if not 1 <= self.t <= len(self.parts):
            raise ValueError(f"t must be in 1..{len(self.parts)}")
        return set().union(
            *(
                _Product(subset).run(granularity, filtered=filtered)
                for subset in combinations(self.parts, self.t)
            )
        )


def each(factors: Iterable[Factor]) -> Formula:
    return _NWise(tuple(factors), 1)


def nwise(factors: Iterable[Factor], t: int) -> Formula:
    return _NWise(tuple(factors), t)


def exhaustive(factors: Iterable[Factor]) -> Formula:
    fs = tuple(factors)
    return _NWise(fs, len(fs))


def fix(**values: Any) -> Formula:
    return _Fix(tuple(sorted(values.items())))


def union(*parts: Formula) -> Formula:
    return _Union(tuple(parts))


def prod(*parts: Formula) -> Formula:
    return _Product(tuple(parts))


def nwise_of(parts: Sequence[Formula], t: int) -> Formula:
    return _NWiseOf(tuple(parts), t)


def rules(*fns: Feasible) -> Feasible:
    """Conjoin feasibility rules."""

    def feasible(assignment: Assignment, granularity: str) -> bool:
        return all(fn(assignment, granularity) for fn in fns)

    return feasible


# --- targets ------------------------------------------------------------------


@dataclass
class Context:
    spec: Any
    pre: Any
    operation: Any
    post: Any
    meta: dict


@dataclass
class Target:
    name: str
    aspects: tuple[Aspect, ...]
    observe: Callable[[Context], None]
    profiles: dict[str, Formula]
    feasible: Feasible = lambda _a, _g: True

    @property
    def factors(self) -> tuple[Factor, ...]:
        seen: dict[str, Factor] = {}
        for aspect in self.aspects:
            for f in aspect.factors:
                if f.name in seen and seen[f.name] is not f:
                    raise ValueError(f"duplicate factor name {f.name!r}")
                seen[f.name] = f
        return tuple(seen.values())

    def observation(self, ctx: Context) -> Observation:
        """Run ``observe`` under a recorder; the outcome aspect is captured for it."""
        with recording() as rec:
            self.observe(ctx)
            capture_outcome(ctx.post is not None)
        return rec.observation()

    def record(self, obs: Observation, granularity: str) -> dict[str, Any]:
        return {f.name: f.value(obs, granularity) for f in self.factors}


# --- scoring ------------------------------------------------------------------


@dataclass
class Report:
    profile: str
    granularity: str
    total: int
    covered: int
    uncovered: list[dict] = field(default_factory=list)
    unexpected: list[dict] = field(default_factory=list)

    @property
    def percent(self) -> float | None:
        return round(100 * self.covered / self.total, 2) if self.total else None

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "granularity": self.granularity,
            "total": self.total,
            "covered": self.covered,
            "percent": self.percent,
            "uncovered": self.uncovered,
            "unexpected": self.unexpected,
        }


def _satisfied(obligation: Obligation, rec: dict[str, Any]) -> bool:
    return all(rec[name] is not NA and rec[name] == value for name, value in obligation)


def _sorted(obligations: Iterable[Obligation]) -> list[dict]:
    return [dict(sorted(o)) for o in sorted(obligations, key=lambda o: repr(sorted(o)))]


def score(
    target: Target,
    records: Sequence[dict[str, Any]],
    formula: Formula,
    granularity: str,
    profile: str = "",
) -> Report:
    wanted = formula.run(granularity)
    covered = {o for o in wanted if any(_satisfied(o, r) for r in records)}
    pruned = formula.run(granularity, filtered=False) - wanted
    unexpected = {o for o in pruned if any(_satisfied(o, r) for r in records)}
    return Report(
        profile=profile,
        granularity=granularity,
        total=len(wanted),
        covered=len(covered),
        uncovered=_sorted(wanted - covered),
        unexpected=_sorted(unexpected),
    )


# --- vector loading and CLI ---------------------------------------------------

TARGETS = {
    "block_header": "tests.generators.compliance_runners.state_transition.block_header.target",
    "voluntary_exit": "tests.generators.compliance_runners.state_transition.voluntary_exit.target",
    "process_operations": "tests.generators.compliance_runners.state_transition.operations.target",
    "eth1_data_reset": "tests.generators.compliance_runners.state_transition.eth1_data_reset.target",
    "historical_summaries_update": "tests.generators.compliance_runners.state_transition.historical_summaries_update.target",
    "participation_flag_updates": "tests.generators.compliance_runners.state_transition.participation_flag_updates.target",
    "randao_mixes_reset": "tests.generators.compliance_runners.state_transition.randao_mixes_reset.target",
    "slashings_reset": "tests.generators.compliance_runners.state_transition.slashings_reset.target",
    "sync_committee_updates": "tests.generators.compliance_runners.state_transition.sync_committee_updates.target",
}


def load_observations(tests: list[Path], target: Target, preset: str) -> list[Observation]:
    spec = spec_targets[preset]["gloas"]
    out = []
    for case in test_run.gather_tests(tests):
        if case.handler != target.name or case.preset != preset or case.fork != "gloas":
            continue
        tc = test_run.get_test_case(spec, Path(case.test_dir), target.name)
        obs = target.observation(Context(spec, tc["pre"], tc["operation"], tc["post"], tc["meta"]))
        obs["_case"] = str(case.test_dir)
        out.append(obs)
    if not out:
        raise ValueError(f"no {preset}/gloas vectors for {target.name} under {tests}")
    return out


def describe(target: Target) -> str:
    lines = [f"target {target.name}"]
    for aspect in target.aspects:
        lines.append(f"  aspect {aspect.name}")
        for f in aspect.factors:
            kind = type(f).__name__.lower()
            gate = f"  [if {f.gate}]" if f.gate else ""
            lines.append(f"    {f.name:<26} {kind:<5} {f.description}{gate}")
    return "\n".join(lines)


def _format(report: Report, max_uncovered: int) -> str:
    lines = [
        f"  {report.profile:<14} {report.covered:>5}/{report.total:<5} ({report.percent}%)",
    ]
    for item in report.uncovered[:max_uncovered]:
        lines.append(f"      missing    {item}")
    if len(report.uncovered) > max_uncovered:
        lines.append(f"      ... {len(report.uncovered) - max_uncovered} more")
    for item in report.unexpected:
        lines.append(f"      UNEXPECTED (pruned as infeasible, yet observed) {item}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score vectors with a target's coverage profiles")
    parser.add_argument("--tests", type=Path, nargs="+", required=True)
    parser.add_argument("--target", choices=sorted(TARGETS), default="voluntary_exit")
    parser.add_argument("--preset", choices=("minimal", "mainnet"), default="minimal")
    parser.add_argument("--granularity", choices=GRANULARITIES, action="append")
    parser.add_argument("--profile", action="append", help="default: every profile")
    parser.add_argument("--max-uncovered", type=int, default=10)
    parser.add_argument("--describe", action="store_true", help="print the extracted factors")
    parser.add_argument("--records", action="store_true", help="dump abstracted records")
    parser.add_argument("--json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    target: Target = import_module(TARGETS[args.target]).TARGET
    if args.describe:
        print(describe(target))
    observations = load_observations(args.tests, target, args.preset)
    granularities = args.granularity or list(GRANULARITIES)
    profiles = args.profile or list(target.profiles)
    unknown = set(profiles) - target.profiles.keys()
    if unknown:
        raise SystemExit(f"unknown profile(s) {sorted(unknown)}; have {sorted(target.profiles)}")

    result: dict[str, Any] = {
        "target": target.name,
        "preset": args.preset,
        "vectors": len(observations),
        "aspects": {a.name: [f.name for f in a.factors] for a in target.aspects},
        "granularities": {},
    }
    print(f"{target.name}/{args.preset}: {len(observations)} vectors")
    for granularity in granularities:
        records = [target.record(o, granularity) for o in observations]
        if args.records:
            for obs, rec in zip(observations, records, strict=True):
                print(f"  {Path(obs['_case']).name}: {rec}")
        print(f"granularity={granularity}")
        reports = [score(target, records, target.profiles[p], granularity, p) for p in profiles]
        result["granularities"][granularity] = [r.as_dict() for r in reports]
        for report in reports:
            print(_format(report, args.max_uncovered))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return result


if __name__ == "__main__":
    main()
