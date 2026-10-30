from eth_consensus_specs.test.context import spec_state_test, with_eip8450_and_later
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.eip8450.pq_keys import is_registered, register_pq_keys
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


@with_eip8450_and_later
@spec_state_test
def test_new_validators_have_unset_pq_keys(spec, state):
    # Registered keys of existing validators are left untouched
    registered_keys = register_pq_keys(spec, state, 0)

    pre_validator_count = len(state.validators)
    new_validator_count = 2
    for offset in range(new_validator_count):
        state.pending_deposits.append(
            prepare_pending_deposit(
                spec,
                pre_validator_count + offset,
                spec.MIN_ACTIVATION_BALANCE,
                signed=True,
            )
        )

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert len(state.validators) == pre_validator_count + new_validator_count
    assert len(state.post_quantum_key_material) == len(state.validators)
    assert len(state.post_quantum_key_change_epochs) == len(state.validators)
    for index in range(pre_validator_count, len(state.validators)):
        assert not is_registered(spec, state, index)
        assert state.post_quantum_key_material[index] == spec.PQKeyMaterial()
        assert state.post_quantum_key_change_epochs[index] == spec.FAR_FUTURE_EPOCH
    assert state.post_quantum_key_material[0] == registered_keys
