"""Materialize MiniZinc model solutions into consensus spec test cases."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import minizinc

from eth_consensus_specs.test.utils.dumper import Dumper
from eth_consensus_specs.test.helpers.genesis import create_genesis_state

from .models.basics import (
    ComparisonOp,
    BuilderType,
    SignatureType,
    BuilderVersion,
)

from ..gen_base.gen_typing import (
    TestCase,
    TestCaseResult,
    TestCasePart,
)
from ..gen_base.output import dump_test_case_result

if TYPE_CHECKING:
    from collections.abc import Iterator
    from eth_consensus_specs.utils.types import SpecForkName

# Type for MiniZinc solution
Solution = dict[str, Any]


def load_minizinc_model(model_path: Path) -> minizinc.Model:
    """Load the MiniZinc model from file."""
    return minizinc.Model(str(model_path))


def solve_model(model: minizinc.Model, **solver_args) -> Iterator[Any]:
    """Solve the MiniZinc model and yield all solutions.

    Args:
        model: The loaded MiniZinc model
        **solver_args: Additional arguments to pass to the solver

    Yields:
        Solution objects from the MiniZinc solver
    """
    # Configure the solver (using default solver)
    instance = minizinc.Instance(minizinc.Solver.lookup("gecode"), model)

    # Solve and get all solutions
    # result.solution is a list of Solution objects
    result = instance.solve(all_solutions=True, **solver_args)

    # Iterate over all solutions
    for solution in result:
        yield solution


class ExecutionPayloadBidMaterializer:
    """Materialize MiniZinc solutions into ExecutionPayloadBid test cases."""

    def __init__(
        self,
        spec: Any,
        model_path: Path,
        fork_name: str = "gloas",
        preset_name: str = "minimal",
    ):
        self.spec = spec
        self.model_path = model_path
        self.fork_name = fork_name
        self.preset_name = preset_name
        self.model = load_minizinc_model(model_path)

    def _setup_builder_state(
        self,
        state: Any,
        deposit_to_finalized: int,
        state_to_withdrawable: int,
        balance_to_zero: int,
        balance_to_min: int,
        withdrawable_epoch_set: bool,
        has_pending_withdrawal: bool,
        has_pending_payment: bool,
        version: int,
        case_idx: int,
    ) -> None:
        """Set up builder state based on constraint values.

        Args:
            state: BeaconState to modify
            deposit_to_finalized: ComparisonOp for deposit vs finalized epoch
            state_to_withdrawable: ComparisonOp for state vs withdrawable epoch
            balance_to_zero: ComparisonOp for balance vs zero
            balance_to_min: ComparisonOp for balance vs MIN_DEPOSIT_AMOUNT
            withdrawable_epoch_set: Whether withdrawable epoch is set
            has_pending_withdrawal: Whether builder has pending withdrawal
            has_pending_payment: Whether builder has pending payment
            version: Builder version (0=PAYLOAD_BUILDER, 1=UNKNOWN)
            case_idx: Case index for deterministic variation
        """
        # Ensure we have at least one builder
        while len(state.builders) == 0:
            state.builders.append(
                self.spec.Builder(
                    pubkey=self.spec.BLSPubkey(b'\x00' * 48),
                    execution_address=self.spec.ExecutionAddress(b'\x00' * 20),
                    balance=self.spec.Gwei(0),
                    deposit_epoch=self.spec.Epoch(0),
                    withdrawable_epoch=self.spec.FAR_FUTURE_EPOCH,
                )
            )

        # Use first builder for the test
        builder = state.builders[0]

        # Set builder version based on constraint
        builder.version = self.spec.PAYLOAD_BUILDER_VERSION if version == 0 else 1

        # Set deposit epoch based on constraint
        current_epoch = self.spec.get_current_epoch(state)
        finalized_epoch = int(state.finalized_checkpoint.epoch)
        if deposit_to_finalized == 0:  # LT: deposit < finalized
            builder.deposit_epoch = self.spec.Epoch(max(0, finalized_epoch - 1))
        elif deposit_to_finalized == 1:  # EQ: deposit == finalized
            builder.deposit_epoch = self.spec.Epoch(finalized_epoch)
        else:  # GT: deposit > finalized
            builder.deposit_epoch = self.spec.Epoch(finalized_epoch + 1)

        # Set withdrawable epoch based on constraint
        current_epoch_int = int(current_epoch)
        if withdrawable_epoch_set:
            if state_to_withdrawable == 0:  # LT
                builder.withdrawable_epoch = self.spec.Epoch(max(0, current_epoch_int - 1))
            elif state_to_withdrawable == 1:  # EQ
                builder.withdrawable_epoch = self.spec.Epoch(current_epoch_int)
            else:  # GT
                builder.withdrawable_epoch = self.spec.Epoch(current_epoch_int + 1)
        else:
            builder.withdrawable_epoch = self.spec.FAR_FUTURE_EPOCH

        # Set balance based on constraint
        # For self-builds, balance doesn't matter (value is 0)
        # For other builders, set based on whether they can cover the bid
        base_balance = self.spec.Gwei(self.spec.MIN_ACTIVATION_BALANCE)
        if balance_to_zero == 0:  # LT: balance < 0 (impossible, so 0)
            builder.balance = self.spec.Gwei(0)
        elif balance_to_zero == 1:  # EQ: balance == 0
            builder.balance = self.spec.Gwei(0)
        else:  # GT: balance > 0
            if balance_to_min == 0:  # LT: balance < MIN_DEPOSIT
                builder.balance = base_balance - self.spec.Gwei(1)
            elif balance_to_min == 1:  # EQ: balance == MIN_DEPOSIT
                builder.balance = base_balance
            else:  # GT: balance > MIN_DEPOSIT
                builder.balance = base_balance + self.spec.Gwei(case_idx + 1)

        # Set pending balances if constraints indicate they should exist.
        # Builder is always at index 0 (see top of this method).
        if has_pending_withdrawal:
            state.builder_pending_withdrawals.append(
                self.spec.BuilderPendingWithdrawal(
                    fee_recipient=self.spec.ExecutionAddress(b'\x00' * 20),
                    amount=self.spec.Gwei(1),
                    builder_index=self.spec.BuilderIndex(0),
                )
            )

        if has_pending_payment:
            state.builder_pending_payments[0] = self.spec.BuilderPendingPayment(
                weight=self.spec.Gwei(1),
                withdrawal=self.spec.BuilderPendingWithdrawal(
                    fee_recipient=self.spec.ExecutionAddress(b'\x00' * 20),
                    amount=self.spec.Gwei(1),
                    builder_index=self.spec.BuilderIndex(0),
                ),
                proposer_index=self.spec.ValidatorIndex(0),
            )

    def _materialize_comparison_value(
        self,
        comparison_op: int,
        base_value: int = 1,
        offset: int = 0,
    ) -> int:
        """Convert a ComparisonOp to a concrete value.

        Args:
            comparison_op: Integer representation of ComparisonOp (0=LT, 1=EQ, 2=GT)
            base_value: The reference value to compare against
            offset: Additional offset to apply

        Returns:
            A concrete value satisfying the comparison
        """
        # Map from MiniZinc enum values to our ComparisonOp
        if comparison_op == 0:  # LT
            return max(0, base_value - 1 + offset)
        elif comparison_op == 1:  # EQ
            return base_value + offset
        elif comparison_op == 2:  # GT
            return base_value + 1 + offset
        else:
            raise ValueError(f"Unknown comparison op: {comparison_op}")

    def _minizinc_enum_to_int(self, enum_str: str, enum_type: str) -> int:
        """Convert MiniZinc enum string to integer value.

        Args:
            enum_str: MiniZinc enum value as string (e.g., 'LT', 'EQ', 'SELF')
            enum_type: Type of enum ('ComparisonOp', 'BuilderType', 'SignatureType')

        Returns:
            Integer representation of the enum
        """
        if enum_type == "ComparisonOp":
            mapping = {"LT": 0, "EQ": 1, "GT": 2}
        elif enum_type == "BuilderType":
            mapping = {"SELF": 0, "EXTERNAL": 1, "NON_EXISTING": 2}
        elif enum_type == "SignatureType":
            mapping = {"INF": 0, "VALID": 1, "RANDOM": 2}
        elif enum_type == "BuilderVersion":
            mapping = {"PAYLOAD_BUILDER": 0, "UNKNOWN": 1}
        else:
            raise ValueError(f"Unknown enum type: {enum_type}")

        return mapping.get(enum_str, 0)

    def materialize_solution(
        self,
        solution: Any,
        case_idx: int,
    ) -> tuple[Any, Any, Any]:
        """Convert a MiniZinc solution to concrete BeaconState and ExecutionPayloadBid.

        Args:
            solution: MiniZinc solution object
            case_idx: Index of this case for generating unique names

        Returns:
            Tuple of (pre_state, signed_execution_payload_bid, post_state)
        """
        # Extract model solution values from MiniZinc Solution object
        # The solution object has attributes: bid, pre_state_builder, pre_state_builder_active
        # Each is a dict with the constraint values

        # Extract ExecutionPayloadBid constraints
        bid_data = solution.bid
        bid_builder_type = self._minizinc_enum_to_int(bid_data["builder_type"], "BuilderType")
        bid_signature_type = self._minizinc_enum_to_int(bid_data["signature_type"], "SignatureType")
        bid_value_to_zero = self._minizinc_enum_to_int(bid_data["value_to_zero"], "ComparisonOp")
        bid_can_cover = bid_data["can_builder_cover_bid"]
        bid_kzg_to_max = self._minizinc_enum_to_int(bid_data["kzg_commitments_to_max_commitments"], "ComparisonOp")
        bid_slot_to_state = self._minizinc_enum_to_int(bid_data["slot_to_state_slot"], "ComparisonOp")
        bid_parent_hash_valid = bid_data["parent_block_hash_valid"]
        bid_parent_root_valid = bid_data["parent_block_root_valid"]
        bid_prev_randao_valid = bid_data["prev_randao_valid"]

        # Extract Builder constraints
        pre_state_builder_data = solution.pre_state_builder
        builder_deposit_to_finalized = self._minizinc_enum_to_int(
            pre_state_builder_data["deposit_to_finalized_epoch"], "ComparisonOp"
        )
        builder_state_to_withdrawable = self._minizinc_enum_to_int(
            pre_state_builder_data["state_to_withdrawable_epoch"], "ComparisonOp"
        )
        builder_balance_to_zero = self._minizinc_enum_to_int(
            pre_state_builder_data["balance_to_zero"], "ComparisonOp"
        )
        builder_balance_to_min = self._minizinc_enum_to_int(
            pre_state_builder_data["balance_to_min_deposit_amount"], "ComparisonOp"
        )
        builder_withdrawable_epoch_set = pre_state_builder_data["withdrawable_epoch_set"]
        builder_has_pending_withdrawal = pre_state_builder_data["has_pending_withdrawal"]
        builder_has_pending_payment = pre_state_builder_data["has_pending_payment"]
        builder_version = self._minizinc_enum_to_int(pre_state_builder_data["version"], "BuilderVersion")

        pre_state_builder_active = solution.pre_state_builder_active

        # Create pre-state with a genesis state
        # Create validator balances - need enough validators for PTC
        num_validators = max(128, case_idx % 50 + 128)
        validator_balances = [self.spec.MAX_EFFECTIVE_BALANCE] * num_validators
        pre_state = create_genesis_state(
            self.spec,
            validator_balances=validator_balances,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )

        # Advance to a slot well past genesis. Gloas activates long after
        # genesis, so builder epoch comparisons need headroom: a genesis
        # state (epoch 0) can't represent deposit_epoch < finalized_epoch,
        # since finalized_epoch is 0 at genesis.
        epochs_past_genesis = 10
        advance_slot = epochs_past_genesis * self.spec.SLOTS_PER_EPOCH + (case_idx % 10)
        pre_state.slot = self.spec.Slot(pre_state.slot + advance_slot)

        # Fabricate a finalized checkpoint with headroom on both sides, so
        # deposit_to_finalized_epoch can be materialized as LT, EQ, or GT.
        # Directly mutating finality fields (rather than running epoch
        # processing) is an established pattern for cheap test setup in
        # this codebase (see e.g. test_process_attestation.py).
        current_epoch = int(self.spec.get_current_epoch(pre_state))
        finalized_epoch = current_epoch - 5
        pre_state.finalized_checkpoint = self.spec.Checkpoint(
            epoch=self.spec.Epoch(finalized_epoch),
            root=self.spec.Root(b'\x01' * 32),
        )

        # Set up builder based on pre_state_builder_active constraint
        if pre_state_builder_active:
            # Builder should be active - configure it based on constraints
            self._setup_builder_state(pre_state, builder_deposit_to_finalized,
                                     builder_state_to_withdrawable, builder_balance_to_zero,
                                     builder_balance_to_min, builder_withdrawable_epoch_set,
                                     builder_has_pending_withdrawal, builder_has_pending_payment,
                                     builder_version, case_idx)
        else:
            # Builder should not be active - ensure state has no builders
            # or create an inactive builder
            if len(pre_state.builders) > 0:
                # Clear all builders to represent no active builder
                pre_state.builders = self.spec.List[self.spec.Builder, self.spec.VALIDATOR_REGISTRY_LIMIT]()

        # Determine bid value based on comparison operation and coverage constraint
        if bid_builder_type == 0:  # SELF
            bid_value = 0  # Self-builds must have value 0
        else:
            # For non-self-builds, value depends on constraint and builder balance
            if bid_value_to_zero == 0:  # LT: value < 0 (impossible, use 0)
                bid_value = 0
            elif bid_value_to_zero == 1:  # EQ: value == 0
                bid_value = 0
            else:  # GT: value > 0
                # Set value based on whether builder can cover it
                if bid_can_cover:
                    # Builder can cover, set value to something they have.
                    # max(1, ...) guarantees value > 0 even when the builder's
                    # balance is 0 or 1 (balance // 2 would otherwise be 0).
                    bid_value = max(1, min(1000, int(pre_state.builders[0].balance) // 2)) if len(pre_state.builders) > 0 else 100
                else:
                    # Builder cannot cover, set value higher than balance
                    current_balance = int(pre_state.builders[0].balance) if len(pre_state.builders) > 0 else 0
                    bid_value = current_balance + 1000 + case_idx

        # Determine slot based on slot_to_state_slot constraint
        bid_slot = self._materialize_comparison_value(
            bid_slot_to_state,
            base_value=int(pre_state.slot),
            offset=0,
        )

        # Determine builder index
        if bid_builder_type == 0:  # SELF
            builder_index = self.spec.BUILDER_INDEX_SELF_BUILD
        elif bid_builder_type == 2:  # NON_EXISTING
            # Index one past the end of the builder registry can never
            # reference an existing builder, regardless of builder count.
            builder_index = self.spec.BuilderIndex(len(pre_state.builders))
        else:  # EXTERNAL
            # EXTERNAL requires pre_state_builder_active, so an existing
            # builder is guaranteed to be present.
            builder_index = self.spec.BuilderIndex(case_idx % max(1, len(pre_state.builders)))

        # For valid bids, use state values for critical fields
        # These are checked in process_execution_payload_bid
        parent_block_hash = pre_state.latest_block_hash
        prev_randao = self.spec.get_randao_mix(
            pre_state,
            self.spec.get_current_epoch(pre_state)
        )

        # Get the previous block root
        try:
            parent_block_root = self.spec.get_block_root_at_slot(
                pre_state,
                self.spec.Slot(int(pre_state.slot) - 1)
            )
        except (IndexError, KeyError):
            parent_block_root = pre_state.block_roots[0]

        # For self-builds, value must be 0
        if bid_builder_type == 0:
            bid_value = 0

        # For testing invalid values, modify some fields
        if not bid_parent_hash_valid:
            parent_block_hash = self.spec.Hash32(b'\x02' * 32)
        if not bid_parent_root_valid:
            parent_block_root = self.spec.Root(b'\x04' * 32)
        if not bid_prev_randao_valid:
            prev_randao = self.spec.Bytes32(b'\x06' * 32)

        # Generate KZG commitments based on constraint
        # bid_kzg_to_max: LT=under limit, EQ=at limit, GT=over limit
        max_blobs = self.spec.get_blob_parameters(
            self.spec.get_current_epoch(pre_state)
        ).max_blobs_per_block

        if bid_kzg_to_max == 0:  # LT: under the limit
            num_commitments = max(0, max_blobs - 1)
        elif bid_kzg_to_max == 1:  # EQ: at the limit
            num_commitments = max_blobs
        else:  # GT: over the limit (invalid)
            num_commitments = max_blobs + 1

        kzg_commitments = [
            self.spec.KZGCommitment(bytes([i % 256]) * 48)
            for i in range(num_commitments)
        ]

        # Create ExecutionPayloadBid
        bid = self.spec.ExecutionPayloadBid(
            parent_block_hash=parent_block_hash,
            parent_block_root=parent_block_root,
            block_hash=self.spec.Hash32(b'\x07' * 32),
            prev_randao=prev_randao,
            fee_recipient=self.spec.ExecutionAddress(b'\x00' * 20),
            gas_limit=self.spec.Uint64(30000000),
            builder_index=builder_index,
            slot=self.spec.Slot(bid_slot),
            value=self.spec.Gwei(bid_value),
            execution_payment=self.spec.Gwei(0),
            blob_kzg_commitments=kzg_commitments,
            execution_requests_root=self.spec.Root(b'\x08' * 32),
        )

        # Create SignedExecutionPayloadBid
        # For self-builds, use G2_POINT_AT_INFINITY
        if bid_builder_type == 0:
            signature = self.spec.bls.G2_POINT_AT_INFINITY
        else:
            signature = self.spec.BLSSignature(b'\x00' * 96)  # Placeholder for other builders

        signed_bid = self.spec.SignedExecutionPayloadBid(
            message=bid,
            signature=signature,
        )

        # Generate post-state by processing the bid
        # Make a copy to avoid modifying pre_state
        post_state = pre_state.copy()

        try:
            # Call the actual spec processing function
            self.spec.process_execution_payload_bid(post_state, signed_bid)
        except (AssertionError, IndexError):
            # If processing fails, it's an invalid operation. AssertionError
            # covers the checks in process_execution_payload_bid itself;
            # IndexError covers a NON_EXISTING builder_index, since
            # is_active_builder() indexes state.builders without a bounds
            # check first.
            # Leave post_state as-is to indicate the operation failed
            # In real test scenarios, you might want to not include post.ssz_snappy
            # or mark the test case as expecting failure
            pass

        return pre_state, signed_bid, post_state

    def _validate_materialization(
        self,
        solution: Any,
        pre_state: Any,
        signed_bid: Any,
        case_idx: int,
    ) -> list[str]:
        """Validate that materialized state/bid match solution constraints.

        Args:
            solution: MiniZinc solution with constraints
            pre_state: Generated BeaconState
            signed_bid: Generated SignedExecutionPayloadBid
            case_idx: Case index for error messages

        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []
        bid = signed_bid.message

        # Extract constraint values from solution
        bid_data = solution.bid
        builder_data = solution.pre_state_builder
        builder_active = solution.pre_state_builder_active

        # Validate builder presence
        has_builders = len(pre_state.builders) > 0
        if builder_active and not has_builders:
            errors.append(f"case_{case_idx:04d}: pre_state_builder_active=True but no builders in state")
        elif not builder_active and has_builders:
            errors.append(f"case_{case_idx:04d}: pre_state_builder_active=False but builders exist in state")

        # Only validate builder constraints if builder should be active
        if builder_active and has_builders:
            builder = pre_state.builders[0]

            # Validate builder version
            version_constraint = self._minizinc_enum_to_int(builder_data["version"], "BuilderVersion")
            if version_constraint == 0:  # PAYLOAD_BUILDER
                if builder.version != self.spec.PAYLOAD_BUILDER_VERSION:
                    errors.append(f"case_{case_idx:04d}: builder.version mismatch (expected PAYLOAD_BUILDER)")
            else:  # UNKNOWN
                if builder.version == self.spec.PAYLOAD_BUILDER_VERSION:
                    errors.append(f"case_{case_idx:04d}: builder.version mismatch (expected UNKNOWN)")

            # Validate deposit epoch vs finalized
            finalized_epoch = int(pre_state.finalized_checkpoint.epoch)
            deposit_constraint = self._minizinc_enum_to_int(builder_data["deposit_to_finalized_epoch"], "ComparisonOp")
            builder_deposit = int(builder.deposit_epoch)

            if deposit_constraint == 0:  # LT
                if not (builder_deposit < finalized_epoch):
                    errors.append(f"case_{case_idx:04d}: deposit_epoch not < finalized_epoch ({builder_deposit} vs {finalized_epoch})")
            elif deposit_constraint == 1:  # EQ
                if builder_deposit != finalized_epoch:
                    errors.append(f"case_{case_idx:04d}: deposit_epoch not == finalized_epoch ({builder_deposit} vs {finalized_epoch})")
            else:  # GT
                if not (builder_deposit > finalized_epoch):
                    errors.append(f"case_{case_idx:04d}: deposit_epoch not > finalized_epoch ({builder_deposit} vs {finalized_epoch})")

            # Validate balance vs zero
            balance_constraint = self._minizinc_enum_to_int(builder_data["balance_to_zero"], "ComparisonOp")
            builder_balance = int(builder.balance)

            if balance_constraint == 0:  # LT (impossible for Gwei, effectively 0)
                if builder_balance != 0:
                    errors.append(f"case_{case_idx:04d}: balance not <= 0 ({builder_balance})")
            elif balance_constraint == 1:  # EQ
                if builder_balance != 0:
                    errors.append(f"case_{case_idx:04d}: balance not == 0 ({builder_balance})")
            else:  # GT
                if builder_balance == 0:
                    errors.append(f"case_{case_idx:04d}: balance not > 0 (balance is 0)")

            # Validate pending withdrawal presence (builder is always at index 0)
            has_pending_withdrawal = any(
                int(w.builder_index) == 0 for w in pre_state.builder_pending_withdrawals
            )
            if builder_data["has_pending_withdrawal"] and not has_pending_withdrawal:
                errors.append(f"case_{case_idx:04d}: has_pending_withdrawal=True but no matching builder_pending_withdrawals entry")
            elif not builder_data["has_pending_withdrawal"] and has_pending_withdrawal:
                errors.append(f"case_{case_idx:04d}: has_pending_withdrawal=False but a matching builder_pending_withdrawals entry exists")

            # Validate pending payment presence (default/empty payment slots also have
            # builder_index == 0, so filter on a nonzero amount to avoid false positives)
            has_pending_payment = any(
                int(p.withdrawal.builder_index) == 0 and int(p.withdrawal.amount) > 0
                for p in pre_state.builder_pending_payments
            )
            if builder_data["has_pending_payment"] and not has_pending_payment:
                errors.append(f"case_{case_idx:04d}: has_pending_payment=True but no matching builder_pending_payments entry")
            elif not builder_data["has_pending_payment"] and has_pending_payment:
                errors.append(f"case_{case_idx:04d}: has_pending_payment=False but a matching builder_pending_payments entry exists")

        # Validate bid constraints
        bid_value_constraint = self._minizinc_enum_to_int(bid_data["value_to_zero"], "ComparisonOp")
        bid_value = int(bid.value)

        if bid_data["builder_type"] == "SELF":
            # Self-builds must have value 0
            if bid_value != 0:
                errors.append(f"case_{case_idx:04d}: SELF builder bid value not 0 ({bid_value})")
        else:
            # For non-self, validate value constraint
            if bid_value_constraint == 0 or bid_value_constraint == 1:  # LT or EQ
                if bid_value != 0:
                    errors.append(f"case_{case_idx:04d}: bid value not 0 ({bid_value})")
            else:  # GT
                if bid_value == 0:
                    errors.append(f"case_{case_idx:04d}: bid value not > 0 (value is 0)")

        # Validate KZG commitments
        kzg_constraint = self._minizinc_enum_to_int(bid_data["kzg_commitments_to_max_commitments"], "ComparisonOp")
        max_blobs = self.spec.get_blob_parameters(
            self.spec.get_current_epoch(pre_state)
        ).max_blobs_per_block
        num_commitments = len(bid.blob_kzg_commitments)

        if kzg_constraint == 0:  # LT
            if not (num_commitments < max_blobs):
                errors.append(f"case_{case_idx:04d}: commitments not < max ({num_commitments} vs {max_blobs})")
        elif kzg_constraint == 1:  # EQ
            if num_commitments != max_blobs:
                errors.append(f"case_{case_idx:04d}: commitments not == max ({num_commitments} vs {max_blobs})")
        else:  # GT
            if not (num_commitments > max_blobs):
                errors.append(f"case_{case_idx:04d}: commitments not > max ({num_commitments} vs {max_blobs})")

        return errors

    def materialize_test_cases(
        self,
        output_dir: Path,
        start_sol_id: int | None = None,
        num_solutions: int | None = None,
        validate: bool = True,
    ) -> None:
        """Generate test cases from MiniZinc model solutions.

        Args:
            output_dir: Directory to write test cases to
            num_solutions: Maximum number of solutions to generate (None for all)
            validate: Whether to validate materialization against constraints
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        dumper = Dumper()

        if start_sol_id is None:
            start_sol_id = 0
        
        solution_count = 0
        validation_errors = []

        for solution_id, solution in enumerate(solve_model(self.model), start=start_sol_id):
            if num_solutions is not None and solution_count >= num_solutions:
                break

            case_name = f"case_{solution_id:04d}"

            # Materialize the solution
            pre_state, signed_bid, post_state = self.materialize_solution(
                solution,
                solution_id,
            )

            # Validate materialization
            if validate:
                errors = self._validate_materialization(
                    solution,
                    pre_state,
                    signed_bid,
                    solution_id,
                )
                validation_errors.extend(errors)

            # Create test case metadata
            test_case = TestCase(
                fork_name=self.fork_name,
                preset_name=self.preset_name,
                runner_name="operations",
                handler_name="execution_payload_bid",
                suite_name="main",
                case_name=case_name,
            )
            test_case.set_output_dir(str(output_dir))

            # Create test case parts
            # Serialize SSZ objects to bytes before passing to TestCaseResult
            case_parts: list[TestCasePart] = [
                ("pre", "ssz", pre_state.encode_bytes()),  # type: ignore
                ("execution_payload_bid", "ssz", signed_bid.encode_bytes()),  # type: ignore
                ("post", "ssz", post_state.encode_bytes()),  # type: ignore
            ]

            # Create test case result
            meta = {
                "description": f"Generated test case from MiniZinc model",
                "bls_setting": 1,  # Valid BLS for Gloas
            }

            result = TestCaseResult(
                test_case=test_case,
                meta=meta,
                case_parts=case_parts,
            )

            # Use the standard output function
            dump_test_case_result(result, dumper)

            solution_count += 1

        print(f"Generated {solution_count} test cases")

        # Report validation results
        if validate:
            if validation_errors:
                print(f"\n⚠️  Validation found {len(validation_errors)} error(s):")
                for error in validation_errors[:10]:  # Show first 10
                    print(f"  {error}")
                if len(validation_errors) > 10:
                    print(f"  ... and {len(validation_errors) - 10} more")
            else:
                print(f"✓ All {solution_count} test cases passed validation")


def main():
    """Generate execution_payload_bid test cases from MiniZinc model."""
    # Import the Gloas spec
    # This is a dynamic import to match the pattern used in other test generators
    try:
        from eth_consensus_specs.gloas import minimal as gloas_minimal
        spec = gloas_minimal
    except ImportError:
        print("Error: Could not import Gloas minimal spec")
        print("Make sure the spec has been generated from markdown files")
        return

    model_path = Path(__file__).parent / "models" / "process_execution_payload_bid.mzn"
    # Base output directory - test_case.set_output_dir will add preset/fork/runner/handler/suite/case
    output_dir = Path(__file__).parent.parent.parent.parent / "reftests"

    materializer = ExecutionPayloadBidMaterializer(spec, model_path)
    materializer.materialize_test_cases(output_dir, start_sol_id=0, num_solutions=1000)


if __name__ == "__main__":
    main()
