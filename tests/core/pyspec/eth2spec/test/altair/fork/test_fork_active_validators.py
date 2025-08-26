from collections.abc import Callable

from eth2spec.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.constants import ELECTRA, PHASE0
from eth2spec.test.helpers.deposits import prepare_deposit_request, prepare_state_and_deposit
from eth2spec.test.helpers.execution_payload import compute_el_block_hash_for_block
from eth2spec.test.helpers.fork_transition import do_fork_generate
from eth2spec.test.helpers.state import next_epoch, state_transition_and_sign_block
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.test.utils.utils import with_meta_tags
from tests.infra.template_test import (
    template_test_upgrades_all,
    template_test_upgrades_from,
    template_test_upgrades_from_to,
)


@template_test_upgrades_all
def _template_test_at_fork_deactivate_validators_wo_block(
    pre_spec: SpecForkName, post_spec: SpecForkName
) -> tuple[Callable, str]:
    meta_tags = {
        "fork": str(post_spec).lower(),
    }

    @with_phases(phases=[pre_spec], other_phases=[post_spec])
    @spec_test
    @with_state
    @with_meta_tags(meta_tags)
    def test_after_fork_deactivate_validators_wo_block(spec, phases, state):
        current_epoch = spec.get_current_epoch(state)
        fork_epoch = current_epoch + spec.MIN_SEED_LOOKAHEAD + 1

        exited_validators = []
        # Change the active validator set by exiting half of the validators in future epochs
        # within the MIN_SEED_LOOKAHEAD range
        for validator_index in range(len(state.validators) // 2):
            validator = state.validators[validator_index]
            # Set exit_epoch to a future epoch within MIN_SEED_LOOKAHEAD + 1 range
            # This makes the validator active at current_epoch but exited in future epochs
            validator.exit_epoch = fork_epoch
            exited_validators.append(validator_index)

        while spec.get_current_epoch(state) < fork_epoch - 1:
            spec.process_slots(
                state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
            )
            assert state.slot % spec.SLOTS_PER_EPOCH == 0

        spec.process_slots(
            state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
        )
        assert state.slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

        state, _ = yield from do_fork_generate(
            state, spec, phases[post_spec], fork_epoch, with_block=False
        )

        current_epoch = spec.get_current_epoch(state)

        for validator_index in exited_validators:
            validator = state.validators[validator_index]
            # Check that the validator is no longer active
            assert not phases[post_spec].is_active_validator(validator, current_epoch), (
                f"Validator {validator_index} should be inactive at epoch {current_epoch}"
            )

    return (
        test_after_fork_deactivate_validators_wo_block,
        f"test_after_fork_deactivate_validators_wo_block_from_{pre_spec}_to_{post_spec}",
    )


_template_test_at_fork_deactivate_validators_wo_block()

@template_test_upgrades_all
def _template_test_at_fork_deactivate_validators(
    pre_spec: SpecForkName, post_spec: SpecForkName
) -> tuple[Callable, str]:
    meta_tags = {
        "fork": str(post_spec).lower(),
    }

    @with_phases(phases=[pre_spec], other_phases=[post_spec])
    @spec_test
    @with_state
    @with_meta_tags(meta_tags)
    def test_after_fork_deactivate_validators(spec, phases, state):
        current_epoch = spec.get_current_epoch(state)
        fork_epoch = current_epoch + spec.MIN_SEED_LOOKAHEAD + 1

        exited_validators = []
        # Change the active validator set by exiting half of the validators in future epochs
        # within the MIN_SEED_LOOKAHEAD range
        for validator_index in range(len(state.validators) // 2):
            validator = state.validators[validator_index]
            # Set exit_epoch to a future epoch within MIN_SEED_LOOKAHEAD + 1 range
            # This makes the validator active at current_epoch but exited in future epochs
            validator.exit_epoch = fork_epoch
            exited_validators.append(validator_index)

        while spec.get_current_epoch(state) < fork_epoch - 1:
            spec.process_slots(
                state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
            )
            assert state.slot % spec.SLOTS_PER_EPOCH == 0

        spec.process_slots(
            state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
        )
        assert state.slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

        state, _ = yield from do_fork_generate(
            state, spec, phases[post_spec], fork_epoch, with_block=True
        )

        current_epoch = spec.get_current_epoch(state)

        for validator_index in exited_validators:
            validator = state.validators[validator_index]
            # Check that the validator is no longer active
            assert not phases[post_spec].is_active_validator(validator, current_epoch), (
                f"Validator {validator_index} should be inactive at epoch {current_epoch}"
            )

    return (
        test_after_fork_deactivate_validators,
        f"test_after_fork_deactivate_validators_from_{pre_spec}_to_{post_spec}",
    )


_template_test_at_fork_deactivate_validators()


@template_test_upgrades_from_to(PHASE0, ELECTRA)
def _template_test_after_fork_new_validator_active_pre_electra(
    pre_spec: SpecForkName, post_spec: SpecForkName
) -> tuple[Callable, str]:
    meta_tags = {
        "fork": str(post_spec).lower(),
    }

    @with_phases(phases=[pre_spec], other_phases=[post_spec])
    @spec_test
    @with_state
    @with_meta_tags(meta_tags)
    def test_after_fork_new_validator_active(spec, phases, state):
        new_validator_index = len(state.validators)

        amount = spec.MAX_EFFECTIVE_BALANCE

        deposit = prepare_state_and_deposit(spec, state, new_validator_index, amount, signed=True)

        # As `prepare_state_and_deposit` changes the state, we need to create the block after calling it.
        deposit_block = build_empty_block_for_next_slot(spec, state)
        deposit_block.body.deposits = [deposit]

        _ = state_transition_and_sign_block(spec, state, deposit_block)

        next_epoch(spec, state)
        next_epoch(spec, state)

        state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1

        next_epoch(spec, state)

        assert len(state.validators) == new_validator_index + 1

        while (
            state.validators[new_validator_index].activation_eligibility_epoch
            == spec.FAR_FUTURE_EPOCH
        ):
            next_epoch(spec, state)

        while (
            spec.get_current_epoch(state)
            <= state.validators[new_validator_index].activation_eligibility_epoch
        ):
            next_epoch(spec, state)

        state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1

        while state.validators[new_validator_index].activation_epoch == spec.FAR_FUTURE_EPOCH:
            next_epoch(spec, state)

        fork_epoch = state.validators[new_validator_index].activation_epoch
        assert spec.get_current_epoch(state) < fork_epoch - 1

        while spec.get_current_epoch(state) < fork_epoch - 1:
            next_epoch(spec, state)

        new_validator = state.validators[new_validator_index]

        assert not spec.is_active_validator(new_validator, spec.get_current_epoch(state)), (
            f"New Validator should be inactive at epoch {spec.get_current_epoch(state)}"
        )

        spec.process_slots(
            state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
        )
        assert state.slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

        state, _ = yield from do_fork_generate(state, spec, phases[post_spec], fork_epoch)

        new_validator = state.validators[new_validator_index]

        assert spec.is_active_validator(new_validator, spec.get_current_epoch(state)), (
            f"New Validator should be active at epoch {spec.get_current_epoch(state)}"
        )

    return (
        test_after_fork_new_validator_active,
        f"test_after_fork_new_validator_active_from_{pre_spec}_to_{post_spec}",
    )


_template_test_after_fork_new_validator_active_pre_electra()


@template_test_upgrades_from(ELECTRA)
def _template_test_after_fork_new_validator_active_post_electra(
    pre_spec: SpecForkName, post_spec: SpecForkName
) -> tuple[Callable, str]:
    meta_tags = {
        "fork": str(post_spec).lower(),
    }

    @with_phases(phases=[pre_spec], other_phases=[post_spec])
    @spec_test
    @with_state
    @with_meta_tags(meta_tags)
    def test_after_fork_new_validator_active(spec, phases, state):
        new_validator_index = len(state.validators)

        amount = spec.MIN_ACTIVATION_BALANCE

        deposit_request = prepare_deposit_request(spec, new_validator_index, amount, signed=True)

        # As `prepare_state_and_deposit` changes the state, we need to create the block after calling it.
        deposit_block = build_empty_block_for_next_slot(spec, state)

        deposit_block.body.execution_requests.deposits = [deposit_request]
        deposit_block.body.execution_payload.block_hash = compute_el_block_hash_for_block(
            spec, deposit_block
        )

        _ = state_transition_and_sign_block(spec, state, deposit_block)

        pending_deposit = spec.PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=deposit_block.slot,
        )
        assert state.pending_deposits == [pending_deposit]

        next_epoch(spec, state)
        next_epoch(spec, state)

        state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1

        next_epoch(spec, state)

        assert state.pending_deposits == []

        assert len(state.validators) == new_validator_index + 1

        while (
            state.validators[new_validator_index].activation_eligibility_epoch
            == spec.FAR_FUTURE_EPOCH
        ):
            next_epoch(spec, state)

        while (
            spec.get_current_epoch(state)
            <= state.validators[new_validator_index].activation_eligibility_epoch
        ):
            next_epoch(spec, state)

        state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1

        while state.validators[new_validator_index].activation_epoch == spec.FAR_FUTURE_EPOCH:
            next_epoch(spec, state)

        fork_epoch = state.validators[new_validator_index].activation_epoch
        assert spec.get_current_epoch(state) < fork_epoch - 1

        while spec.get_current_epoch(state) < fork_epoch - 1:
            next_epoch(spec, state)

        new_validator = state.validators[new_validator_index]

        assert not spec.is_active_validator(new_validator, spec.get_current_epoch(state)), (
            f"New Validator should be inactive at epoch {spec.get_current_epoch(state)}"
        )

        spec.process_slots(
            state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
        )
        assert state.slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

        state, _ = yield from do_fork_generate(state, spec, phases[post_spec], fork_epoch)

        new_validator = state.validators[new_validator_index]

        assert spec.is_active_validator(new_validator, spec.get_current_epoch(state)), (
            f"New Validator should be active at epoch {spec.get_current_epoch(state)}"
        )

    return (
        test_after_fork_new_validator_active,
        f"test_after_fork_new_validator_active_from_{pre_spec}_to_{post_spec}",
    )


_template_test_after_fork_new_validator_active_post_electra()
