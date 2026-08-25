"""Materialize aspect-model solutions for parent execution payload processing."""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.withdrawals import (
    set_parent_block_empty,
    set_parent_block_full,
)
from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

EPOCHS_PAST_GENESIS = 10
EVICTED_EPOCH_DISTANCE = 5
DISPATCH_DEPOSITS_COUNT = 20
FEE_RECIPIENT = b"\xab" * 20
PAYMENT_VALUE = 50_000_000

_DIMS = [
    "parent_payload_revealed",
    "requests_empty",
    "requests_root_matches",
    "withdrawals_within_cap",
    "consolidations_within_cap",
    "builder_deposits_within_cap",
    "builder_exits_within_cap",
    "deposits_nonempty",
    "dispatches_nonempty_requests",
    "payment_settlement",
    "payment_value_nonzero",
    "requests_empty_checked",
    "requests_root_checked",
    "withdrawals_cap_checked",
    "consolidations_cap_checked",
    "builder_deposits_cap_checked",
    "builder_exits_cap_checked",
    "outcome",
    "state_effected",
    "payment_withdrawal_appended",
    "payment_slot_cleared",
]


def _b(solution: Any, name: str) -> bool:
    return bool(getattr(solution, name))


def _s(solution: Any, name: str) -> str:
    return str(getattr(solution, name))


class ParentExecutionPayloadMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "parent_execution_payload"
    """Build operations-format vectors from model representatives."""

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = spec.Slot(EPOCHS_PAST_GENESIS * spec.SLOTS_PER_EPOCH)
        return state

    def _request_list(
        self,
        request_type: Any,
        within_cap: bool,
        cap: int,
        dispatch_nonempty: bool,
    ) -> Any:
        count = 1 if dispatch_nonempty else 0
        if not within_cap:
            count = cap + 1
        return self.spec.ProgressiveList[request_type]([request_type()] * count)

    def _requests(self, solution: Any) -> Any:
        spec = self.spec
        deposits_nonempty = _b(solution, "deposits_nonempty")
        deposits_count = DISPATCH_DEPOSITS_COUNT if deposits_nonempty else 0
        return spec.ExecutionRequests(
            deposits=spec.ProgressiveList[spec.DepositRequest](
                [spec.DepositRequest()] * deposits_count
            ),
            withdrawals=self._request_list(
                spec.WithdrawalRequest,
                _b(solution, "withdrawals_within_cap"),
                spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD,
                deposits_nonempty,
            ),
            consolidations=self._request_list(
                spec.ConsolidationRequest,
                _b(solution, "consolidations_within_cap"),
                spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD,
                deposits_nonempty,
            ),
            builder_deposits=self._request_list(
                spec.BuilderDepositRequest,
                _b(solution, "builder_deposits_within_cap"),
                spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD,
                deposits_nonempty,
            ),
            builder_exits=self._request_list(
                spec.BuilderExitRequest,
                _b(solution, "builder_exits_within_cap"),
                spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD,
                deposits_nonempty,
            ),
        )

    def _parent_slot(self, current_epoch: int, settlement: str) -> int:
        if settlement == "CURRENT_EPOCH":
            parent_epoch = current_epoch
        elif settlement == "PREVIOUS_EPOCH":
            parent_epoch = current_epoch - 1
        else:
            parent_epoch = current_epoch - EVICTED_EPOCH_DISTANCE
        return int(self.spec.compute_start_slot_at_epoch(parent_epoch))

    def _payment_index(self, parent_slot: int, settlement: str) -> int:
        offset = parent_slot % int(self.spec.SLOTS_PER_EPOCH)
        if settlement == "CURRENT_EPOCH":
            return int(self.spec.SLOTS_PER_EPOCH) + offset
        return offset

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        if _b(solution, "parent_payload_revealed"):
            set_parent_block_full(spec, pre)
        else:
            set_parent_block_empty(spec, pre)

        requests = self._requests(solution)
        requests_root = spec.hash_tree_root(requests)
        if _b(solution, "requests_root_matches"):
            pre.latest_execution_payload_bid.execution_requests_root = requests_root
        else:
            mismatched_root = bytes(requests_root)
            mismatched_root = bytes([mismatched_root[0] ^ 1]) + mismatched_root[1:]
            pre.latest_execution_payload_bid.execution_requests_root = spec.Root(mismatched_root)

        settlement = _s(solution, "payment_settlement")
        current_epoch = int(spec.get_current_epoch(pre))
        parent_slot = self._parent_slot(current_epoch, settlement)
        parent_bid = pre.latest_execution_payload_bid
        parent_bid.slot = spec.Slot(parent_slot)
        parent_bid.fee_recipient = spec.ExecutionAddress(FEE_RECIPIENT)
        parent_bid.builder_index = spec.BuilderIndex(0)
        payment_value = spec.Gwei(PAYMENT_VALUE if _b(solution, "payment_value_nonzero") else 0)
        if settlement == "EVICTED":
            parent_bid.value = payment_value
        else:
            payment_index = self._payment_index(parent_slot, settlement)
            pre.builder_pending_payments[payment_index] = spec.BuilderPendingPayment(
                withdrawal=spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(FEE_RECIPIENT),
                    amount=payment_value,
                    builder_index=spec.BuilderIndex(0),
                )
            )

        availability_index = parent_slot % int(spec.SLOTS_PER_HISTORICAL_ROOT)
        pre.execution_payload_availability[availability_index] = 0b0

        block = spec.BeaconBlock()
        block.body.signed_execution_payload_bid.message.parent_block_hash = spec.Hash32(
            pre.latest_block_hash
        )
        block.body.parent_execution_requests = requests

        post = pre.copy()
        try:
            spec.process_parent_execution_payload(post, block)
        except (AssertionError, IndexError):
            post = None

        claimed = {
            name: (
                _b(solution, name)
                if isinstance(getattr(solution, name), bool)
                else _s(solution, name)
            )
            for name in _DIMS
        }
        parts: list[TestCasePart] = [
            ("pre", "ssz", pre.encode_bytes()),
            ("block", "ssz", block.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        meta = {"description": f"process_parent_execution_payload: {claimed['outcome']}", "bls_setting": 1, "claimed": claimed}
        return meta, parts
