"""Finite MiniZinc feasibility and coverage-plan compilation.

Feasibility is solved over the shared conditional-factor encoding. Coverage is
a second MiniZinc model over those finite rows: set comprehensions implement
projection, union, and compatible products with existential completion. Only
the resulting obligation is a decision variable, avoiding duplicate solutions
for its unrelated completions. Large encodings use the shared Python projection
evaluator over the solved rows when Gecode cannot represent their mixed-radix obligation IDs. This remains
an enumerative reference backend.
"""

import json
import subprocess
import tempfile
from itertools import combinations
from math import prod
from pathlib import Path
from types import SimpleNamespace

from tests.generators.compliance_runners.tools.coverage_model import Expr, expression

from .coverage_dsl import Cmp


def _walk(node):
    yield node
    for arg in node.args:
        if isinstance(arg, Expr):
            yield from _walk(arg)


def _and(parts):
    return "(" + " /\\ ".join(parts) + ")" if parts else "true"


def _or(parts):
    return "(" + " \\/ ".join(parts) + ")" if parts else "false"


def _plan_key(plan):
    if plan.kind == "nwise":
        return plan.kind, tuple(f.name for f in plan.parts), plan.strength
    if plan.kind == "fix":
        return plan.kind, plan.parts
    return plan.kind, tuple(_plan_key(part) for part in plan.parts)


def _solve(source, solver):
    import minizinc  # noqa: PLC0415 - optional backend
    from minizinc.error import ConfigurationError, parse_error  # noqa: PLC0415
    from minizinc.json import decode_json_stream  # noqa: PLC0415

    driver = minizinc.default_driver
    if driver is None:
        raise ConfigurationError("No compatible MiniZinc driver provided")
    configuration = minizinc.Solver.lookup(solver, driver=driver)
    if "-a" not in configuration.stdFlags:
        raise NotImplementedError("Solver does not support the -a flag")
    # Our generated satisfaction models have known integer output fields. Read
    # those directly instead of launching Instance's separate interface-analysis
    # process before every solve. Keep discovery/configuration and diagnostics
    # with the MiniZinc library, and require an exhaustive terminal status.
    solutions, status = [], None
    with (
        tempfile.TemporaryDirectory(prefix="target-minizinc-") as directory,
        tempfile.TemporaryFile() as errors,
        configuration.configuration() as solver_configuration,
    ):
        model = Path(directory) / "model.mzn"
        model.write_text(source)
        command = [
            str(driver.executable),
            "--solver",
            solver_configuration,
            "--json-stream",
            "--output-mode",
            "json",
            "--all-solutions",
            str(model),
        ]
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors) as process:
            try:
                # Stream stdout; buffering all JSON would duplicate large row
                # enumerations in memory. A file for stderr avoids pipe stalls.
                for line in process.stdout:
                    for message in decode_json_stream(line):
                        if message["type"] == "solution":
                            solutions.append(SimpleNamespace(**message["output"]["json"]))
                        elif message["type"] == "status":
                            status = message["status"]
                process.wait()
                if process.returncode:
                    errors.seek(0)
                    raise parse_error(errors.read())
            except BaseException:
                # Let MiniZinc terminate its solver children before resorting
                # to a forced kill if the driver does not respond.
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise
    if status == "UNSATISFIABLE":
        return []
    if status != "ALL_SOLUTIONS":
        raise RuntimeError(f"incomplete MiniZinc enumeration: {status}")
    return solutions


class Backend:
    def __init__(self, target):
        self.target = target
        self.definition = target.definition
        self.model = self.definition.model(target.bound_constants)
        self.python_projection = prod(len(f.values) + 1 for f in self.model.factors) - 1 > 2**31 - 1
        self.indices = {f.name: i for i, f in enumerate(self.model.factors)}
        self.strings = {}
        self._configurations = {}
        self._obligations = {}
        self._callback_rows = None
        self.constant_callback = (
            self.definition.constant_feasibility(target.bound_constants)
            if self.definition.constant_feasibility is not None
            else None
        )

    def literal(self, value):
        if type(value) is bool:
            return str(value).lower()
        if type(value) is str:
            if value not in self.strings:
                self.strings[value] = len(self.strings) + 1
            return str(self.strings[value])
        if type(value) is int:
            # Gecode's integer range is smaller than some bound spec constants.
            # Constant-only expressions are folded before reaching this point.
            if not -(2**31 - 1) <= value <= 2**31 - 1:
                raise ValueError("MiniZinc expression exceeds the supported integer range")
            return str(value)
        raise TypeError(f"unsupported MiniZinc literal: {value!r}")

    def expr(self, node):
        """Return (known, value), preserving abstract three-valued semantics."""
        if not any(n.op in ("factor", "coverage", "present", "attribute") for n in _walk(node)):
            return "true", self.literal(node.evaluate({}, self.target.bound_constants))
        if node.op in ("factor", "coverage", "present"):
            f = node.args[0]
            i = self.indices[f.name]
            known = f"(v_{i} != 0)"
            if node.op == "present":
                return "true", known
            values = self.model.factors[i].values
            if node.op == "factor" and f.kind == "comparison":
                abstraction = Cmp(f.name, op=f.op, granularity=f.granularity)
                values = tuple(abstraction.holds(v) for v in values)
            # Index zero gets a harmless default; 'known' controls its meaning.
            default = False if type(values[0]) is bool else 0
            encoded = ", ".join(self.literal(v) for v in (default, *values))
            return known, f"array1d(0..{len(values)}, [{encoded}])[v_{i}]"
        if node.op == "attribute":
            raise ValueError("raw attributes cannot be translated to abstract feasibility")
        operands = [self.expr(arg) for arg in node.args]
        if node.op == "derived":
            return operands[0]
        known = _and([k for k, _ in operands])
        values = [v for _, v in operands]
        if node.op == "~":
            return known, f"(not ({values[0]}))"
        if node.op in ("&", "|"):
            decisive = [_and([k, v if node.op == "|" else f"not ({v})"]) for k, v in operands]
            known = _or([known, *decisive])
            value = _or(decisive) if node.op == "|" else f"not {_or(decisive)}"
            return known, value
        if node.op == "choose":
            condition, yes, no = operands
            return (
                _and([condition[0], f"(if {condition[1]} then {yes[0]} else {no[0]} endif)"]),
                f"(if {condition[1]} then {yes[1]} else {no[1]} endif)",
            )
        if node.op == "max":
            return known, f"max({values[0]}, {values[1]})"
        if node.op == "%":
            # MiniZinc mod truncates toward zero; Python's remainder follows
            # the divisor's sign. Unknown divisors need a harmless substitute.
            divisor = f"(if {known} then {values[1]} else 1 endif)"
            return known, f"((({values[0]} mod {divisor}) + {divisor}) mod {divisor})"
        op = {"==": "=", "!=": "!="}.get(node.op, node.op)
        return known, f"({values[0]} {op} {values[1]})"

    def assertion_terms(self, assertions):
        failed, unknown = [], []
        for f in assertions.declarations:
            active_known, active = self.expr(f.when)
            value_known, value = self.expr(expression(f))
            failed.append(_and([active_known, active, value_known, f"not ({value})"]))
            unknown.append(_or([f"not ({active_known})", _and([active, f"not ({value_known})"])]))
        count = "(" + " + ".join(f"bool2int({f})" for f in failed) + ")"
        return count, _or(unknown)

    def configuration_source(self, *, filtered=True, scopes=(), callbacks=True):
        lines = self.model.to_minizinc().splitlines()[:-1]
        if filtered:
            for rule in self.definition.constraints:
                known, value = self.expr(rule)
                lines.extend(f"% {line}" for line in rule.render().splitlines())
                lines.append(f"constraint not ({known}) \\/ ({value});")
            assertions = self.definition.assertions
            if assertions is not None and assertions.observed is not None:
                count, unknown = self.assertion_terms(assertions)
                known, observed = self.expr(expression(assertions.observed))
                agreement = (
                    f"(if {count} > 0 then not ({observed}) "
                    f"elseif {unknown} then true "
                    f"else {observed if assertions.complete else 'true'} endif)"
                )
                lines.extend(
                    [
                        "% Assertion/outcome consistency.",
                        f"constraint not ({known}) \\/ {agreement};",
                    ]
                )
            if callbacks and (
                self.definition._feasible_callback is not None or self.constant_callback is not None
            ):
                rows = self.callback_rows()
                lines.append(
                    "% Legacy Python witness callbacks: explicit finite compatibility table."
                )
                if not rows:
                    lines.append("constraint false;")
                else:
                    variables = ", ".join(f"v_{i}" for i in range(len(self.model.factors)))
                    values = ", ".join(str(v) for row in rows for v in row)
                    lines.extend(
                        [
                            'include "table.mzn";',
                            (
                                f"constraint table([{variables}], array2d(1..{len(rows)}, "
                                f"1..{len(self.model.factors)}, [{values}]));"
                            ),
                        ]
                    )
        for assertions, minimum, maximum in scopes:
            count, unknown = self.assertion_terms(assertions)
            lines.extend(["% Formula fault scope.", f"constraint {count} >= {minimum};"])
            if maximum is not None:
                lines.append(f"constraint not ({unknown}) /\\ {count} <= {maximum};")
        lines.append("solve satisfy;")
        return "\n".join(lines) + "\n"

    def decode(self, solution):
        return frozenset(
            (f.name, f.values[code - 1])
            for i, f in enumerate(self.model.factors)
            if (code := getattr(solution, f"v_{i}")) != 0
        )

    def encode_row(self, configuration):
        values = dict(configuration)
        return tuple(
            f.values.index(values[f.name]) + 1 if f.name in values else 0
            for f in self.model.factors
        )

    def callback_rows(self):
        if self._callback_rows is None:
            source = self.configuration_source(filtered=True, callbacks=False)
            configurations = [self.decode(s) for s in _solve(source, self.target.solver)]
            callbacks = [
                c
                for c in (self.definition._feasible_callback, self.constant_callback)
                if c is not None
            ]
            self._callback_rows = sorted(
                self.encode_row(c) for c in configurations if all(fn(dict(c)) for fn in callbacks)
            )
        return self._callback_rows

    def configurations(self, *, filtered=True, scopes=()):
        key = filtered, scopes
        if key not in self._configurations:
            self._configurations[key] = {
                self.decode(s)
                for s in _solve(
                    self.configuration_source(filtered=filtered, scopes=scopes), self.target.solver
                )
            }
        return self._configurations[key]

    def obligations(self, plan, configurations):
        key = _plan_key(plan), frozenset(configurations)
        if key not in self._obligations:
            if self.python_projection:
                from .declarations import BoundFormula  # noqa: PLC0415 - avoid import cycle

                self._obligations[key] = BoundFormula(self.target, plan)._run(plan, configurations)
                return self._obligations[key]
            compiler = Projection(self.model, configurations)
            self._obligations[key] = {
                compiler.decode(s.obligation)
                for s in _solve(compiler.source(plan), self.target.solver)
            }
        return self._obligations[key]


class Projection:
    """Compile a coverage-plan tree into MiniZinc finite-set operations."""

    def __init__(self, model, configurations):
        self.model = model
        self.indices = {f.name: i for i, f in enumerate(model.factors)}
        self.radices = [len(f.values) + 1 for f in model.factors]
        self.multipliers = [prod(self.radices[:i]) for i in range(len(self.radices))]
        if prod(self.radices) - 1 > 2**31 - 1:
            raise ValueError("MiniZinc projection encoding exceeds the supported integer range")
        self.rows = sorted(
            tuple(
                f.values.index(values[f.name]) + 1 if f.name in values else 0 for f in model.factors
            )
            for c in configurations
            for values in [dict(c)]
        )
        values = ", ".join(str(v) for row in self.rows for v in row)
        self.lines = [
            "% Generated coverage formula over solved finite configurations.",
            (
                f"array[0..{len(model.factors) - 1}] of int: weights = "
                f"array1d(0..{len(model.factors) - 1}, [{', '.join(str(v) for v in self.multipliers)}]);"
            ),
            (
                f"array[1..{len(self.rows)}, 0..{len(model.factors) - 1}] of int: cfg = "
                f"array2d(1..{len(self.rows)}, 0..{len(model.factors) - 1}, [{values}]);"
            ),
        ]
        self.lines.extend(
            "% "
            + json.dumps({"column": i, "factor": f.name, "values": dict(enumerate(f.values, 1))})
            for i, f in enumerate(model.factors)
        )
        self.counter = 0
        self._plans = {}

    def digit(self, value, i):
        return f"(({value} div {self.multipliers[i]}) mod {self.radices[i]})"

    def closure(self, names):
        included = set(names)
        pending = list(names)
        while pending:
            for parent, _ in self.model._by_name[pending.pop()].conditions:
                if parent not in included:
                    included.add(parent)
                    pending.append(parent)
        return sorted(self.indices[n] for n in included)

    def projected_row(self, included):
        return "(" + " + ".join(f"cfg[r,{i}] * {self.multipliers[i]}" for i in included) + ")"

    def emit(self, expr):
        name = f"plan_{self.counter}"
        self.counter += 1
        self.lines.append(f"set of int: {name} = {expr};")
        return name

    def compile(self, plan):
        key = _plan_key(plan)
        if key not in self._plans:
            self._plans[key] = self._compile(plan)
        return self._plans[key]

    def _compile(self, plan):
        self.lines.append(f"% Coverage node: {plan.kind}")
        if plan.kind == "nwise":
            names = [f.name for f in plan.parts]
            seeds, closures = [], []
            for size in range(1, plan.strength + 1):
                for selected in combinations(names, size):
                    seeds.append("{" + ",".join(str(self.indices[n]) for n in selected) + "}")
                    closures.append("{" + ",".join(str(i) for i in self.closure(selected)) + "}")
            prefix = f"selection_{self.counter}"
            selected_indices = "{" + ",".join(str(self.indices[n]) for n in names) + "}"
            self.lines.extend(
                [
                    f"array[1..{len(seeds)}] of set of int: {prefix}_seeds = [{', '.join(seeds)}];",
                    f"array[1..{len(seeds)}] of set of int: {prefix}_closure = [{', '.join(closures)}];",
                    (
                        f"array[1..{plan.strength}] of set of int: {prefix}_sizes = "
                        f"[{{s | s in 1..{len(seeds)} where card({prefix}_seeds[s]) = k}} "
                        f"| k in 1..{plan.strength}];"
                    ),
                    (
                        f"array[1..{len(self.rows)}] of set of int: {prefix}_active = "
                        f"[{{i | i in {selected_indices} where cfg[r,i] != 0}} "
                        f"| r in 1..{len(self.rows)}];"
                    ),
                ]
            )
            return self.emit(
                "{sum(i in " + prefix + "_closure[s])(cfg[r,i] * weights[i]) "
                f"| r in 1..{len(self.rows)} where card({prefix}_active[r]) > 0, "
                f"s in {prefix}_sizes[min({plan.strength}, card({prefix}_active[r]))] "
                f"where {prefix}_seeds[s] subset {prefix}_active[r]" + "}"
            )
        if plan.kind == "fix":
            if not plan.parts:
                return self.emit("{0}" if self.rows else "{}")
            conditions = []
            names = []
            for name, value in plan.parts:
                f = self.model._by_name[name]
                if value not in f.values:
                    raise ValueError(f"invalid fixed value: {name}={value!r}")
                names.append(name)
                conditions.append(f"cfg[r,{self.indices[name]}] = {f.values.index(value) + 1}")
            return self.emit(
                "{"
                + self.projected_row(self.closure(names))
                + f" | r in 1..{len(self.rows)} where {_and(conditions)}"
                + "}"
            )
        if plan.kind == "union":
            return self.emit(" union ".join(self.compile(p) for p in plan.parts) or "{}")
        if plan.kind != "product":
            raise ValueError(f"unsupported unscoped coverage formula: {plan.kind}")
        result = self.emit("{0}")
        for part in plan.parts:
            other = self.compile(part)
            digits = [(self.digit("a", i), self.digit("b", i)) for i in range(len(self.radices))]
            compatible = _and([f"({a} = 0 \\/ {b} = 0 \\/ {a} = {b})" for a, b in digits])
            merged = " + ".join(
                f"max({a}, {b}) * {self.multipliers[i]}" for i, (a, b) in enumerate(digits)
            )
            result = self.emit(
                "{" + merged + f" | a in {result}, b in {other} where {compatible}" + "}"
            )
        return result

    def source(self, plan):
        result = self.compile(plan)

        def has_product(node):
            return node.kind == "product" or (
                node.kind == "union" and any(has_product(part) for part in node.parts)
            )

        # Every leaf is supported by construction. Only products can merge
        # independent witnesses into an unsupported combined obligation.
        if not has_product(plan):
            self.lines.extend([f"var {result}: obligation;", "solve satisfy;"])
            return "\n".join(self.lines) + "\n"
        shape = " + ".join(
            f"bool2int({self.digit('o', i)} != 0) * {2**i}" for i in range(len(self.radices))
        )
        projected = (
            f"sum(i in 0..{len(self.radices) - 1} where (s div pow(2,i)) mod 2 = 1)"
            "(cfg[r,i] * weights[i])"
        )
        self.lines.extend(
            [
                "% Index existential completions once per selected-factor shape.",
                f"set of int: shapes = {{{shape} | o in {result}}};",
                "array[1..card(shapes)] of int: shape_values = [s | s in shapes];",
                (
                    "array[1..card(shapes)] of set of int: completions = "
                    f"[{{{projected} | r in 1..{len(self.rows)}}} | s in shapes];"
                ),
                (
                    f"set of int: supported = {{o | o in {result} where "
                    f"exists(i in 1..card(shapes))(shape_values[i] = {shape} /\\ o in completions[i])}};"
                ),
                "var supported: obligation;",
                "solve satisfy;",
            ]
        )
        return "\n".join(self.lines) + "\n"

    def decode(self, value):
        return frozenset(
            (f.name, f.values[code - 1])
            for i, f in enumerate(self.model.factors)
            if (code := value // self.multipliers[i] % self.radices[i]) != 0
        )
