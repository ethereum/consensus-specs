from __future__ import annotations

import sys
from pathlib import Path

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

Y = YAML(typ="safe")


def dec(p, t):
    return t.decode_bytes(snappy.decompress(p.read_bytes()))


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "reftests"
    bad = 0
    cases = sorted(root.glob("**/epoch_processing/builder_pending_payments/**/case_*"))
    if not cases:
        print(f"No cases found under {root}")
        return 1
    for d in cases:
        pre = dec(d / "pre.ssz_snappy", spec.BeaconState)
        post = dec(d / "post.ssz_snappy", spec.BeaconState)
        spe = int(spec.SLOTS_PER_EPOCH)
        q = spec.get_builder_payment_quorum_threshold(pre)
        claimed = Y.load((d / "dimensions.yaml").read_text())["claimed"]
        appended = [p.withdrawal for p in pre.builder_pending_payments[:spe] if p.weight >= q]
        payments = list(pre.builder_pending_payments[spe:]) + [
            spec.BuilderPendingPayment() for _ in range(spe)
        ]
        withdrawals = list(pre.builder_pending_withdrawals) + appended
        expected = pre.copy()
        expected.builder_pending_payments = payments
        expected.builder_pending_withdrawals = withdrawals
        first = list(pre.builder_pending_payments[:spe])
        occupied = [p for p in first if p != spec.BuilderPendingPayment()]
        relation = (
            "NA"
            if not occupied
            else ("LT" if occupied[0].weight < q else "EQ" if occupied[0].weight == q else "GT")
        )
        actual = {
            "previous_epoch_occupancy": "EMPTY"
            if not occupied
            else "SINGLE"
            if len(occupied) == 1
            else "MULTIPLE",
            "target_weight_to_quorum": relation,
            "target_amount_nonzero": "NA"
            if not occupied
            else "T"
            if occupied[0].withdrawal.amount
            else "F",
            "qualifying_payment_count": "ZERO"
            if not appended
            else "ONE"
            if len(appended) == 1
            else "MULTIPLE_COUNT",
            "mixed_quorum_relations": {"LT", "EQ", "GT"}.issubset(
                {"LT" if p.weight < q else "EQ" if p.weight == q else "GT" for p in occupied}
            ),
            "next_epoch_payments_nondefault": any(
                p != spec.BuilderPendingPayment() for p in pre.builder_pending_payments[spe:]
            ),
            "preexisting_withdrawals_nonempty": bool(pre.builder_pending_withdrawals),
            "withdrawals_appended": "ZERO"
            if not appended
            else "ONE"
            if len(appended) == 1
            else "MULTIPLE_COUNT",
            "previous_epoch_discarded": all(
                p == spec.BuilderPendingPayment() for p in post.builder_pending_payments[spe:]
            ),
            "next_epoch_shifted_forward": list(post.builder_pending_payments[:spe])
            == list(pre.builder_pending_payments[spe:]),
            "new_tail_defaulted": all(
                p == spec.BuilderPendingPayment() for p in post.builder_pending_payments[spe:]
            ),
            "outcome": "NO_STATE_CHANGE"
            if not occupied
            and not any(
                p != spec.BuilderPendingPayment() for p in pre.builder_pending_payments[spe:]
            )
            else "ROTATED_ONLY"
            if not appended
            else "APPENDED_ONE_AND_ROTATED"
            if len(appended) == 1
            else "APPENDED_MULTIPLE_AND_ROTATED",
            "state_effected": expected.hash_tree_root() != pre.hash_tree_root(),
        }
        mismatches = [name for name, value in claimed.items() if actual.get(name) != value]
        ok = post.hash_tree_root() == expected.hash_tree_root() and not mismatches
        print(d.name, "OK" if ok else "FAIL")
        for name in mismatches:
            print(f"  {name}: claimed={claimed[name]!r} actual={actual.get(name)!r}")
        bad += not ok
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
