"""Coverage profiles for the withdrawal-processing handler aspects.

The withdrawal-processing handler covers two aspect models:

- ``builder_pending_withdrawal_processing`` — a single pending builder
  withdrawal entry (referenced builder + amount-vs-balance comparisons).
- ``withdrawal_processing`` — the aggregate pending builder/validator queues,
  the builder sweep, and the validator sweep.

This module enumerates each model's feasible space and selects a coverage
profile (``standard`` = pairwise, ``exhaustive`` = every distinct signature).

``materialize_profile`` feeds the chosen solutions of both models to the single
merged materializer.
"""

from __future__ import annotations

import sys
from pathlib import Path

import minizinc

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import cover, signature
from tests.generators.compliance_runners.state_transition.withdrawal_processing.materializer import (
    _normalize_pending_withdrawal,
    _normalize_withdrawal_processing,
    WithdrawalProcessingMaterializer,
)

ASPECTS_DIR = Path(__file__).parent.parent / "aspects" / "withdrawal_processing"

PENDING_MODEL = ASPECTS_DIR / "builder_pending_withdrawal_processing.mzn"
WITHDRAWAL_PROCESSING_MODEL = ASPECTS_DIR / "withdrawal_processing.mzn"

# --- builder_pending_withdrawal_processing ---

PENDING_ASPECTS = {
    "payload": ["state_latest_block_hash_match"],
    "amount": ["cmp_pending_amount_zero", "cmp_builder_balance_amount"],
    "builder": [
        "payload_builder_version",
        "cmp_state_epoch_deposit_epoch",
        "cmp_state_epoch_withdrawal_epoch",
        "cmp_finalized_epoch_deposit_epoch",
        "withdrawable_epoch_set",
        "cmp_balance_zero",
        "cmp_balance_min_deposit",
        "has_pending_payments",
        "has_pending_withdrawals",
    ],
}

# --- withdrawal_processing ---

WITHDRAWAL_PROCESSING_ASPECTS = {
    "payload": ["state_latest_block_hash_match"],
    "builder_pending": [
        "builder_pending_withdrawals_exist",
        "builder_pending_withdrawals_hit_limit",
    ],
    "validator_pending": [
        "validator_pending_withdrawals_exist",
        "eligible_validator_pending_withdrawals_exist",
        "validator_pending_withdrawals_hit_limit",
    ],
    "builder_sweep": [
        "cmp_builder_count_withdrawals_limit",
        "cmp_builder_count_max_per_sweep",
        "cmp_eligible_builder_count_zero",
        "cmp_swept_count_zero",
        "cmp_swept_count_max_per_sweep",
        "cmp_next_index_zero",
        "cmp_next_index_last_builder_index",
        "swept_builders_hit_withdrawals_limit",
    ],
    "validator_sweep": [
        "validators_eligible_for_sweep_exist",
        "swept_validators_hit_limit",
    ],
}

PROFILES = {"standard": 2, "exhaustive": None}


def _flatten_withdrawal_processing(sol) -> dict:
    rec = _normalize_withdrawal_processing(sol)
    rec.update(rec.pop("builder_sweep", {}))
    return rec


# (model_path, normalize, aspects) per model; normalization flattens to the
# flat claimed-dimension dict consumed by `signature`/`cover`.
_MODELS = [
    (PENDING_MODEL, _normalize_pending_withdrawal, PENDING_ASPECTS),
    (WITHDRAWAL_PROCESSING_MODEL, _flatten_withdrawal_processing, WITHDRAWAL_PROCESSING_ASPECTS),
]


def _pairs(model_path: Path, normalize, aspects: dict) -> list[tuple]:
    """Distinct (solution, record) pairs, deduplicated by aspect signature."""
    model = minizinc.Model(str(model_path))
    result = minizinc.Instance(minizinc.Solver.lookup("gecode"), model).solve(all_solutions=True)
    seen: dict = {}
    for sol in result:
        rec = normalize(sol)
        rec["_rank"] = 0
        seen.setdefault(signature(rec, aspects), (sol, rec))
    return list(seen.values())


def _records(model_path: Path, normalize, aspects: dict) -> list[dict]:
    return [rec for _, rec in _pairs(model_path, normalize, aspects)]


def _build_profile(model_path: Path, normalize, aspects: dict, name: str) -> list[dict]:
    records = _records(model_path, normalize, aspects)
    strength = PROFILES[name]
    if strength is None:
        return records
    _, chosen = cover(records, aspects, strength, None)
    return chosen


def build_profile(name: str) -> list[dict]:
    return [
        rec
        for model_path, normalize, aspects in _MODELS
        for rec in _build_profile(model_path, normalize, aspects, name)
    ]


def materialize_profile(name: str) -> int:
    materializer = WithdrawalProcessingMaterializer(spec)
    solutions = []
    for model_path, normalize, aspects in _MODELS:
        sol_by_sig = {
            signature(rec, aspects): sol for sol, rec in _pairs(model_path, normalize, aspects)
        }
        for rec in _build_profile(model_path, normalize, aspects, name):
            solutions.append(sol_by_sig[signature(rec, aspects)])

    output_dir = Path(__file__).parent / "reftests"
    return materializer.materialize_reps(output_dir, solutions)[0]


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    materialize = "--materialize" in sys.argv
    counts = [len(_records(m, n, a)) for m, n, a in _MODELS]
    print(
        "distinct aspect-state signatures: "
        f"{counts[0]} builder-pending, {counts[1]} withdrawal-processing\n"
    )
    if not args:
        print(f"{'profile':14} {'cases':>7}")
        for name in PROFILES:
            print(f"{name:14} {len(build_profile(name)):>7}")
        return 0
    name = args[0]
    print(f"profile '{name}': {len(build_profile(name))} cases")
    if materialize:
        materialize_profile(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
