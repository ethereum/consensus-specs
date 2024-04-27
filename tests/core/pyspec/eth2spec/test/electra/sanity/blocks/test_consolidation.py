
from eth2spec.test.context import (
    with_electra_and_later,
    with_presets,
    spec_test,
    single_phase,
    with_custom_state,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    default_activation_threshold,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.helpers.consolidations import (
    sign_consolidation,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
)


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_multiple_consolidations_below_churn(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit
    current_epoch = spec.get_current_epoch(state)

    yield "pre", state

    # Prepare a bunch of consolidations, each of them in a block, based on the current state
    blocks = []
    consolidation_count = 3
    for i in range(consolidation_count):
        source_index = 2 * i
        target_index = 2 * i + 1
        source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
        target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]
        # Set source and target withdrawal credentials to the same eth1 credential
        set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
        set_eth1_withdrawal_credential_with_balance(spec, state, target_index)
        signed_consolidation = sign_consolidation(
            spec,
            state,
            spec.Consolidation(
                epoch=current_epoch,
                source_index=source_index,
                target_index=target_index,
            ),
            source_privkey,
            target_privkey,
        )
        block = build_empty_block_for_next_slot(spec, state)
        block.body.consolidations = [signed_consolidation]
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    yield "blocks", blocks
    yield "post", state

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    assert state.earliest_consolidation_epoch == expected_exit_epoch
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - 3 * spec.MIN_ACTIVATION_BALANCE
    )
    for i in range(consolidation_count):
        assert state.validators[2 * i].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_multiple_consolidations_equal_churn(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit
    current_epoch = spec.get_current_epoch(state)

    yield "pre", state
    # Prepare a bunch of consolidations, each of them in a block, based on the current state
    blocks = []
    consolidation_count = 4
    for i in range(consolidation_count):
        source_index = 2 * i
        target_index = 2 * i + 1
        source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
        target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]
        # Set source and target withdrawal credentials to the same eth1 credential
        set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
        set_eth1_withdrawal_credential_with_balance(spec, state, target_index)
        signed_consolidation = sign_consolidation(
            spec,
            state,
            spec.Consolidation(
                epoch=current_epoch,
                source_index=source_index,
                target_index=target_index,
            ),
            source_privkey,
            target_privkey,
        )
        block = build_empty_block_for_next_slot(spec, state)
        block.body.consolidations = [signed_consolidation]
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    yield "blocks", blocks
    yield "post", state

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    assert state.earliest_consolidation_epoch == expected_exit_epoch
    assert state.consolidation_balance_to_consume == 0
    for i in range(consolidation_count):
        assert state.validators[2 * i].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_multiple_consolidations_above_churn(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit
    current_epoch = spec.get_current_epoch(state)

    # Prepare a bunch of consolidations, each of them in a block, based on the current state
    blocks = []
    consolidation_count = 4
    for i in range(consolidation_count):
        source_index = 2 * i
        target_index = 2 * i + 1
        source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
        target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]
        # Set source and target withdrawal credentials to the same eth1 credential
        set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
        set_eth1_withdrawal_credential_with_balance(spec, state, target_index)
        signed_consolidation = sign_consolidation(
            spec,
            state,
            spec.Consolidation(
                epoch=current_epoch,
                source_index=source_index,
                target_index=target_index,
            ),
            source_privkey,
            target_privkey,
        )
        block = build_empty_block_for_next_slot(spec, state)
        block.body.consolidations = [signed_consolidation]
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    # consolidate an additional validator
    source_index = spec.get_active_validator_indices(state, current_epoch)[-2]
    target_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # This is the interesting part of the test: on a pre-state with full consolidation queue,
    #  when processing an additional consolidation, it results in an exit in a later epoch
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.consolidations = [signed_consolidation]
    signed_block = state_transition_and_sign_block(spec, state, block)
    blocks.append(signed_block)

    yield "blocks", blocks
    yield "post", state

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    assert state.earliest_consolidation_epoch == expected_exit_epoch + 1
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - spec.MIN_ACTIVATION_BALANCE
    )
    assert state.validators[source_index].exit_epoch == expected_exit_epoch + 1
    for i in range(consolidation_count):
        assert state.validators[2 * i].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_multiple_consolidations_equal_twice_churn(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit
    current_epoch = spec.get_current_epoch(state)

    yield "pre", state
    # Prepare a bunch of consolidations, each of them in a block, based on the current state
    blocks = []
    consolidation_count = 8
    for i in range(consolidation_count):
        source_index = 2 * i
        target_index = 2 * i + 1
        source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
        target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]
        # Set source and target withdrawal credentials to the same eth1 credential
        set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
        set_eth1_withdrawal_credential_with_balance(spec, state, target_index)
        signed_consolidation = sign_consolidation(
            spec,
            state,
            spec.Consolidation(
                epoch=current_epoch,
                source_index=source_index,
                target_index=target_index,
            ),
            source_privkey,
            target_privkey,
        )
        block = build_empty_block_for_next_slot(spec, state)
        block.body.consolidations = [signed_consolidation]
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    yield "blocks", blocks
    yield "post", state

    first_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    assert state.consolidation_balance_to_consume == 0
    assert state.earliest_consolidation_epoch == first_exit_epoch + 1
    for i in range(consolidation_count // 2):
        assert state.validators[2 * i].exit_epoch == first_exit_epoch
    for i in range(consolidation_count // 2, consolidation_count):
        assert state.validators[2 * i].exit_epoch == first_exit_epoch + 1
