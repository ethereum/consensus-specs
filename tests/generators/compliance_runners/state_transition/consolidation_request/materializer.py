"""Materialize aspect-model solutions into process_consolidation_request cases.

The most involved materializer: two validators (source + target), a churn gate
realized by sizing the active validator set (64 -> sufficient, 32 -> ==MIN, i.e.
insufficient), and two queue fills. No BLS. Never raises, so `post` is always
present.

Spec: specs/electra/beacon-chain.md process_consolidation_request (inherited by gloas).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkeys
from tests.generators.compliance_runners.state_transition.aspects_helpers.authorization import (
    credential_and_other_address,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_capacity import (
    queue_length_from_profile,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_from_profile,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

_VALIDATOR_COUNT_BY_CHURN_RELATION = {
    "LT": 16,
    "EQ": 32,
    "GT": 64,
}
PENDING_WITHDRAWAL_AMOUNT = 10**9

_DIMS = [
    "same_source_target",
    "pending_consolidations_capacity",
    "consolidation_churn_to_min_activation",
    "churn_variant",
    "validator_pubkey_found",
    "validator_credential",
    "source_address_matches",
    "validator_active",
    "validator_exiting",
    "validator_old_enough",
    "has_pending_partial_withdrawal",
    "target_found",
    "target_credential",
    "target_active",
    "target_exiting",
    "validator_has_execution_credential",
    "validator_has_compounding_credential",
    "target_has_compounding_credential",
    "outcome",
    "state_effected",
]


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


class ConsolidationRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "consolidation_request"

    def _epochs(
        self, current_epoch: int, active: bool, exiting: bool, old_enough: bool
    ) -> tuple[int, int]:
        far = int(self.spec.FAR_FUTURE_EPOCH)
        committee_period = int(self.spec.config.SHARD_COMMITTEE_PERIOD)
        activation = (
            self.rng.randrange(current_epoch - committee_period + 1)
            if old_enough
            else self.rng.randrange(current_epoch - committee_period + 1, current_epoch + 1)
        )
        if active:
            exit_epoch = current_epoch + self.rng.randrange(1, 11) if exiting else far
        elif exiting:
            exit_epoch = self.rng.randrange(current_epoch + 1)
        else:
            activation, exit_epoch = current_epoch + self.rng.randrange(1, 11), far
        return activation, exit_epoch

    def _set_validator(
        self,
        v: Any,
        credential_profile: str,
        credential_address: bytes,
        current_epoch: int,
        active: bool,
        exiting: bool,
        old_enough: bool,
    ) -> None:
        spec = self.spec
        v.withdrawal_credentials = spec.Bytes32(
            withdrawal_credentials_from_profile(
                spec, credential_profile, credential_address, self.rng
            )
        )
        activation, exit_epoch = self._epochs(current_epoch, active, exiting, old_enough)
        v.activation_epoch = spec.Epoch(activation)
        v.exit_epoch = spec.Epoch(exit_epoch)

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        n = _VALIDATOR_COUNT_BY_CHURN_RELATION[_s(sol, "consolidation_churn_to_min_activation")]
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * n,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        current_epoch = self.rng.randrange(
            int(spec.config.SHARD_COMMITTEE_PERIOD) + 10,
            int(spec.config.SHARD_COMMITTEE_PERIOD) + 101,
        )
        pre.slot = spec.Slot(current_epoch * spec.SLOTS_PER_EPOCH)
        source_index, target_index = distinct_indices(self.rng, n, 2)
        absent_source_index, absent_target_index = distinct_indices(
            self.rng,
            len(pubkeys) - n,
            2,
        )
        absent_source = pubkeys[n + absent_source_index]
        absent_target = pubkeys[n + absent_target_index]
        credential_address, other_address = credential_and_other_address(self.rng)

        same = _b(sol, "same_source_target")
        source_found = _b(sol, "validator_pubkey_found")

        # ---- source validator --------------------------------------------------
        if source_found:
            self._set_validator(
                pre.validators[source_index],
                _s(sol, "validator_credential"),
                credential_address,
                current_epoch,
                _s(sol, "validator_active") == "T",
                _s(sol, "validator_exiting") == "T",
                _s(sol, "validator_old_enough") == "T",
            )
            if _s(sol, "churn_variant") == "CARRY_OVERFLOW":
                pre.validators[source_index].effective_balance = spec.Gwei(
                    int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA)
                )
            source_pubkey = pre.validators[source_index].pubkey
            source_address = (
                credential_address if _s(sol, "source_address_matches") == "T" else other_address
            )
        else:
            source_pubkey = absent_source
            source_address = credential_address

        activation_epoch = int(spec.compute_activation_exit_epoch(spec.get_current_epoch(pre)))
        source_balance = int(pre.validators[source_index].effective_balance)
        variant = _s(sol, "churn_variant")
        if variant == "RESET_FIT":
            pre.earliest_consolidation_epoch = spec.Epoch(max(0, activation_epoch - 1))
            pre.consolidation_balance_to_consume = spec.Gwei(0)
        elif variant == "CARRY_FIT":
            pre.earliest_consolidation_epoch = spec.Epoch(activation_epoch)
            pre.consolidation_balance_to_consume = spec.Gwei(source_balance)
        elif variant == "CARRY_OVERFLOW":
            # A later queue epoch and one-unit remainder exercise reuse plus
            # multi-epoch consolidation queueing.
            pre.earliest_consolidation_epoch = spec.Epoch(activation_epoch + 1)
            pre.consolidation_balance_to_consume = spec.Gwei(1)

        # ---- target validator (consolidation path only) ------------------------
        if same:
            target_pubkey = source_pubkey
        elif _s(sol, "target_found") == "T":
            self._set_validator(
                pre.validators[target_index],
                _s(sol, "target_credential"),
                credential_address,
                current_epoch,
                _s(sol, "target_active") == "T",
                _s(sol, "target_exiting") == "T",
                old_enough=True,
            )
            target_pubkey = pre.validators[target_index].pubkey
        else:
            target_pubkey = absent_target

        # ---- source pending partial withdrawal ---------------------------------
        if source_found and _s(sol, "has_pending_partial_withdrawal") == "T":
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(source_index),
                    amount=spec.Gwei(self.rng.randrange(1, PENDING_WITHDRAWAL_AMOUNT + 1)),
                    withdrawable_epoch=spec.Epoch(current_epoch + self.rng.randrange(11)),
                )
            )

        # ---- pending consolidations queue --------------------------------------
        queue_capacity = _s(sol, "pending_consolidations_capacity")
        queue_length = queue_length_from_profile(
            queue_capacity, int(spec.PENDING_CONSOLIDATIONS_LIMIT), self.rng
        )
        if queue_length:

            def pending_consolidation() -> Any:
                queue_source_index, queue_target_index = distinct_indices(self.rng, n, 2)
                return spec.PendingConsolidation(
                    source_index=spec.ValidatorIndex(queue_source_index),
                    target_index=spec.ValidatorIndex(queue_target_index),
                )

            pre.pending_consolidations = spec.PendingConsolidations(
                data=[pending_consolidation() for _ in range(queue_length)]
            )

        request = spec.ConsolidationRequest(
            source_address=spec.ExecutionAddress(source_address),
            source_pubkey=spec.BLSPubkey(source_pubkey),
            target_pubkey=spec.BLSPubkey(target_pubkey),
        )
        post = pre.copy()
        spec.process_consolidation_request(post, request)  # never raises

        claimed = {
            k: (_b(sol, k) if isinstance(getattr(sol, k), bool) else _s(sol, k)) for k in _DIMS
        }
        meta = {
            "description": f"process_consolidation_request: {claimed['outcome']}",
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("consolidation_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts
