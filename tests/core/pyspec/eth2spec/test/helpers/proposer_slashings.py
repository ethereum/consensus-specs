from eth2spec.test.helpers.block_header import sign_block_header
from eth2spec.test.helpers.forks import is_post_altair, is_post_bellatrix, is_post_electra
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.state import get_balance
from eth2spec.test.helpers.sync_committee import (
    compute_committee_indices,
    compute_sync_committee_participant_reward_and_penalty,
)


def get_min_slashing_penalty_quotient(spec):
    if is_post_electra(spec):
        return spec.MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA
    elif is_post_bellatrix(spec):
        return spec.MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX
    elif is_post_altair(spec):
        return spec.MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR
    else:
        return spec.MIN_SLASHING_PENALTY_QUOTIENT


def get_whistleblower_reward_quotient(spec):
    if is_post_electra(spec):
        return spec.WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA
    else:
        return spec.WHISTLEBLOWER_REWARD_QUOTIENT


def check_proposer_slashing_effect(spec, pre_state, state, slashed_index, block=None):
    slashed_validator = state.validators[slashed_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    proposer_index = spec.get_beacon_proposer_index(state)
    slash_penalty = state.validators[
        slashed_index
    ].effective_balance // get_min_slashing_penalty_quotient(spec)
    whistleblower_reward = state.validators[
        slashed_index
    ].effective_balance // get_whistleblower_reward_quotient(spec)

    # Altair introduces sync committee (SC) reward and penalty
    sc_reward_for_slashed = sc_penalty_for_slashed = sc_reward_for_proposer = (
        sc_penalty_for_proposer
    ) = 0
    if is_post_altair(spec) and block is not None:
        committee_indices = compute_committee_indices(state, state.current_sync_committee)
        committee_bits = block.body.sync_aggregate.sync_committee_bits
        sc_reward_for_slashed, sc_penalty_for_slashed = (
            compute_sync_committee_participant_reward_and_penalty(
                spec,
                pre_state,
                slashed_index,
                committee_indices,
                committee_bits,
            )
        )
        sc_reward_for_proposer, sc_penalty_for_proposer = (
            compute_sync_committee_participant_reward_and_penalty(
                spec,
                pre_state,
                proposer_index,
                committee_indices,
                committee_bits,
            )
        )

    if proposer_index != slashed_index:
        # slashed validator lost initial slash penalty
        assert (
            get_balance(state, slashed_index)
            == get_balance(pre_state, slashed_index)
            - slash_penalty
            + sc_reward_for_slashed
            - sc_penalty_for_slashed
        )
        # block proposer gained whistleblower reward
        # >= because proposer could have reported multiple
        assert get_balance(state, proposer_index) >= (
            get_balance(pre_state, proposer_index)
            + whistleblower_reward
            + sc_reward_for_proposer
            - sc_penalty_for_proposer
        )
    else:
        # proposer reported themself so get penalty and reward
        # >= because proposer could have reported multiple
        assert get_balance(state, slashed_index) >= (
            get_balance(pre_state, slashed_index)
            - slash_penalty
            + whistleblower_reward
            + sc_reward_for_slashed
            - sc_penalty_for_slashed
        )


def get_valid_proposer_slashing(
    spec,
    state,
    random_root=b"\x99" * 32,
    slashed_index=None,
    slot=None,
    signed_1=False,
    signed_2=False,
):
    if slashed_index is None:
        current_epoch = spec.get_current_epoch(state)
        slashed_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validators[slashed_index].pubkey]
    if slot is None:
        slot = state.slot

    header_1 = spec.BeaconBlockHeader(
        slot=slot,
        proposer_index=slashed_index,
        parent_root=b"\x33" * 32,
        state_root=b"\x44" * 32,
        body_root=b"\x55" * 32,
    )
    header_2 = header_1.copy()
    header_2.parent_root = random_root

    if signed_1:
        signed_header_1 = sign_block_header(spec, state, header_1, privkey)
    else:
        signed_header_1 = spec.SignedBeaconBlockHeader(message=header_1)
    if signed_2:
        signed_header_2 = sign_block_header(spec, state, header_2, privkey)
    else:
        signed_header_2 = spec.SignedBeaconBlockHeader(message=header_2)

    return spec.ProposerSlashing(
        signed_header_1=signed_header_1,
        signed_header_2=signed_header_2,
    )
