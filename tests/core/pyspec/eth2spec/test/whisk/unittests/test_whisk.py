from eth2spec.test.context import (
    with_phases,
    spec_state_test,
)
from eth2spec.test.helpers.constants import WHISK
from eth2spec.test.helpers.state import next_epoch
from tests.core.pyspec.eth2spec.test.helpers.block import build_empty_block
from tests.core.pyspec.eth2spec.test.helpers.deposits import mock_deposit, prepare_state_and_deposit, run_deposit_processing
from eth2spec.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64,
    Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist)
from tests.core.pyspec.eth2spec.test.helpers.state import state_transition_and_sign_block

@with_phases([WHISK])
@spec_state_test
def test_whisk_process_epoch(spec, state):
    k = spec.get_unique_whisk_k(state, spec.ValidatorIndex(len(state.validators)))

    
    # fresh deposit = next validator index = validator appended to registry
    validator_index = spec.ValidatorIndex(len(state.validators))
    # effective balance will be 1 EFFECTIVE_BALANCE_INCREMENT smaller because of this small decrement.
    amount = spec.MAX_EFFECTIVE_BALANCE - 1
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)
    spec.process_deposit(state, deposit)
    print("spec validators", state.validators[validator_index])

    spec.process_slots(state, state.slot + 1)

    block = build_empty_block(spec, state, slot=state.slot)
    spec.process_block_header(state, block)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)
    print("signed block", signed_block)


    assert 1 == 0
