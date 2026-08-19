"""Coverage profiles for the Gloas ``process_withdrawals`` handler.

Aspects follow the handler body: the parent guard, one aspect per stage of
``get_expected_withdrawals``, the pre-state bookkeeping the getter does not
determine, and one effect aspect per group of state updates.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    cover,
    dedup,
    enumerate_signatures,
)
from tests.generators.compliance_runners.state_transition.withdrawals.materializer import (
    _DIMS,
    WithdrawalsMaterializer,
)

INPUT_ASPECTS = {
    "parent": ["parent_payload_revealed"],
    "builder_pending": ["bp_queue", "bp_amount_to_balance"],
    "pending_partial": ["pp_queue", "pp_withdrawable", "pp_eligible", "pp_amount_to_excess"],
    "builder_sweep": ["bs_registry", "bs_eligible", "bs_cursor_high"],
    "validator_sweep": ["vs_fill", "vs_cursor_high"],
    "bookkeeping": ["next_index_start", "stale_payload_expected"],
}
# One aspect per group of update_* calls, so an effect obligation is stated
# against the statement that produces it rather than against the inputs.
EFFECT_ASPECTS = {
    "outcome": ["outcome", "reserve_saturated"],
    "queue_updates": ["eff_builder_pending", "eff_pending_partial"],
    "cursor_updates": ["eff_builder_cursor", "eff_validator_cursor"],
    "write_updates": ["eff_next_index", "eff_payload_expected"],
    "saturation": ["eff_builder_saturated", "eff_partial_truncated"],
}
ALL_ASPECTS = {**INPUT_ASPECTS, **EFFECT_ASPECTS}
ACCEPT = {"NO_WITHDRAWALS", "PARTIAL_PAYLOAD", "FULL_PAYLOAD"}
MODEL = Path(__file__).parent / "models" / "handler_withdrawals.mzn"


def _nfaults(record: dict) -> int:
    """Rank: a revealed parent is the cleaner representative of any signature."""
    return int(not record["parent_payload_revealed"])


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": ({**INPUT_ASPECTS, **EFFECT_ASPECTS}, 2, "normal"),
    "exceptional": ({**INPUT_ASPECTS, "outcome": EFFECT_ASPECTS["outcome"]}, 1, "exceptional"),
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(records, name: str):
    if name == "all":
        return len(records), records
    if name == "standard":
        _, normal = cover(records, *PROFILES["normal"], accept=ACCEPT)
        _, exceptional = cover(records, *PROFILES["exceptional"], accept=ACCEPT)
        return -1, dedup(normal + exceptional, ALL_ASPECTS)
    aspects, strength, outcome_filter = PROFILES[name]
    return cover(records, aspects, strength, outcome_filter, accept=ACCEPT)


def materialize_profile(name: str) -> int:
    _, chosen = build_profile(_recs(), name)
    return WithdrawalsMaterializer(spec, MODEL).materialize_reps(
        Path(__file__).parent / "reftests", [SimpleNamespace(**record) for record in chosen]
    )


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    materialize = "--materialize" in sys.argv
    records = _recs()
    print(f"distinct aspect-state signatures: {len(records)}\n")
    if not args:
        print(f"{'profile':14} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "normal", "exceptional"):
            obligations, cases = build_profile(records, name)
            print(f"{name:14} {obligations:>12} {len(cases):>7}")
        _, cases = build_profile(records, "standard")
        print(f"{'standard':14} {'(union)':>12} {len(cases):>7}")
        return 0
    obligations, cases = build_profile(records, args[0])
    print(
        f"profile '{args[0]}': {len(cases)} cases"
        + (f" covering {obligations} obligations" if obligations >= 0 else "")
    )
    if materialize:
        materialize_profile(args[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
