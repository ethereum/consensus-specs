"""Collect slices and calculate group coverage for generated compliance vectors."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import coverage
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.catalog import HANDLERS
from tests.generators.compliance_runners.state_transition.runner import test_run

from . import collect_slice

if TYPE_CHECKING:
    from types import ModuleType


PROCESSORS = {
    "attestation": "process_attestation",
    "attester_slashing": "process_attester_slashing",
    "bls_to_execution_change": "process_bls_to_execution_change",
    "builder_deposit_request": "process_builder_deposit_request",
    "builder_exit_request": "process_builder_exit_request",
    "consolidation_request": "process_consolidation_request",
    "deposit_request": "process_deposit_request",
    "execution_payload_bid": "process_execution_payload_bid",
    "parent_execution_payload": "process_parent_execution_payload",
    "payload_attestation": "process_payload_attestation",
    "proposer_slashing": "process_proposer_slashing",
    "sync_aggregate": "process_sync_aggregate",
    "voluntary_exit": "process_voluntary_exit",
    "withdrawal_request": "process_withdrawal_request",
    "withdrawals": "process_withdrawals",
    "builder_pending_payments": "process_builder_pending_payments",
    "effective_balance_updates": "process_effective_balance_updates",
    "pending_consolidations": "process_pending_consolidations",
    "pending_deposits": "process_pending_deposits",
    "ptc_window": "process_ptc_window",
    "slashings": "process_slashings",
}

PACKAGE_DIR = Path(__file__).resolve().parent
YAML_READER = YAML(typ="safe")


def load_yaml(path: Path):
    with path.open() as stream:
        return YAML_READER.load(stream)


def resolve_group(name: str, definitions: dict) -> list[str]:
    if name in PROCESSORS:
        return [name]
    if name not in definitions:
        raise ValueError(f"unknown group {name!r}")
    resolved: list[str] = []
    for child in definitions[name].get("includes", []):
        resolved.extend(resolve_group(child, definitions))
    resolved.extend(definitions[name].get("handlers", []))
    unknown = set(resolved) - PROCESSORS.keys()
    if unknown:
        raise ValueError(f"group {name!r} names unknown handler(s): {sorted(unknown)}")
    return list(dict.fromkeys(resolved))


def slice_path(work_dir: Path, preset: str, group: str) -> Path:
    return (work_dir / "slices" / preset / group / "code_to_test.py").resolve()


def load_slice(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load slice {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def collect(args: argparse.Namespace) -> None:
    exclusions = load_yaml(PACKAGE_DIR / "exclusions.yaml")["functions"]
    definitions = load_yaml(PACKAGE_DIR / "groups.yaml")
    module = collect_slice.load_module("gloas", args.preset)
    for group in args.group or list(HANDLERS):
        handlers = resolve_group(group, definitions)
        output = slice_path(args.work_dir, args.preset, group)
        output.parent.mkdir(parents=True, exist_ok=True)
        roots = [PROCESSORS[handler] for handler in handlers]
        expanded, imports, typing_imports, uses_config, reachable_from = collect_slice.collect(
            module, roots, set(exclusions)
        )
        output.write_text(
            collect_slice.emit(
                module,
                roots,
                set(exclusions),
                expanded,
                imports,
                typing_imports,
                uses_config,
                reachable_from,
                group,
            )
        )
        if collect_slice.check(output, module):
            raise RuntimeError(f"generated slice does not match installed PySpec: {output}")


def run_case(case: test_run.StateTransitionTestInfo, processor) -> None:
    spec = spec_targets[case.preset][case.fork]
    test_case = test_run.get_test_case(spec, Path(case.test_dir), case.handler)
    old_bls_active = bls.bls_active
    bls.bls_active = bool(test_case["meta"].get("bls_setting", 0))
    try:
        extra_args = ()
        if case.handler == "attestation" and is_post_gloas(spec):
            extra_args = (spec.Slot(test_case["meta"]["parent_slot"]),)
        test_run.run_processing_case(
            processor,
            test_case["pre"],
            test_case["operation"],
            test_case["post"],
            extra_args,
        )
    finally:
        bls.bls_active = old_bls_active


def cases_for(tests: list[Path], handler: str, preset: str):
    cases = [
        case
        for case in test_run.gather_tests(tests)
        if case.handler == handler and case.preset == preset and case.fork == "gloas"
    ]
    if not cases:
        raise ValueError(f"no {preset}/gloas vectors for {handler}")
    return cases


def annotate_slice(cov: coverage.Coverage, path: Path) -> Path:
    """Use Coverage.py's native ``annotate`` report for a collected slice."""
    output_dir = path.parent / "coverage"
    output_dir.mkdir(exist_ok=True)
    cov.annotate([str(path)], directory=str(output_dir))
    annotated = [item for item in output_dir.iterdir() if item.name.endswith(",cover")]
    if len(annotated) != 1:
        raise RuntimeError(f"expected one Coverage.py annotation for {path}, got {annotated}")
    return annotated[0]


def percent(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def coverage_metric(cov: coverage.Coverage, path: Path) -> dict:
    """Return Coverage.py's own statement and branch totals for ``path``."""
    numbers = cov._analyze(str(path)).numbers
    statement_covered, statement_total = numbers.ratio_statements
    branch_covered, branch_total = numbers.ratio_branches
    return {
        "statements": {
            "total": statement_total,
            "covered": statement_covered,
            "percent": percent(statement_covered, statement_total),
        },
        "branches": {
            "total": branch_total,
            "covered": branch_covered,
            "percent": percent(branch_covered, branch_total),
        },
    }


def evaluate_group(args: argparse.Namespace, group: str, definitions: dict) -> dict:
    handlers = resolve_group(group, definitions)
    path = slice_path(args.work_dir, args.preset, group)
    if not path.is_file():
        raise ValueError(f"missing {path}; run collect --group {group} first")
    vector_counts = {}
    cov = coverage.Coverage(branch=True, data_file=None, include=[str(path)])
    cov.start()
    try:
        module = load_slice(path, f"evaluation_{group}")
        for handler in handlers:
            cases = cases_for(args.tests, handler, args.preset)
            vector_counts[handler] = len(cases)
            processor = getattr(module, PROCESSORS[handler])
            for case in cases:
                run_case(case, processor)
    finally:
        cov.stop()
    return {
        "group": group,
        "handlers": handlers,
        "vectors": vector_counts,
        "annotated_slice": str(annotate_slice(cov, path)),
        "coverage": coverage_metric(cov, path),
    }


def evaluate(args: argparse.Namespace) -> None:
    definitions = load_yaml(PACKAGE_DIR / "groups.yaml")
    groups = args.group or ["all"]
    result_dir = args.work_dir / "results" / args.preset
    result_dir.mkdir(parents=True, exist_ok=True)
    for group in groups:
        result = evaluate_group(args, group, definitions)
        (result_dir / f"{group}.json").write_text(json.dumps(result, indent=2) + "\n")
        covered = result["coverage"]
        print(
            f"{group}: {sum(result['vectors'].values())} vectors, "
            f"{covered['statements']['percent']}% statements, {covered['branches']['percent']}% branches"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect_parser = commands.add_parser("collect")
    collect_parser.add_argument("--work-dir", type=Path, required=True)
    collect_parser.add_argument("--preset", choices=("minimal", "mainnet"), default="minimal")
    collect_parser.add_argument("--group", action="append", help="group or individual handler")
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--tests", type=Path, nargs="+", required=True)
    evaluate_parser.add_argument("--work-dir", type=Path, required=True)
    evaluate_parser.add_argument("--preset", choices=("minimal", "mainnet"), default="minimal")
    evaluate_parser.add_argument("--group", action="append")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "collect":
        collect(args)
    else:
        evaluate(args)


if __name__ == "__main__":
    main()
