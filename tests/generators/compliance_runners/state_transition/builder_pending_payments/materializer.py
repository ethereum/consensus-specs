from __future__ import annotations

from typing import TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
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

        def payment(slot, weight, amount):
            return s.BuilderPendingPayment(
                weight=s.Gwei(weight),
                withdrawal=s.BuilderPendingWithdrawal(
                    fee_recipient=s.ExecutionAddress(bytes([slot + 1]) * 20),
                    amount=s.Gwei(amount),
                    builder_index=s.BuilderIndex(slot + 10),
                ),
                proposer_index=s.ValidatorIndex(slot + 20),
            )

        rel = str(sol.target_weight_to_quorum)
        weight = {"LT": q - 1, "EQ": q, "GT": q + 1}.get(rel, 0)
        amount = 0 if str(sol.target_amount_nonzero) == "F" else 100
        occ = str(sol.previous_epoch_occupancy)
        count = str(sol.qualifying_payment_count)
        if occ == "SINGLE":
            pre.builder_pending_payments[0] = payment(0, weight, amount)
        elif occ in {"MULTIPLE", "FULL"}:
            payment_count = 3 if occ == "MULTIPLE" else spe
            if bool(sol.mixed_quorum_relations):
                weights = [q - 1, q, q + 1] + [q - 1] * (payment_count - 3)
                for i, w in enumerate(weights):
                    pre.builder_pending_payments[i] = payment(i, w, amount + i)
            else:
                qualifiers = {"ZERO": 0, "ONE": 1, "MULTIPLE_COUNT": 2}[count]
                ws = [weight]
                qualifying_weight = max(weight, q)
                ws.extend([qualifying_weight] * max(0, qualifiers - int(weight >= q)))
                ws.extend([q - 1] * (payment_count - len(ws)))
                for i, w in enumerate(ws):
                    pre.builder_pending_payments[i] = payment(i, w, amount + i)
        next_epoch_count = {
            "EMPTY": 0,
            "SINGLE": 1,
            "MULTIPLE": 2,
            "FULL": spe,
        }[str(sol.next_epoch_payments_occupancy)]
        for i in range(next_epoch_count):
            pre.builder_pending_payments[spe + i] = payment(i + 7, q + 1, 77 + i)

        withdrawal_count = {
            "ZERO": 0,
            "ONE": 1,
            "MULTIPLE_COUNT": 2,
        }[str(sol.preexisting_withdrawals_occupancy)]
        for i in range(withdrawal_count):
            pre.builder_pending_withdrawals.append(
                s.BuilderPendingWithdrawal(
                    fee_recipient=s.ExecutionAddress(bytes([0xAA + i]) * 20),
                    amount=s.Gwei(99 + i),
                    builder_index=s.BuilderIndex(99 + i),
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
