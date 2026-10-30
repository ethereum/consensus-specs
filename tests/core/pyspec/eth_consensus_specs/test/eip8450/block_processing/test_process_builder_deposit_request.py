from eth_consensus_specs.test.context import spec_state_test, with_eip8450_and_later
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    prepare_process_builder_deposit_request,
    run_builder_deposit_request_processing,
)
from eth_consensus_specs.test.helpers.eip8450.pq_keys import (
    activate_builders,
    builder_registry_index,
    is_registered,
    register_pq_keys,
)


@with_eip8450_and_later
@spec_state_test
def test_new_builder_has_unset_pq_keys(spec, state):
    pre_builder_count = len(state.builders)
    request = prepare_process_builder_deposit_request(spec, state, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert len(state.builders) == pre_builder_count + 1
    assert len(state.builder_post_quantum_key_material) == len(state.builders)
    assert len(state.builder_post_quantum_key_change_epochs) == len(state.builders)
    builder = state.builders[pre_builder_count]
    assert builder.pubkey == request.pubkey
    assert state.builder_post_quantum_key_material[pre_builder_count] == spec.PQKeyMaterial()
    assert state.builder_post_quantum_key_change_epochs[pre_builder_count] == builder.deposit_epoch
    assert not is_registered(spec, state, builder_registry_index(spec, pre_builder_count))


@with_eip8450_and_later
@spec_state_test
def test_reused_builder_index_resets_pq_keys(spec, state):
    # The earlier builder registered keys, then exited and withdrew
    activate_builders(spec, state)
    index = builder_registry_index(spec, 0)
    register_pq_keys(spec, state, index)
    pre_builder_count = len(state.builders)
    request = prepare_process_builder_deposit_request(
        spec,
        state,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch", "balance": 0}},
        signed=True,
    )

    yield from run_builder_deposit_request_processing(spec, state, request)

    # The new builder takes the index with a fresh entry at its deposit epoch
    assert len(state.builders) == pre_builder_count
    assert state.builders[0].pubkey == request.pubkey
    assert state.builders[0].deposit_epoch == spec.get_current_epoch(state)
    assert state.builder_post_quantum_key_material[0] == spec.PQKeyMaterial()
    assert state.builder_post_quantum_key_change_epochs[0] == state.builders[0].deposit_epoch
    assert not is_registered(spec, state, index)
