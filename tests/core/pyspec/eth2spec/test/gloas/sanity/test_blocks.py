from random import Random

from eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.helpers.attestations import get_max_attestations
from eth2spec.test.helpers.attester_slashings import (
    get_max_attester_slashings,
    get_valid_attester_slashing_by_indices,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth2spec.test.helpers.deposits import build_deposit_data, deposit_from_context
from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.test.helpers.multi_operations import (
    get_random_attestations,
)
from eth2spec.test.helpers.proposer_slashings import (
    get_valid_proposer_slashings,
)
from eth2spec.test.helpers.state import next_epoch, next_slots, state_transition_and_sign_block
from eth2spec.test.helpers.voluntary_exits import prepare_signed_exits


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_proposer_slashings(spec, state):
    num_slashings = spec.MAX_PROPOSER_SLASHINGS + 1
    proposer_slashings = get_valid_proposer_slashings(spec, state, num_slashings)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings = proposer_slashings
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_attester_slashings(spec, state):
    num_slashings = get_max_attester_slashings(spec) + 1
    full_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[:8]
    per_slashing_length = len(full_indices) // num_slashings
    attester_slashings = [
        get_valid_attester_slashing_by_indices(
            spec,
            state,
            full_indices[i * per_slashing_length : (i + 1) * per_slashing_length],
            signed_1=True,
            signed_2=True,
        )
        for i in range(num_slashings)
    ]

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings = attester_slashings
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_attestations(spec, state):
    rng = Random(2000)

    next_epoch(spec, state)
    num_attestations = get_max_attestations(spec) + 1
    attestations = get_random_attestations(spec, state, rng, num_attestations)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.attestations = attestations
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_deposits(spec, state):
    num_deposits = spec.MAX_DEPOSITS + 1
    validator_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE

    deposit_data_list = [spec.DepositData() for _ in range(state.eth1_deposit_index)]
    for _ in range(num_deposits):
        deposit_data = build_deposit_data(
            spec,
            pubkeys[validator_index],
            privkeys[validator_index],
            amount,
            withdrawal_credentials=b"\x00" * 32,
            signed=True,
        )
        deposit_data_list.append(deposit_data)

    deposits = []
    deposit_root = None
    for i in range(state.eth1_deposit_index, state.eth1_deposit_index + num_deposits):
        deposit, deposit_root, _ = deposit_from_context(spec, deposit_data_list, i)
        deposits.append(deposit)

    state.eth1_data.deposit_root = deposit_root
    state.eth1_data.deposit_count = len(deposit_data_list)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits = deposits
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_voluntary_exits(spec, state):
    next_slots(spec, state, spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH)
    num_exits = spec.MAX_VOLUNTARY_EXITS + 1
    full_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[
        :num_exits
    ]
    signed_exits = prepare_signed_exits(spec, state, full_indices)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.voluntary_exits = signed_exits
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_too_many_bls_to_execution_changes(spec, state):
    num_address_changes = spec.MAX_BLS_TO_EXECUTION_CHANGES + 1
    signed_address_changes = [
        get_signed_address_change(spec, state, validator_index=i)
        for i in range(num_address_changes)
    ]

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.bls_to_execution_changes = signed_address_changes
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None
