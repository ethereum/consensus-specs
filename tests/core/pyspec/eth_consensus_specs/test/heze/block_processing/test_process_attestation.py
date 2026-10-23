from eth_consensus_specs.test.context import (
    always_bls,
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    run_attestation_processing,
)
from eth_consensus_specs.test.helpers.block import apply_empty_block
from eth_consensus_specs.test.helpers.constants import HEZE
from eth_consensus_specs.test.helpers.heze.slot_duration import expected_base_reward


def _run_proposer_reward_test(spec, state, epoch, previous_epoch: bool = False):
    attestation_slot = spec.compute_start_slot_at_epoch(epoch)
    if previous_epoch:
        attestation_slot += spec.SLOTS_PER_EPOCH - 1

    apply_empty_block(spec, state, attestation_slot)

    attester = spec.get_beacon_committee(state, attestation_slot, 0)[0]
    attestation = get_valid_attestation(
        spec,
        state,
        index=0,
        filter_participant_set=lambda _: {attester},
        signed=True,
    )
    spec.process_slots(state, attestation_slot + 1)

    proposer = spec.get_beacon_proposer_index(state)
    balances = list(state.balances)
    duration_ms = (
        spec.config.SLOT_DURATION_MS
        if epoch < spec.config.HEZE_FORK_EPOCH
        else spec.config.SLOT_DURATION_MS_HEZE
    )
    base_reward = expected_base_reward(spec, state, attester, duration_ms)
    weight = spec.TIMELY_SOURCE_WEIGHT + spec.TIMELY_TARGET_WEIGHT + spec.TIMELY_HEAD_WEIGHT
    proposer_reward_numerator = base_reward * weight
    proposer_reward_denominator = (
        (spec.WEIGHT_DENOMINATOR - spec.PROPOSER_WEIGHT)
        * spec.WEIGHT_DENOMINATOR
        // spec.PROPOSER_WEIGHT
    )
    balances[proposer] += proposer_reward_numerator // proposer_reward_denominator

    yield from run_attestation_processing(spec, state, attestation)
    assert list(state.balances) == balances


@with_phases([HEZE])
@spec_configured_state_test({"HEZE_FORK_EPOCH": 2}, activate_at_genesis=True)
@always_bls
def test_proposer_reward_previous_epoch_at_heze_fork(spec, state):
    yield from _run_proposer_reward_test(
        spec, state, spec.config.HEZE_FORK_EPOCH - 1, previous_epoch=True
    )


@with_phases([HEZE])
@spec_configured_state_test({"HEZE_FORK_EPOCH": 2}, activate_at_genesis=True)
@always_bls
def test_proposer_reward_current_epoch_at_heze_fork(spec, state):
    yield from _run_proposer_reward_test(spec, state, spec.config.HEZE_FORK_EPOCH)
