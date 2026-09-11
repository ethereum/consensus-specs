from __future__ import annotations

from typing import TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.comparison_witness import (
    value_for_comparison,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

_DIMS = [
    "previous_epoch_occupancy",
    "target_weight_to_quorum",
    "target_amount_nonzero",
    "qualifying_payment_count",
    "mixed_quorum_relations",
    "next_epoch_payments_occupancy",
    "preexisting_withdrawals_occupancy",
    "outcome",
    "state_effected",
]


class BuilderPendingPaymentsMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "builder_pending_payments"

    def materialize_solution(self, sol) -> tuple[dict, list[TestCasePart]]:
        s = self.spec
        pre = create_genesis_state(
            s,
            validator_balances=[s.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=s.MAX_EFFECTIVE_BALANCE,
        )
        s.process_slots(pre, s.Slot(s.SLOTS_PER_EPOCH - 1))
        q = s.get_builder_payment_quorum_threshold(pre)
        assert q > 0
        spe = int(s.SLOTS_PER_EPOCH)

        def payment(weight, amount):
            fee_recipient, _ = distinct_bytes(self.rng, 20)
            return s.BuilderPendingPayment(
                weight=s.Gwei(weight),
                withdrawal=s.BuilderPendingWithdrawal(
                    fee_recipient=s.ExecutionAddress(fee_recipient),
                    amount=s.Gwei(amount),
                    builder_index=s.BuilderIndex(self.rng.randrange(64)),
                ),
                proposer_index=s.ValidatorIndex(self.rng.randrange(64)),
            )

        rel = str(sol.target_weight_to_quorum)
        weight = value_for_comparison(self.rng, rel, int(q)) if rel != "NA" else 0
        amount = 0 if str(sol.target_amount_nonzero) == "F" else self.rng.randrange(1, 1_000)
        occ = str(sol.previous_epoch_occupancy)
        count = str(sol.qualifying_payment_count)
        previous_slots = (
            tuple(range(spe))
            if occ == "FULL"
            else tuple(sorted(distinct_indices(self.rng, spe, 3)))
        )
        if occ == "SINGLE":
            pre.builder_pending_payments[previous_slots[0]] = payment(weight, amount)
        elif occ in {"MULTIPLE", "FULL"}:
            payment_count = 3 if occ == "MULTIPLE" else spe
            if bool(sol.mixed_quorum_relations):
                weights = [
                    value_for_comparison(self.rng, "LT", int(q)),
                    int(q),
                    value_for_comparison(self.rng, "GT", int(q)),
                ] + [
                    value_for_comparison(self.rng, "LT", int(q))
                    for _ in range(payment_count - 3)
                ]
            else:
                qualifiers = {"ZERO": 0, "ONE": 1, "MULTIPLE_COUNT": 2}[count]
                ws = [weight]
                qualifying_weight = max(weight, q)
                ws.extend([qualifying_weight] * max(0, qualifiers - int(weight >= q)))
                ws.extend(
                    value_for_comparison(self.rng, "LT", int(q))
                    for _ in range(payment_count - len(ws))
                )
                weights = ws
            for i, (slot, entry_weight) in enumerate(zip(previous_slots, weights, strict=True)):
                entry_amount = amount if i == 0 else self.rng.randrange(1, 1_000)
                pre.builder_pending_payments[slot] = payment(entry_weight, entry_amount)
        next_epoch_count = {
            "EMPTY": 0,
            "SINGLE": 1,
            "MULTIPLE": 2,
            "FULL": spe,
        }[str(sol.next_epoch_payments_occupancy)]
        next_slots = (
            tuple(range(spe))
            if next_epoch_count == spe
            else tuple(sorted(distinct_indices(self.rng, spe, next_epoch_count)))
        )
        for slot in next_slots:
            pre.builder_pending_payments[spe + slot] = payment(
                value_for_comparison(self.rng, "GT", int(q)), self.rng.randrange(1, 1_000)
            )

        withdrawal_count = {
            "ZERO": 0,
            "ONE": 1,
            "MULTIPLE_COUNT": 2,
        }[str(sol.preexisting_withdrawals_occupancy)]
        for _ in range(withdrawal_count):
            fee_recipient, _ = distinct_bytes(self.rng, 20)
            pre.builder_pending_withdrawals.append(
                s.BuilderPendingWithdrawal(
                    fee_recipient=s.ExecutionAddress(fee_recipient),
                    amount=s.Gwei(self.rng.randrange(1, 1_000)),
                    builder_index=s.BuilderIndex(self.rng.randrange(64)),
                )
            )
        post = pre.copy()
        s.process_builder_pending_payments(post)
        claimed = {
            n: (bool(v) if isinstance(v := getattr(sol, n), bool) else str(v)) for n in _DIMS
        }
        meta = {"description": "process_builder_pending_payments", "claimed": claimed}
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts
