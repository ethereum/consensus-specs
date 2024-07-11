from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.context import (
    spec_state_test,
    with_phases,
    ELECTRA,
)
from eth2spec.test.helpers.deposits import (
    build_deposit_data,
    deposit_from_context,
    prepare_deposit_request,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block
)


def run_deposit_transition_block(spec, state, block, top_up_keys=[], valid=True):
    """
    Run ``process_block``, yielding:
      - pre-state ('pre')
      - block ('block')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield 'pre', state

    signed_block = state_transition_and_sign_block(spec, state, block, not valid)

    yield 'blocks', [signed_block]
    yield 'post', state if valid else None

    # Check that deposits are applied
    if valid:
        expected_pubkeys = [d.data.pubkey for d in block.body.deposits]
        deposit_requests = block.body.execution_payload.deposit_requests
        expected_pubkeys = expected_pubkeys + [d.pubkey for d in deposit_requests if (d.pubkey not in top_up_keys)]
        actual_pubkeys = [v.pubkey for v in state.validators[len(state.validators) - len(expected_pubkeys):]]

        assert actual_pubkeys == expected_pubkeys


def prepare_state_and_block(spec,
                            state,
                            deposit_cnt,
                            deposit_request_cnt,
                            first_deposit_request_index=0,
                            deposit_requests_start_index=None,
                            eth1_data_deposit_count=None):
    deposits = []
    deposit_requests = []
    keypair_index = len(state.validators)

    # Prepare deposits
    deposit_data_list = []
    for index in range(deposit_cnt):
        deposit_data = build_deposit_data(spec,
                                          pubkeys[keypair_index],
                                          privkeys[keypair_index],
                                          # use max effective balance
                                          spec.MAX_EFFECTIVE_BALANCE,
                                          # insecurely use pubkey as withdrawal key
                                          spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkeys[keypair_index])[1:],
                                          signed=True)
        deposit_data_list.append(deposit_data)
        keypair_index += 1

    deposit_root = None
    for index in range(deposit_cnt):
        deposit, deposit_root, _ = deposit_from_context(spec, deposit_data_list, index)
        deposits.append(deposit)

    if deposit_root:
        state.eth1_deposit_index = 0
        if not eth1_data_deposit_count:
            eth1_data_deposit_count = deposit_cnt
        state.eth1_data = spec.Eth1Data(deposit_root=deposit_root,
                                        deposit_count=eth1_data_deposit_count,
                                        block_hash=state.eth1_data.block_hash)

    # Prepare deposit requests
    for offset in range(deposit_request_cnt):
        deposit_request = prepare_deposit_request(spec,
                                                  keypair_index,
                                                  # use max effective balance
                                                  spec.MAX_EFFECTIVE_BALANCE,
                                                  first_deposit_request_index + offset,
                                                  signed=True)
        deposit_requests.append(deposit_request)
        keypair_index += 1

    # Set start index if defined
    if deposit_requests_start_index:
        state.deposit_requests_start_index = deposit_requests_start_index

    block = build_empty_block_for_next_slot(spec, state)

    # Assign deposits and deposit requests
    block.body.deposits = deposits
    block.body.execution_payload.deposit_requests = deposit_requests
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload, state)

    return state, block


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__start_index_is_set(spec, state):
    # 0 deposits, 2 deposit requests, unset deposit_requests_start_index
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=0,
                                           deposit_request_cnt=2,
                                           first_deposit_request_index=state.eth1_data.deposit_count + 11)

    yield from run_deposit_transition_block(spec, state, block)

    # deposit_requests_start_index must be set to the index of the first request
    assert state.deposit_requests_start_index == block.body.execution_payload.deposit_requests[0].index


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__process_eth1_deposits(spec, state):
    # 3 deposits, 1 deposit request, state.eth1_data.deposit_count < state.deposit_requests_start_index
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=3,
                                           deposit_request_cnt=1,
                                           first_deposit_request_index=11,
                                           deposit_requests_start_index=7)

    yield from run_deposit_transition_block(spec, state, block)


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__process_max_eth1_deposits(spec, state):
    # spec.MAX_DEPOSITS deposits, 1 deposit request, state.eth1_data.deposit_count > state.deposit_requests_start_index
    # state.deposit_requests_start_index == spec.MAX_DEPOSITS
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=spec.MAX_DEPOSITS,
                                           deposit_request_cnt=1,
                                           first_deposit_request_index=spec.MAX_DEPOSITS + 1,
                                           deposit_requests_start_index=spec.MAX_DEPOSITS,
                                           eth1_data_deposit_count=23)

    yield from run_deposit_transition_block(spec, state, block)


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__process_eth1_deposits_up_to_start_index(spec, state):
    # 3 deposits, 1 deposit request, state.eth1_data.deposit_count == state.deposit_requests_start_index
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=3,
                                           deposit_request_cnt=1,
                                           first_deposit_request_index=7,
                                           deposit_requests_start_index=3)

    yield from run_deposit_transition_block(spec, state, block)


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__invalid_not_enough_eth1_deposits(spec, state):
    # 3 deposits, 1 deposit request, state.eth1_data.deposit_count < state.deposit_requests_start_index
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=3,
                                           deposit_request_cnt=1,
                                           first_deposit_request_index=29,
                                           deposit_requests_start_index=23,
                                           eth1_data_deposit_count=17)

    yield from run_deposit_transition_block(spec, state, block, valid=False)


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__invalid_too_many_eth1_deposits(spec, state):
    # 3 deposits, 1 deposit request, state.eth1_data.deposit_count < state.eth1_data_index
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=3,
                                           deposit_request_cnt=1,
                                           first_deposit_request_index=11,
                                           deposit_requests_start_index=7,
                                           eth1_data_deposit_count=2)

    yield from run_deposit_transition_block(spec, state, block, valid=False)


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__invalid_eth1_deposits_overlap_in_protocol_deposits(spec, state):
    # spec.MAX_DEPOSITS deposits, 1 deposit request, state.eth1_data.deposit_count > state.deposit_requests_start_index
    # state.deposit_requests_start_index == spec.MAX_DEPOSITS - 1
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=spec.MAX_DEPOSITS,
                                           deposit_request_cnt=1,
                                           first_deposit_request_index=spec.MAX_DEPOSITS,
                                           deposit_requests_start_index=spec.MAX_DEPOSITS - 1,
                                           eth1_data_deposit_count=23)

    yield from run_deposit_transition_block(spec, state, block, valid=False)


@with_phases([ELECTRA])
@spec_state_test
def test_deposit_transition__deposit_and_top_up_same_block(spec, state):
    # 1 deposit, 1 deposit request that top ups deposited validator
    state, block = prepare_state_and_block(spec, state,
                                           deposit_cnt=1,
                                           deposit_request_cnt=1,
                                           first_deposit_request_index=11,
                                           deposit_requests_start_index=7)

    # Artificially assign deposit's pubkey to a deposit request of the same block
    top_up_keys = [block.body.deposits[0].data.pubkey]
    block.body.execution_payload.deposit_requests[0].pubkey = top_up_keys[0]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload, state)

    pre_pending_deposits = len(state.pending_balance_deposits)

    yield from run_deposit_transition_block(spec, state, block, top_up_keys=top_up_keys)

    # Check the top up
    assert len(state.pending_balance_deposits) == pre_pending_deposits + 2
    assert state.pending_balance_deposits[pre_pending_deposits].amount == block.body.deposits[0].data.amount
    amount_from_deposit = block.body.execution_payload.deposit_requests[0].amount
    assert state.pending_balance_deposits[pre_pending_deposits + 1].amount == amount_from_deposit
