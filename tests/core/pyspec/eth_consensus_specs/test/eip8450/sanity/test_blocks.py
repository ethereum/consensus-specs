from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8450_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.eip8450.pq_keys import (
    activate_builders,
    builder_registry_index,
    get_pq_key_material,
    get_signed_pq_key_registration,
    get_xmss_secret_key,
    is_registered,
)
from eth_consensus_specs.test.helpers.proposer_slashings import get_valid_proposer_slashing
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block
from eth_consensus_specs.test.helpers.voluntary_exits import prepare_signed_exits
from eth_consensus_specs.test.helpers.withdrawals import (
    prepare_withdrawal_request,
    set_compounding_withdrawal_credential,
    set_eth1_withdrawal_credential_with_balance,
    set_parent_block_full,
)


def run_block_with_registrations(spec, state, block, valid=True):
    yield "pre", state
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=not valid)
    yield "blocks", [signed_block]
    yield "post", state if valid else None


def get_non_proposer_indices(spec, state, count):
    """
    Return ``count`` active validator indices that do not propose the next block.
    """
    proposer_index = build_empty_block_for_next_slot(spec, state).proposer_index
    indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    return [index for index in indices if index != proposer_index][:count]


def assert_exit_initiated_by(spec, state, validator_index, apply_cause):
    """
    Check, on a copy of ``state``, that ``apply_cause`` initiates the exit of the
    validator, so that the test exercises the ordering of operations.
    """
    copy = state.copy()
    assert copy.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    apply_cause(copy)
    assert copy.validators[validator_index].exit_epoch != spec.FAR_FUTURE_EPOCH


@with_eip8450_and_later
@spec_state_test
def test_pq_key_registration(spec, state):
    validator_index = get_non_proposer_indices(spec, state, 1)[0]
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block)

    assert (
        state.post_quantum_key_material[validator_index] == signed_registration.message.key_material
    )
    assert state.post_quantum_key_change_epochs[validator_index] == spec.get_current_epoch(state)


@with_eip8450_and_later
@spec_state_test
def test_max_pq_key_registrations(spec, state):
    indices = get_non_proposer_indices(spec, state, spec.MAX_PQ_KEY_REGISTRATIONS)
    registrations = [get_signed_pq_key_registration(spec, state, index=index) for index in indices]

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=registrations)
    yield from run_block_with_registrations(spec, state, block)

    for registration in registrations:
        index = registration.message.index
        assert state.post_quantum_key_material[index] == registration.message.key_material


@with_eip8450_and_later
@spec_state_test
def test_invalid_too_many_pq_key_registrations(spec, state):
    # Each registration is valid on its own, so only the count rejects the block
    indices = get_non_proposer_indices(spec, state, spec.MAX_PQ_KEY_REGISTRATIONS + 1)
    registrations = [get_signed_pq_key_registration(spec, state, index=index) for index in indices]

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=registrations)
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_duplicate_registration_in_block(spec, state):
    # The first registration moves the stored epoch, so the second does not apply
    validator_index = get_non_proposer_indices(spec, state, 1)[0]
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(
        data=[signed_registration, signed_registration]
    )
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_two_registrations_for_same_index_in_block(spec, state):
    # Two different, individually valid registrations for one index: the first
    # moves the stored epoch, so the second no longer names it
    validator_index = get_non_proposer_indices(spec, state, 1)[0]
    first = get_signed_pq_key_registration(spec, state, index=validator_index, generation=0)
    second = get_signed_pq_key_registration(spec, state, index=validator_index, generation=1)
    assert first != second

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[first, second])
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_same_key_for_two_validators_in_block(spec, state):
    owner_index, other_index = get_non_proposer_indices(spec, state, 2)
    owner_registration = get_signed_pq_key_registration(spec, state, index=owner_index)

    # The second validator holds the same leanXMSS key, with its own valid proof
    key_material = get_pq_key_material(spec, other_index)
    key_material.xmss_public_key = owner_registration.message.key_material.xmss_public_key
    other_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=other_index,
        key_material=key_material,
        xmss_secret_key=get_xmss_secret_key(owner_index),
    )

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(
        data=[owner_registration, other_registration]
    )
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_registration_after_voluntary_exit_in_block(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs so the validator can exit
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    validator_index = get_non_proposer_indices(spec, state, 1)[0]

    signed_exits = prepare_signed_exits(spec, state, [validator_index])
    assert_exit_initiated_by(
        spec,
        state,
        validator_index,
        lambda copy: spec.process_voluntary_exit(copy, signed_exits[0]),
    )
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.voluntary_exits = spec.VoluntaryExits(data=signed_exits)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_registration_after_proposer_slashing_in_block(spec, state):
    validator_index = get_non_proposer_indices(spec, state, 1)[0]

    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slashed_index=validator_index, signed_1=True, signed_2=True
    )
    assert_exit_initiated_by(
        spec,
        state,
        validator_index,
        lambda copy: spec.process_proposer_slashing(copy, proposer_slashing),
    )
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings = spec.ProposerSlashings(data=[proposer_slashing])
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_registration_after_attester_slashing_in_block(spec, state):
    validator_index = get_non_proposer_indices(spec, state, 1)[0]

    attester_slashing = get_valid_attester_slashing_by_indices(
        spec, state, [validator_index], signed_1=True, signed_2=True
    )
    assert_exit_initiated_by(
        spec,
        state,
        validator_index,
        lambda copy: spec.process_attester_slashing(copy, attester_slashing),
    )
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings = spec.AttesterSlashings(data=[attester_slashing])
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_registration_after_parent_withdrawal_request(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs so the validator can exit
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    validator_index = get_non_proposer_indices(spec, state, 1)[0]

    # The parent block is full, with a bid committing to a full-exit request
    set_parent_block_full(spec, state)
    withdrawal_request = prepare_withdrawal_request(spec, state, validator_index)
    requests = spec.ExecutionRequests(withdrawals=spec.WithdrawalRequests.of(withdrawal_request))
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)
    assert_exit_initiated_by(
        spec,
        state,
        validator_index,
        lambda copy: spec.process_withdrawal_request(copy, withdrawal_request),
    )
    signed_registration = get_signed_pq_key_registration(spec, state, index=validator_index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@spec_state_test
def test_invalid_registration_after_parent_consolidation_request(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs so the validator can consolidate
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    source_index, target_index = get_non_proposer_indices(spec, state, 2)

    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index, address=source_address)
    set_compounding_withdrawal_credential(spec, state, target_index)
    state.consolidation_balance_to_consume = spec.get_consolidation_churn_limit(state)

    # The parent block is full, with a bid committing to the consolidation
    set_parent_block_full(spec, state)
    consolidation_request = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    requests = spec.ExecutionRequests(
        consolidations=spec.ConsolidationRequests.of(consolidation_request)
    )
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)
    assert_exit_initiated_by(
        spec,
        state,
        source_index,
        lambda copy: spec.process_consolidation_request(copy, consolidation_request),
    )
    signed_registration = get_signed_pq_key_registration(spec, state, index=source_index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_builder_pq_key_registration(spec, state):
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    signed_registration = get_signed_pq_key_registration(spec, state, index=index)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block)

    assert state.builder_post_quantum_key_material[0] == signed_registration.message.key_material
    assert state.builder_post_quantum_key_change_epochs[0] == spec.get_current_epoch(state)


@with_eip8450_and_later
@spec_state_test
def test_validator_and_builder_pq_key_registrations(spec, state):
    activate_builders(spec, state)
    validator_index = get_non_proposer_indices(spec, state, 1)[0]
    registrations = [
        get_signed_pq_key_registration(spec, state, index=validator_index),
        get_signed_pq_key_registration(spec, state, index=builder_registry_index(spec, 0)),
    ]

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=registrations)
    yield from run_block_with_registrations(spec, state, block)

    assert is_registered(spec, state, validator_index)
    assert is_registered(spec, state, builder_registry_index(spec, 0))


@with_eip8450_and_later
@spec_state_test
def test_invalid_same_key_for_validator_and_builder_in_block(spec, state):
    activate_builders(spec, state)
    validator_index = get_non_proposer_indices(spec, state, 1)[0]
    validator_registration = get_signed_pq_key_registration(spec, state, index=validator_index)

    # The builder holds the same leanXMSS key, with its own valid proof
    key_material = spec.PQKeyMaterial(
        xmss_public_key=validator_registration.message.key_material.xmss_public_key
    )
    builder_registration = get_signed_pq_key_registration(
        spec,
        state,
        index=builder_registry_index(spec, 0),
        key_material=key_material,
        xmss_secret_key=get_xmss_secret_key(validator_index),
    )

    block = build_empty_block_for_next_slot(spec, state)
    block.body.pq_key_registrations = spec.PQKeyRegistrations(
        data=[validator_registration, builder_registration]
    )
    yield from run_block_with_registrations(spec, state, block, valid=False)


@with_eip8450_and_later
@spec_state_test
def test_invalid_registration_after_parent_builder_exit_request(spec, state):
    activate_builders(spec, state)
    builder_index = 0
    builder = state.builders[builder_index]
    assert spec.get_pending_balance_to_withdraw_for_builder(state, builder_index) == 0

    # The parent block is full, with a bid committing to the builder's exit
    set_parent_block_full(spec, state)
    exit_request = spec.BuilderExitRequest(
        source_address=builder.execution_address,
        pubkey=builder.pubkey,
    )
    requests = spec.ExecutionRequests(builder_exits=spec.BuilderExitRequests.of(exit_request))
    state.latest_execution_payload_bid.execution_requests_root = spec.hash_tree_root(requests)
    copy = state.copy()
    spec.process_builder_exit_request(copy, exit_request)
    assert not spec.is_active_builder(copy, builder_index)
    signed_registration = get_signed_pq_key_registration(
        spec, state, index=builder_registry_index(spec, builder_index)
    )

    block = build_empty_block_for_next_slot(spec, state)
    block.body.parent_execution_requests = requests
    block.body.pq_key_registrations = spec.PQKeyRegistrations(data=[signed_registration])
    yield from run_block_with_registrations(spec, state, block, valid=False)
