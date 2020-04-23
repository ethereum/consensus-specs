from eth2spec.test.context import spec_state_test, never_bls, with_all_phases
from eth2spec.test.helpers.block import build_empty_block
from eth2spec.test.helpers.deposits import prepare_state_and_deposit
from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.test.helpers.state import next_epoch
from eth2spec.utils import bls


def run_is_candidate_block(spec, eth1_block, period_start, success):
    result = spec.is_candidate_block(eth1_block, period_start)
    if success:
        assert result
    else:
        assert not result


def get_min_new_period_epochs(spec):
    return int(
        spec.SECONDS_PER_ETH1_BLOCK * spec.ETH1_FOLLOW_DISTANCE * 2  # to seconds
        / spec.SECONDS_PER_SLOT / spec.SLOTS_PER_EPOCH
    )


#
# Becoming a validator
#


@with_all_phases
@spec_state_test
@never_bls
def test_check_if_validator_active(spec, state):
    active_validator_index = len(state.validators) - 1
    assert spec.check_if_validator_active(state, active_validator_index)
    new_validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, new_validator_index, amount, signed=True)
    spec.process_deposit(state, deposit)
    assert not spec.check_if_validator_active(state, new_validator_index)


#
# Validator assignments
#


@with_all_phases
@spec_state_test
@never_bls
def test_get_committee_assignment(spec, state):
    epoch = spec.get_current_epoch(state)
    validator_index = len(state.validators) - 1
    assignment = spec.get_committee_assignment(state, epoch, validator_index)
    committee, committee_index, slot = assignment
    assert spec.compute_epoch_at_slot(slot) == epoch
    assert committee == spec.get_beacon_committee(state, slot, committee_index)
    assert committee_index < spec.get_committee_count_at_slot(state, slot)


@with_all_phases
@spec_state_test
@never_bls
def test_is_proposer(spec, state):
    proposer_index = spec.get_beacon_proposer_index(state)
    assert spec.is_proposer(state, proposer_index)

    proposer_index = proposer_index + 1 % len(state.validators)
    assert not spec.is_proposer(state, proposer_index)


#
# Beacon chain responsibilities
#


# Block proposal


@with_all_phases
@spec_state_test
def test_get_epoch_signature(spec, state):
    block = spec.BeaconBlock()
    privkey = privkeys[0]
    pubkey = pubkeys[0]
    signature = spec.get_epoch_signature(state, block, privkey)
    domain = spec.get_domain(state, spec.DOMAIN_RANDAO, spec.compute_epoch_at_slot(block.slot))
    signing_root = spec.compute_signing_root(spec.compute_epoch_at_slot(block.slot), domain)
    assert bls.Verify(pubkey, signing_root, signature)


@with_all_phases
@spec_state_test
def test_is_candidate_block(spec, state):
    period_start = spec.SECONDS_PER_ETH1_BLOCK * spec.ETH1_FOLLOW_DISTANCE * 2 + 1000
    run_is_candidate_block(
        spec,
        spec.Eth1Block(timestamp=period_start - spec.SECONDS_PER_ETH1_BLOCK * spec.ETH1_FOLLOW_DISTANCE),
        period_start,
        success=True,
    )
    run_is_candidate_block(
        spec,
        spec.Eth1Block(timestamp=period_start - spec.SECONDS_PER_ETH1_BLOCK * spec.ETH1_FOLLOW_DISTANCE + 1),
        period_start,
        success=False,
    )
    run_is_candidate_block(
        spec,
        spec.Eth1Block(timestamp=period_start - spec.SECONDS_PER_ETH1_BLOCK * spec.ETH1_FOLLOW_DISTANCE * 2),
        period_start,
        success=True,
    )
    run_is_candidate_block(
        spec,
        spec.Eth1Block(timestamp=period_start - spec.SECONDS_PER_ETH1_BLOCK * spec.ETH1_FOLLOW_DISTANCE * 2 - 1),
        period_start,
        success=False,
    )


@with_all_phases
@spec_state_test
def test_get_eth1_data_default_vote(spec, state):
    min_new_period_epochs = get_min_new_period_epochs(spec)
    for _ in range(min_new_period_epochs):
        next_epoch(spec, state)

    state.eth1_data_votes = ()
    eth1_chain = []
    eth1_data = spec.get_eth1_vote(state, eth1_chain)
    assert eth1_data == state.eth1_data


@with_all_phases
@spec_state_test
def test_get_eth1_data_consensus_vote(spec, state):
    min_new_period_epochs = get_min_new_period_epochs(spec)
    for _ in range(min_new_period_epochs):
        next_epoch(spec, state)

    period_start = spec.voting_period_start_time(state)
    votes_length = spec.get_current_epoch(state) % spec.EPOCHS_PER_ETH1_VOTING_PERIOD
    state.eth1_data_votes = ()
    eth1_chain = []
    eth1_data_votes = []
    block = spec.Eth1Block(timestamp=period_start - spec.SECONDS_PER_ETH1_BLOCK * spec.ETH1_FOLLOW_DISTANCE)
    for i in range(votes_length):
        eth1_chain.append(block)
        eth1_data_votes.append(spec.get_eth1_data(block))

    state.eth1_data_votes = eth1_data_votes
    eth1_data = spec.get_eth1_vote(state, eth1_chain)
    print(state.eth1_data_votes)
    assert eth1_data.block_hash == block.hash_tree_root()


@with_all_phases
@spec_state_test
def test_compute_new_state_root(spec, state):
    pre_state = state.copy()
    post_state = state.copy()
    block = build_empty_block(spec, state, state.slot + 1)
    state_root = spec.compute_new_state_root(state, block)

    assert state_root != pre_state.hash_tree_root()

    # dumb verification
    spec.process_slots(post_state, block.slot)
    spec.process_block(post_state, block)
    assert state_root == post_state.hash_tree_root()


@with_all_phases
@spec_state_test
def test_get_block_signature(spec, state):
    privkey = privkeys[0]
    pubkey = pubkeys[0]
    block = build_empty_block(spec, state)
    signature = spec.get_block_signature(state, block, privkey)
    domain = spec.get_domain(state, spec.DOMAIN_BEACON_PROPOSER, spec.compute_epoch_at_slot(block.slot))
    signing_root = spec.compute_signing_root(block, domain)
    assert bls.Verify(pubkey, signing_root, signature)
