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
from tests.generators.compliance_runners.runner import state_transition as replay
from tests.generators.compliance_runners.runner.discovery import gather_tests
from tests.generators.compliance_runners.runner.io import read_yaml

from .backend_config import BACKENDS

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

    def domain(self) -> tuple:
        raise NotImplementedError

    def abstract(self, raw: Any) -> Any:
        raise NotImplementedError

    def value(self, obs: Observation) -> Any:
        raw = obs.get(self.name, NA)
        return NA if raw is NA else self.abstract(raw)

    def holds(self, value: Any) -> bool | None:
        """Truth of the underlying spec predicate for an abstract value, if any."""
        return None


@dataclass(frozen=True)
class Pred(Factor):
    values: tuple = (True, False)

    def domain(self) -> tuple:
        return self.values

    def abstract(self, raw: Any) -> Any:
        return bool(raw)

    def holds(self, value: Any) -> bool | None:
        return bool(value)


@dataclass(frozen=True)
class Cmp(Factor):
    """``lhs op rhs``, observed as the integer ``lhs - rhs``."""

    op: str = ""
    granularity: str = "predicate"
    bounds: tuple = (None, None)

    def __post_init__(self):
        if self.granularity not in GRANULARITIES:
            raise ValueError(f"unknown granularity {self.granularity!r}")

    def domain(self) -> tuple:
        lo, hi = self.bounds
        intervals = {
            "LT_FAR": (None, -2),
            "LT_1": (-1, -1),
            "EQ": (0, 0),
            "GT_1": (1, 1),
            "GT_FAR": (2, None),
            "LT": (None, -1),
            "GT": (1, None),
        }
        buckets = {
            "cmp3": ("LT", "EQ", "GT"),
            "cmp5": ("LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR"),
        }

        def intersects(value):
            a, b = intervals[value]
            return not (
                (hi is not None and a is not None and hi < a)
                or (lo is not None and b is not None and lo > b)
            )

        if self.granularity == "predicate":
            possible = {
                _OPS[self.op](_CMP_REPRESENTATIVE[v]) for v in buckets["cmp5"] if intersects(v)
            }
            return tuple(v for v in (True, False) if v in possible)
        return tuple(v for v in buckets[self.granularity] if intersects(v))

    def abstract(self, raw: Any) -> Any:
        delta = int(raw)
        g = self.granularity
        if g == "predicate":
            return _OPS[self.op](delta)
        if g == "cmp3":
            return "LT" if delta < 0 else "EQ" if delta == 0 else "GT"
        if delta < -1:
            return "LT_FAR"
        if delta > 1:
            return "GT_FAR"
        return {-1: "LT_1", 0: "EQ", 1: "GT_1"}[delta]

    def holds(self, value: Any) -> bool | None:
        if self.granularity == "predicate":
            return bool(value)
        return _OPS[self.op](_CMP_REPRESENTATIVE[value])

    def far(self, value: Any) -> bool | None:
        """Whether ``value`` denotes ``|lhs - rhs| > 1``; None if unknowable."""
        g = self.granularity
        if g == "predicate":
            return None
        if g == "cmp3":
            return None if value != "EQ" else False
        return value in ("LT_FAR", "GT_FAR")


@dataclass(frozen=True)
class Enum(Factor):
    values: tuple = ()

    def domain(self) -> tuple:
        return self.values

    def abstract(self, raw: Any) -> Any:
        if raw not in self.values:
            raise ValueError(f"{self.name}: {raw!r} not in {self.values}")
        return raw


Assignment = dict[str, Any]
Obligation = frozenset[tuple[str, Any]]
Feasible = Callable[[Assignment], bool]


def _merge(a: Obligation, b: Obligation) -> Obligation | None:
    da, db = dict(a), dict(b)
    for k, v in db.items():
        if k in da and da[k] != v:
            return None
    return frozenset({**da, **db}.items())


def rules(*fns: Feasible) -> Feasible:
    """Conjoin feasibility rules."""

    def feasible(assignment: Assignment) -> bool:
        return all(fn(assignment) for fn in fns)

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
    comparison_granularities: dict[str, str]
    total: int
    covered: int
    uncovered: list[dict] = field(default_factory=list)
    unexpected: list[dict] = field(default_factory=list)
    outcome_mismatches: list[dict] = field(default_factory=list)

    @property
    def percent(self) -> float | None:
        return round(100 * self.covered / self.total, 2) if self.total else None

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "comparison_granularities": self.comparison_granularities,
            "total": self.total,
            "covered": self.covered,
            "percent": self.percent,
            "uncovered": self.uncovered,
            "unexpected": self.unexpected,
            "outcome_mismatches": self.outcome_mismatches,
        }


def _sorted(obligations: Iterable[Obligation]) -> list[dict]:
    return [dict(sorted(o)) for o in sorted(obligations, key=lambda o: repr(sorted(o)))]


def score(
    target: Target,
    records: Sequence[dict[str, Any]],
    formula: Formula,
    profile: str = "",
) -> Report:
    if target._bound_spec is None:
        raise ValueError("bind the target with for_spec(spec) before scoring")
    wanted = formula.run()
    covered = formula.covered(records)
    unexpected = formula.covered(records, filtered=False) - wanted
    assertions = target.definition.assertions
    mismatches = [
        {
            "record": i,
            "observed_accepted": r[assertions.observed.name],
            "expected_accepted": assertions.evaluate(r, target.bound_constants).expected_accepted,
        }
        for i, r in enumerate(records)
        if assertions is not None and not assertions.agrees(r, target.bound_constants)
    ]
    return Report(
        profile=profile,
        comparison_granularities={
            f.name: f.granularity for f in target.factors if isinstance(f, Cmp)
        },
        total=len(wanted),
        covered=len(covered),
        uncovered=_sorted(wanted - covered),
        unexpected=_sorted(unexpected),
        outcome_mismatches=mismatches,
    )


# --- vector loading and CLI ---------------------------------------------------

TARGETS = {
    "withdrawal_processing": "tests.generators.compliance_runners.state_transition.withdrawal_processing.target",
    "bid_processing": "tests.generators.compliance_runners.state_transition.bid_processing.target",
    "consolidation_request": "tests.generators.compliance_runners.state_transition.consolidation_request.target",
    "withdrawal_request": "tests.generators.compliance_runners.state_transition.withdrawal_request.target",
    "parent_execution_payload": "tests.generators.compliance_runners.state_transition.parent_execution_payload.target",
    "builder_pending_withdrawal_processing": "tests.generators.compliance_runners.state_transition.builder_pending_withdrawal_processing.target",
    "attestation": "tests.generators.compliance_runners.state_transition.attestation.target",
    "pending_deposits": "tests.generators.compliance_runners.state_transition.pending_deposits.target",
    "builder_exit_request": "tests.generators.compliance_runners.state_transition.builder_exit_request.target",
    "process_operations_dispatch": "tests.generators.compliance_runners.state_transition.operations_dispatch.target",
    "builder_deposit_request": "tests.generators.compliance_runners.state_transition.builder_deposit_request.target",
    "builder_pending_payments": "tests.generators.compliance_runners.state_transition.builder_pending_payments.target",
    "attester_slashing": "tests.generators.compliance_runners.state_transition.attester_slashing.target",
    "bls_to_execution_change": "tests.generators.compliance_runners.state_transition.bls_to_execution_change.target",
    "payload_attestation": "tests.generators.compliance_runners.state_transition.payload_attestation.target",
    "proposer_slashing": "tests.generators.compliance_runners.state_transition.proposer_slashing.target",
    "block_header": "tests.generators.compliance_runners.state_transition.block_header.target",
    "voluntary_exit": "tests.generators.compliance_runners.state_transition.voluntary_exit.target",
    "process_operations": "tests.generators.compliance_runners.state_transition.operations.target",
    "eth1_data_reset": "tests.generators.compliance_runners.state_transition.eth1_data_reset.target",
    "effective_balance_updates": "tests.generators.compliance_runners.state_transition.effective_balance_updates.target",
    "justification_and_finalization": "tests.generators.compliance_runners.state_transition.justification_and_finalization.target",
    "registry_updates": "tests.generators.compliance_runners.state_transition.registry_updates.target",
    "rewards_and_penalties": "tests.generators.compliance_runners.state_transition.rewards_and_penalties.target",
    "proposer_lookahead": "tests.generators.compliance_runners.state_transition.proposer_lookahead.target",
    "deposit_request": "tests.generators.compliance_runners.state_transition.deposit_request.target",
    "slashings": "tests.generators.compliance_runners.state_transition.slashings.target",
    "sync_aggregate": "tests.generators.compliance_runners.state_transition.sync_aggregate.target",
    "historical_summaries_update": "tests.generators.compliance_runners.state_transition.historical_summaries_update.target",
    "inactivity_updates": "tests.generators.compliance_runners.state_transition.inactivity_updates.target",
    "inactivity_updates_loop": "tests.generators.compliance_runners.state_transition.inactivity_updates_loop.target",
    "participation_flag_updates": "tests.generators.compliance_runners.state_transition.participation_flag_updates.target",
    "randao_mixes_reset": "tests.generators.compliance_runners.state_transition.randao_mixes_reset.target",
    "slashings_reset": "tests.generators.compliance_runners.state_transition.slashings_reset.target",
    "sync_committee_updates": "tests.generators.compliance_runners.state_transition.sync_committee_updates.target",
    "pending_consolidations": "tests.generators.compliance_runners.state_transition.pending_consolidations.target",
    "ptc_window": "tests.generators.compliance_runners.state_transition.ptc_window.target",
    "process_slot": "tests.generators.compliance_runners.state_transition.slot_processing.target",
}

TARGET_HANDLERS = {
    "withdrawal_processing": "withdrawals",
    "bid_processing": "execution_payload_bid",
    "builder_pending_withdrawal_processing": "withdrawals",
    "process_operations": "blocks",
    "process_operations_dispatch": "blocks",
    "process_slot": "slots",
}


def load_observations(tests: list[Path], target: Target, preset: str) -> list[Observation]:
    spec = spec_targets[preset]["gloas"]
    handler = TARGET_HANDLERS.get(target.name, target.name)
    out = []
    for case in gather_tests(tests, kind="state_transition"):
        if case.handler != handler or case.preset != preset or case.fork != "gloas":
            continue
        if target.name in (
            "process_operations_dispatch",
            "builder_pending_withdrawal_processing",
            "withdrawal_processing",
        ):
            dimensions_path = Path(case.test_dir) / "dimensions.yaml"
            if dimensions_path.exists():
                dimensions = read_yaml(dimensions_path)
                if dimensions.get("test_provider") != target.name:
                    continue
        tc = replay.get_test_case(spec, Path(case.test_dir), case.handler)
        if target.name == "process_slot":
            operation = tc["slots"]
        elif target.name in ("process_operations", "process_operations_dispatch"):
            if not tc["blocks"]:
                raise ValueError(f"sanity/blocks vector has no blocks: {case.test_dir}")
            operation = (
                tc["blocks"][0].message.body
                if target.name == "process_operations"
                else tc["blocks"][0]
            )
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
    for item in report.outcome_mismatches:
        lines.append(f"      OUTCOME MISMATCH {item}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score vectors with a target's coverage profiles")
    parser.add_argument("--tests", type=Path, nargs="+", required=True)
    parser.add_argument("--target", choices=sorted(TARGETS), default="voluntary_exit")
    parser.add_argument("--preset", choices=("minimal", "mainnet"), default="minimal")
    parser.add_argument("--backend", choices=BACKENDS, help="default: target's declared backend")
    parser.add_argument("--solver", help="MiniZinc solver (default: target's declared solver)")
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
    target = target.for_spec(
        spec_targets[args.preset]["gloas"], backend=args.backend, solver=args.solver
    )
    if args.describe:
        print(describe(target))
    observations = load_observations(args.tests, target, args.preset)
    profiles = args.profile or list(target.profiles)
    unknown = set(profiles) - target.profiles.keys()
    if unknown:
        raise SystemExit(f"unknown profile(s) {sorted(unknown)}; have {sorted(target.profiles)}")

    result: dict[str, Any] = {
        "target": target.name,
        "preset": args.preset,
        "vectors": len(observations),
        "aspects": {a.name: [f.name for f in a.factors] for a in target.aspects},
        "comparison_granularities": {
            f.name: f.granularity for f in target.factors if isinstance(f, Cmp)
        },
    }
    print(f"{target.name}/{args.preset}: {len(observations)} vectors")
    records = [target.record(o) for o in observations]
    if args.records:
        for obs, rec in zip(observations, records, strict=True):
            print(f"  {Path(obs['_case']).name}: {rec}")
            if (result_summary := target.assertion_result(rec)) is not None:
                print(
                    f"    expected_accepted={result_summary.expected_accepted}; "
                    f"fault_count={result_summary.fault_count}; "
                    f"failed={result_summary.failed}; unknown={result_summary.unknown}"
                )
    reports = [score(target, records, target.profiles[p], profile=p) for p in profiles]
    result["profiles"] = [r.as_dict() for r in reports]
    for report in reports:
        print(_format(report, args.max_uncovered))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return result


if __name__ == "__main__":
    main()
