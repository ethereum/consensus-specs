"""Coverage observation abstractions, scoring, vector loading, and CLI.

Author specifications with ``declarations.py``; expression trees and conditional
factor enumeration live in the shared state-transition tools.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .declarations import BoundFormula as Formula, DeclarationTarget as Target

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

    def _g(self, granularity: str) -> str:
        g = granularity
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


Assignment = dict[str, Any]
Obligation = frozenset[tuple[str, Any]]
Feasible = Callable[[Assignment, str], bool]


def _merge(a: Obligation, b: Obligation) -> Obligation | None:
    da, db = dict(a), dict(b)
    for k, v in db.items():
        if k in da and da[k] != v:
            return None
    return frozenset({**da, **db}.items())


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
    if target._bound_spec is None:
        raise ValueError("bind the target with for_spec(spec) before scoring")
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
    "effective_balance_updates": "tests.generators.compliance_runners.state_transition.effective_balance_updates.target",
    "justification_and_finalization": "tests.generators.compliance_runners.state_transition.justification_and_finalization.target",
    "registry_updates": "tests.generators.compliance_runners.state_transition.registry_updates.target",
    "rewards_and_penalties": "tests.generators.compliance_runners.state_transition.rewards_and_penalties.target",
    "proposer_lookahead": "tests.generators.compliance_runners.state_transition.proposer_lookahead.target",
    "historical_summaries_update": "tests.generators.compliance_runners.state_transition.historical_summaries_update.target",
    "inactivity_updates": "tests.generators.compliance_runners.state_transition.inactivity_updates.target",
    "inactivity_updates_loop": "tests.generators.compliance_runners.state_transition.inactivity_updates_loop.target",
    "participation_flag_updates": "tests.generators.compliance_runners.state_transition.participation_flag_updates.target",
    "randao_mixes_reset": "tests.generators.compliance_runners.state_transition.randao_mixes_reset.target",
    "slashings_reset": "tests.generators.compliance_runners.state_transition.slashings_reset.target",
    "sync_committee_updates": "tests.generators.compliance_runners.state_transition.sync_committee_updates.target",
    "process_slot": "tests.generators.compliance_runners.state_transition.slot_processing.target",
}

TARGET_HANDLERS = {
    "process_operations": "blocks",
    "process_slot": "slots",
}


def load_observations(tests: list[Path], target: Target, preset: str) -> list[Observation]:
    spec = spec_targets[preset]["gloas"]
    handler = TARGET_HANDLERS.get(target.name, target.name)
    out = []
    for case in test_run.gather_tests(tests):
        if case.handler != handler or case.preset != preset or case.fork != "gloas":
            continue
        tc = test_run.get_test_case(spec, Path(case.test_dir), case.handler)
        if target.name == "process_slot":
            operation = tc["slots"]
        elif target.name == "process_operations":
            if not tc["blocks"]:
                raise ValueError(f"sanity/blocks vector has no blocks: {case.test_dir}")
            operation = tc["blocks"][0].message.body
        else:
            operation = tc["operation"]
        obs = target.observation(Context(spec, tc["pre"], operation, tc["post"], tc["meta"]))
        obs["_case"] = str(case.test_dir)
        out.append(obs)
    if not out:
        raise ValueError(f"no {preset}/gloas vectors for {target.name} under {tests}")
    return out


def describe(target: Target) -> str:
    return target.review()


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
    parser.add_argument(
        "--describe",
        action="store_true",
        help="print the bound coverage specification and obligations",
    )
    parser.add_argument("--records", action="store_true", help="dump abstracted records")
    parser.add_argument("--json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    target: Target = import_module(TARGETS[args.target]).TARGET
    target = target.for_spec(spec_targets[args.preset]["gloas"])
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
