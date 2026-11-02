"""Finite conditional-factor enumeration, independent of coverage capture/scoring.

Activation is a conjunction of prerequisite factor/value pairs. Dependencies
must be acyclic. Forbidden combinations constrain active values only. Both
backends enumerate complete valid configurations; obligations are projections
onto selected active factors and their recursive prerequisites. This deliberately
simple reference implementation is exponential in the complete model size.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations, product

Value = bool | int | str
Obligation = frozenset[tuple[str, Value]]


@dataclass(frozen=True)
class Factor:
    name: str
    values: tuple[Value, ...]
    requires: tuple[tuple[str, Value], ...] = ()
    allowed: tuple[tuple[str, tuple[Value, ...]], ...] = ()

    @property
    def conditions(self):
        return tuple((name, (value,)) for name, value in self.requires) + self.allowed


class Model:
    def __init__(self, factors: Iterable[Factor], forbidden: Iterable[Obligation] = ()):
        self.factors = tuple(factors)
        self.forbidden = tuple(frozenset(c) for c in forbidden)
        self._by_name = {f.name: f for f in self.factors}
        if not self.factors or len(self._by_name) != len(self.factors):
            raise ValueError("expected nonempty factors with unique names")
        for f in self.factors:
            if not f.name or not f.values or any(type(v) not in (bool, int, str) for v in f.values):
                raise ValueError("factors need a name and a nonempty bool/int/str domain")
            if len(set(f.values)) != len(f.values):
                raise ValueError(f"duplicate or equality-ambiguous values for {f.name}")
            for parent, _ in f.conditions:
                if parent not in self._by_name:
                    raise ValueError(f"unknown activation factor: {parent}")
        for literals in (
            *self.forbidden,
            *(tuple((n, v) for n, vs in f.conditions for v in vs) for f in self.factors),
        ):
            for name, value in literals:
                if name not in self._by_name or value not in self._by_name[name].values:
                    raise ValueError(f"unknown factor/value: {(name, value)!r}")
        ordered = []
        visiting = set()
        visited = set()

        def visit(name):
            if name in visiting:
                raise ValueError(f"cyclic activation dependency at {name}")
            if name in visited:
                return
            visiting.add(name)
            for parent, _ in self._by_name[name].conditions:
                visit(parent)
            visiting.remove(name)
            visited.add(name)
            ordered.append(self._by_name[name])

        for f in self.factors:
            visit(f.name)
        self._ordered = tuple(ordered)

    def _selection(self, selected):
        names = tuple(selected)
        if not names or len(set(names)) != len(names) or any(n not in self._by_name for n in names):
            raise ValueError("select nonempty, unique, known factor names")
        return names

    def configurations(self, *, backend="python", solver="gecode") -> set[Obligation]:
        """Return all valid configurations, omitting inactive factors."""
        if backend == "minizinc":
            import minizinc  # noqa: PLC0415 - optional backend

            model = minizinc.Model()
            model.add_string(self.to_minizinc())
            result = minizinc.Instance(minizinc.Solver.lookup(solver), model).solve(
                all_solutions=True
            )
            if result.status == minizinc.Status.UNSATISFIABLE:
                return set()
            if result.status != minizinc.Status.ALL_SOLUTIONS:
                raise RuntimeError(f"incomplete MiniZinc enumeration: {result.status}")
            return {
                frozenset(
                    (f.name, f.values[code - 1])
                    for i, f in enumerate(self.factors)
                    if (code := getattr(solution, f"v_{i}")) != 0
                )
                for solution in result.solution
            }
        if backend != "python":
            raise ValueError(f"unknown backend: {backend}")
        configurations = set()
        for values in product(*(f.values for f in self._ordered)):
            active = {}
            for f, value in zip(self._ordered, values, strict=True):
                if all(parent in active and active[parent] in vs for parent, vs in f.conditions):
                    active[f.name] = value
            configuration = frozenset(active.items())
            if not any(c <= configuration for c in self.forbidden):
                configurations.add(configuration)
        return configurations

    def complete(
        self,
        obligations,
        configurations=None,
        *,
        preference=None,
        backend="python",
        solver="gecode",
    ):
        """Choose a deterministic complete extension for each obligation.

        Inactive factors remain absent. Callers may supply already validated,
        scoped configurations and a preference key (for example fault count).
        Without configurations, enumerate this model using the selected backend.
        Unsupported obligations raise rather than silently changing their values.
        """
        configurations = (
            self.configurations(backend=backend, solver=solver)
            if configurations is None
            else configurations
        )
        ordered = sorted(
            configurations,
            key=lambda c: (
                preference(c) if preference is not None else 0,
                repr(sorted(c)),
            ),
        )
        result = set()
        for obligation in obligations:
            obligation = frozenset(obligation)
            for name, value in obligation:
                if name not in self._by_name or not any(
                    type(value) is type(v) and value == v for v in self._by_name[name].values
                ):
                    raise ValueError(f"unknown factor/value: {(name, value)!r}")
            witness = next((c for c in ordered if obligation <= c), None)
            if witness is None:
                raise ValueError(f"no feasible completion for {dict(sorted(obligation))}")
            result.add(witness)
        return result

    def nwise(
        self,
        selected: Iterable[str],
        strength: int,
        *,
        backend="python",
        solver="gecode",
        complete=False,
    ) -> set[Obligation]:
        """Cover n active selected factors, or all if fewer exist in a branch.

        Prerequisites do not count toward strength. Branches with no active
        selected factors produce no obligation. Unrelated completion values are
        existential witnesses and never appear in the result unless ``complete``
        requests a full configuration for each projected obligation.
        """
        configurations = self.configurations(backend=backend, solver=solver)
        obligations = self.project(selected, strength, configurations)
        return self.complete(obligations, configurations) if complete else obligations

    def _closure(self, names):
        included = set(names)
        pending = list(included)
        while pending:
            for parent, _ in self._by_name[pending.pop()].conditions:
                if parent not in included:
                    included.add(parent)
                    pending.append(parent)
        return included

    def has_completion(self, fixed, *, inactive=(), required=(), predicate=None):
        """Check one partial assignment without enumerating complete configurations.

        Only its factors, required predicate inputs, forbidden combinations,
        and their activation prerequisites can affect the answer. Unrelated
        factors always have an extension because their domains are nonempty.
        """
        inactive = frozenset(inactive)
        names = set(fixed) | inactive | set(required)
        names.update(name for combination in self.forbidden for name, _ in combination)
        if names - self._by_name.keys():
            raise ValueError("unknown completion factor")
        if inactive & fixed.keys() or any(
            value not in self._by_name[name].values for name, value in fixed.items()
        ):
            return False
        relevant = self._closure(names)
        ordered = [f for f in self._ordered if f.name in relevant]
        active = {}

        def visit(index):
            if index == len(ordered):
                return not any(c <= active.items() for c in self.forbidden) and (
                    predicate is None or predicate(dict(active))
                )
            f = ordered[index]
            enabled = all(parent in active and active[parent] in vs for parent, vs in f.conditions)
            if not enabled:
                return f.name not in fixed and visit(index + 1)
            if f.name in inactive:
                return False
            for value in (fixed[f.name],) if f.name in fixed else f.values:
                active[f.name] = value
                if not any(c <= active.items() for c in self.forbidden) and visit(index + 1):
                    return True
            active.pop(f.name, None)
            return False

        return visit(0)

    def project(self, selected, strength, configurations):
        """Project already validated configurations, adding activation prerequisites."""
        names = self._selection(selected)
        if type(strength) is not int or not 1 <= strength <= len(names):
            raise ValueError(f"strength must be in 1..{len(names)}")
        obligations = set()
        for configuration in configurations:
            values = dict(configuration)
            active = [n for n in names if n in values]
            if not active:
                continue
            for subset in combinations(active, min(strength, len(active))):
                included = self._closure(subset)
                obligations.add(frozenset((n, values[n]) for n in included))
        return obligations

    def exhaustive(
        self, selected: Iterable[str], *, backend="python", solver="gecode", complete=False
    ) -> set[Obligation]:
        """Enumerate every feasible branch over the selected factors."""
        names = self._selection(selected)
        return self.nwise(names, len(names), backend=backend, solver=solver, complete=complete)

    def to_minizinc(self) -> str:
        """Export a standalone, reviewable model; enumerate with --all-solutions.

        Zero encodes inactivity, positive integers index each declared domain.
        The model describes complete configurations, before n-wise projection.
        """
        indices = {f.name: i for i, f in enumerate(self.factors)}

        def literal(name, value):
            code = self._by_name[name].values.index(value) + 1
            return f"v_{indices[name]} = {code}"

        lines = ["% Generated conditional-factor model. 0 = inactive."]
        for i, f in enumerate(self.factors):
            label = json.dumps({"factor": f.name, "values": dict(enumerate(f.values, 1))})
            lines.extend([f"% {label}", f"var 0..{len(f.values)}: v_{i};"])
        for i, f in enumerate(self.factors):
            condition = (
                " /\\ ".join(
                    "(" + (" \\/ ".join(f"({literal(n, v)})" for v in vs) or "false") + ")"
                    for n, vs in f.conditions
                )
                or "true"
            )
            lines.append(f"constraint (v_{i} != 0) <-> ({condition});")
        for conflict in self.forbidden:
            condition = (
                " /\\ ".join(f"({literal(n, v)})" for n, v in sorted(conflict, key=repr)) or "true"
            )
            lines.append(f"constraint not ({condition});")
        lines.append("solve satisfy;")
        return "\n".join(lines) + "\n"
