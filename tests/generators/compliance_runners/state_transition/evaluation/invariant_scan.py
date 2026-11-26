"""Check state invariants and handler entry conditions in generated Gloas pre-states."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from itertools import pairwise
from pathlib import Path

from tests.generators.compliance_runners.runner.io import read_yaml
from tests.generators.compliance_runners.runner.state_transition import decode_file, load_spec
from tests.generators.compliance_runners.state_transition.catalog import PROVIDERS
from tests.generators.compliance_runners.state_transition.materializer import SUITE_NAME


def entry_condition_violations(spec, state, runner):
    """Check the point at which the runner enters the state transition."""
    if runner == "epoch_processing":
        if state.slot % spec.SLOTS_PER_EPOCH != spec.SLOTS_PER_EPOCH - 1:
            yield "epoch_handler_off_boundary"
        # process_slots calls process_slot before entering process_epoch.
        index = state.slot % spec.SLOTS_PER_HISTORICAL_ROOT
        block_root = state.block_roots[index]
        if state.state_roots[index] == spec.Root() or block_root == spec.Root():
            yield "epoch_slot_roots_missing"
        if block_root != spec.Root() and block_root != spec.hash_tree_root(
            state.latest_block_header
        ):
            yield "epoch_block_root_mismatch"
    if runner == "sanity" and state.slot < spec.SLOTS_PER_HISTORICAL_ROOT:
        # process_slot has yet to write this index for the first time.
        if (
            state.state_roots[state.slot] != spec.Root()
            or state.block_roots[state.slot] != spec.Root()
        ):
            yield "first_lap_destination_populated"


def state_invariant_violations(spec, state):
    """Check properties of a Gloas BeaconState independently of the handler."""
    epoch = spec.get_current_epoch(state)
    validator_count = len(state.validators)
    increment = spec.EFFECTIVE_BALANCE_INCREMENT

    if state.finalized_checkpoint.epoch > epoch:
        yield "future_finalized_epoch"
    if state.finalized_checkpoint.epoch > state.current_justified_checkpoint.epoch:
        yield "finalized_ahead_of_justified"

    parallel_lists = (
        state.balances,
        state.inactivity_scores,
        state.previous_epoch_participation,
        state.current_epoch_participation,
    )
    if any(len(values) != validator_count for values in parallel_lists):
        yield "parallel_validator_list_lengths"
    if any(v.slashed and v.exit_epoch == spec.FAR_FUTURE_EPOCH for v in state.validators):
        yield "slashed_without_exit"
    if any(v.withdrawable_epoch < v.exit_epoch for v in state.validators):
        yield "withdrawable_before_exit"
    if any(v.activation_eligibility_epoch > v.activation_epoch for v in state.validators):
        yield "eligible_after_activation"
    if any(v.effective_balance % increment for v in state.validators):
        yield "fractional_effective_increment"
    if any(amount % increment for amount in state.slashings):
        yield "fractional_slashings_increment"

    if any(builder.deposit_epoch > epoch for builder in state.builders):
        yield "future_builder_deposit"
    payments = state.builder_pending_payments
    if any(p.weight and not p.withdrawal.amount for p in payments):
        yield "positive_weight_without_bid"
    if any(p.weight % increment for p in payments):
        yield "fractional_payment_weight"
    builder_count = len(state.builders)
    if any(
        p.withdrawal.amount and p.withdrawal.builder_index >= builder_count for p in payments
    ) or any(
        w.amount and w.builder_index >= builder_count for w in state.builder_pending_withdrawals
    ):
        yield "missing_payment_builder"

    if any(
        a.withdrawable_epoch > b.withdrawable_epoch
        for a, b in pairwise(state.pending_partial_withdrawals)
    ):
        yield "partial_queue_unordered"
    sources = [entry.source_index for entry in state.pending_consolidations]
    if len(set(sources)) != len(sources):
        yield "duplicate_consolidation_source"
    if any(
        i >= validator_count or state.validators[i].exit_epoch == spec.FAR_FUTURE_EPOCH
        for i in sources
    ):
        yield "queued_consolidation_without_exit"

    registered = {v.pubkey for v in state.validators}
    committees = (state.current_sync_committee, state.next_sync_committee)
    if any(pubkey not in registered for committee in committees for pubkey in committee.pubkeys):
        yield "unregistered_sync_pubkey"


@dataclass
class ProviderReport:
    scanned: int = 0
    failed: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    examples: dict[str, str] = field(default_factory=dict)


def scan(root: Path, *, provider=None, preset=None):
    reports = defaultdict(ProviderReport)
    errors = {}
    # Multiple providers may write to the same suite. Read it once and use
    # dimensions.yaml to identify which provider produced each case.
    suites = defaultdict(set)
    for entry in PROVIDERS:
        suites[entry.runner, entry.handler].add(entry.name)

    presets = (preset,) if preset else ("minimal", "mainnet")
    for preset_name in presets:
        for (runner, handler), names in suites.items():
            if provider and provider not in names:
                continue
            suite = root / preset_name / "gloas" / runner / handler / SUITE_NAME
            try:
                cases = sorted(path for path in suite.iterdir() if path.name.startswith("case_"))
            except FileNotFoundError:
                continue  # Generated roots can contain a subset of the suites.
            except OSError as exc:
                errors[str(suite.relative_to(root))] = f"{type(exc).__name__}: {exc}"
                continue
            for case in cases:
                relative = str(case.relative_to(root))
                try:
                    name = read_yaml(case / "dimensions.yaml")["test_provider"]
                    if name not in names:
                        raise ValueError(f"unexpected provider {name!r} for {handler}")
                    if provider and provider != name:
                        continue
                    spec = load_spec(preset_name, "gloas", case)
                    state = decode_file(spec, case, "pre", spec.BeaconState)
                except Exception as exc:
                    errors[relative] = f"{type(exc).__name__}: {exc}"
                    continue

                faults = [
                    *entry_condition_violations(spec, state, runner),
                    *state_invariant_violations(spec, state),
                ]
                report = reports[f"{preset_name}/{name}"]
                report.scanned += 1
                report.failed += bool(faults)
                for fault in faults:
                    report.counts[fault] = report.counts.get(fault, 0) + 1
                    report.examples.setdefault(fault, relative)
    return dict(reports), errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--test-dir",
        type=Path,
        required=True,
        help="generated vector root containing the preset directories",
    )
    parser.add_argument("--provider", choices=sorted(p.name for p in PROVIDERS))
    parser.add_argument("--preset", choices=("minimal", "mainnet"))
    parser.add_argument(
        "--json", type=Path, help="write counts, first example paths and input errors as JSON"
    )
    args = parser.parse_args(argv)

    reports, errors = scan(args.test_dir, provider=args.provider, preset=args.preset)
    for name, report in sorted(reports.items()):
        print(f"{name}: {report.failed}/{report.scanned} pre-states with violations")
        for fault, count in sorted(report.counts.items()):
            print(f"  {fault}: {count}  ({report.examples[fault]})")
    for path, message in errors.items():
        print(f"{path}: {message}", file=sys.stderr)

    scanned = sum(report.scanned for report in reports.values())
    failed = sum(report.failed for report in reports.values())
    print(f"Scanned {scanned} pre-states; {failed} with violations; {len(errors)} input errors.")
    if args.json:
        result = {
            "scanned": scanned,
            "failed": failed,
            "providers": {name: asdict(report) for name, report in reports.items()},
            "errors": errors,
        }
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if not scanned and not errors:
        print(f"No matching generated Gloas cases under {args.test_dir}", file=sys.stderr)
    if errors or not scanned:
        return 2
    return int(failed > 0)


if __name__ == "__main__":
    raise SystemExit(main())
