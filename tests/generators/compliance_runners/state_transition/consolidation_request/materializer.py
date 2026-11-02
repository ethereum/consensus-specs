"""Materialize aspect-model solutions into process_consolidation_request cases.

Realizes source and target validator roles, preset-specific active-balance
witnesses for the consolidation churn gate, and queue inputs. No BLS. The
operation returns normally on every path, so `post` is always present.

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

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

_VALIDATOR_COUNT_BY_CHURN_RELATION = {
    "LT": 16,
    "EQ": 32,
    "GT": 64,
}
PENDING_WITHDRAWAL_AMOUNT = 10**9


class ConsolidationRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "consolidation_request"

    def __init__(self, spec, fork_name="gloas", preset_name="minimal", seed=0):
        super().__init__(spec, fork_name, preset_name, seed)
        self._bases = {}

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
        same = sol.same_source_target
        source_found = sol.validator_pubkey_found
        inactive_source = source_found and not sol.validator_active
        inactive_target = not same and sol.target_found and not sol.target_active
        # Churn depends on active effective balance, not validator count. The
        # source and target below may become inactive, so reserve replacements.
        relation = sol.consolidation_churn_to_min_activation
        quotient = int(spec.config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT)
        # The legacy 16/32/64 counts realize minimal's churn boundaries. On
        # mainnet, use a compact pool of compounding validators to supply the
        # much larger total active balance required by its churn quotient.
        total_balance = None
        if quotient > 64 and relation != "LT":
            desired_churn = int(spec.MIN_ACTIVATION_BALANCE)
            if relation == "GT":
                desired_churn += int(spec.EFFECTIVE_BALANCE_INCREMENT)
            total_balance = desired_churn * quotient
            maximum = int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA)
            role_count = 64
            n = role_count + (total_balance + maximum - 1) // maximum
        else:
            n = (
                max(int(spec.SLOTS_PER_EPOCH), _VALIDATOR_COUNT_BY_CHURN_RELATION[relation])
                + inactive_source
                + inactive_target
            )
            role_count = n
        if n not in self._bases:
            self._bases[n] = create_genesis_state(
                spec,
                validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * role_count
                + [spec.MAX_EFFECTIVE_BALANCE_ELECTRA] * (n - role_count),
                activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
            )
        pre = self._bases[n].copy()
        current_epoch = self.rng.randrange(
            int(spec.config.SHARD_COMMITTEE_PERIOD) + 10,
            int(spec.config.SHARD_COMMITTEE_PERIOD) + 101,
        )
        pre.slot = spec.Slot(current_epoch * spec.SLOTS_PER_EPOCH)
        source_index, target_index = distinct_indices(self.rng, role_count, 2)
        absent_source_index, absent_target_index = distinct_indices(
            self.rng,
            len(pubkeys) - n,
            2,
        )
        absent_source = pubkeys[n + absent_source_index]
        absent_target = pubkeys[n + absent_target_index]
        credential_address, other_address = credential_and_other_address(self.rng)

        # ---- source validator --------------------------------------------------
        if source_found:
            self._set_validator(
                pre.validators[source_index],
                sol.validator_credential,
                credential_address,
                current_epoch,
                sol.validator_active,
                sol.validator_exiting,
                sol.validator_old_enough,
            )
            if sol.churn_variant == "CARRY_OVERFLOW":
                pre.validators[source_index].effective_balance = spec.Gwei(
                    int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA)
                )
            source_pubkey = pre.validators[source_index].pubkey
            source_address = credential_address if sol.source_address_matches else other_address
        else:
            source_pubkey = absent_source
            source_address = credential_address

        switch_balance = sol.switch_balance_to_min_activation
        if switch_balance != "NA":
            minimum = int(spec.MIN_ACTIVATION_BALANCE)
            if switch_balance == "LT":
                pre.balances[source_index] = spec.Gwei(self.rng.randrange(minimum))
            elif switch_balance == "GT":
                pre.balances[source_index] = spec.Gwei(
                    minimum + self.rng.randrange(1, PENDING_WITHDRAWAL_AMOUNT + 1)
                )

        activation_epoch = int(spec.compute_activation_exit_epoch(spec.get_current_epoch(pre)))
        source_balance = int(pre.validators[source_index].effective_balance)
        variant = sol.churn_variant
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
        elif sol.target_found:
            self._set_validator(
                pre.validators[target_index],
                sol.target_credential,
                credential_address,
                current_epoch,
                sol.target_active,
                sol.target_exiting,
                old_enough=True,
            )
            target_pubkey = pre.validators[target_index].pubkey
        else:
            target_pubkey = absent_target

        if total_balance is not None:
            role_balance = sum(
                int(v.effective_balance)
                for v in pre.validators[:role_count]
                if spec.is_active_validator(v, spec.Epoch(current_epoch))
            )
            remaining = total_balance - role_balance
            for index in range(role_count, n):
                balance = min(int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA), max(0, remaining))
                validator = pre.validators[index]
                validator.effective_balance = spec.Gwei(balance)
                pre.balances[index] = spec.Gwei(balance)
                if not balance:
                    validator.activation_epoch = spec.FAR_FUTURE_EPOCH
                remaining -= balance
            if remaining != 0:
                raise ValueError("insufficient filler balance for the consolidation churn witness")

        # ---- source pending partial withdrawal ---------------------------------
        if source_found and sol.has_pending_partial_withdrawal:
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(source_index),
                    amount=spec.Gwei(self.rng.randrange(1, PENDING_WITHDRAWAL_AMOUNT + 1)),
                    withdrawable_epoch=spec.Epoch(current_epoch + self.rng.randrange(11)),
                )
            )

        # ---- pending consolidations queue --------------------------------------
        queue_capacity = sol.pending_consolidations_capacity
        queue_limit = int(spec.PENDING_CONSOLIDATIONS_LIMIT)
        queue_length = (
            self.rng.randint(1, min(64, queue_limit - 1))
            if queue_capacity == "AVAILABLE"
            else queue_length_from_profile(queue_capacity, queue_limit, self.rng)
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

        claimed = self.claimed_record(TARGET, sol)
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


MATERIALIZER = ConsolidationRequestMaterializer
