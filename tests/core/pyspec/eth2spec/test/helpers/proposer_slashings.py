from eth2spec.test.helpers.block_header import sign_block_header
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.state import get_balance


def check_proposer_slashing_effect(spec, pre_state, state, slashed_index):
    slashed_validator = state.validators[slashed_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    proposer_index = spec.get_beacon_proposer_index(state)
    slash_penalty = state.validators[slashed_index].effective_balance // spec.MIN_SLASHING_PENALTY_QUOTIENT
    whistleblower_reward = state.validators[slashed_index].effective_balance // spec.WHISTLEBLOWER_REWARD_QUOTIENT
    if proposer_index != slashed_index:
        # slashed validator lost initial slash penalty
        assert (
            get_balance(state, slashed_index)
            == get_balance(pre_state, slashed_index) - slash_penalty
        )
        # block proposer gained whistleblower reward
        # >= because proposer could have reported multiple
        assert (
            get_balance(state, proposer_index)
            >= get_balance(pre_state, proposer_index) + whistleblower_reward
        )
    else:
        # proposer reported themself so get penalty and reward
        # >= because proposer could have reported multiple
        assert (
            get_balance(state, slashed_index)
            >= get_balance(pre_state, slashed_index) - slash_penalty + whistleblower_reward
        )


def get_valid_proposer_slashing(spec, state, random_root=b'\x99' * 32,
                                slashed_index=None, signed_1=False, signed_2=False):
    if slashed_index is None:
        current_epoch = spec.get_current_epoch(state)
        slashed_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validators[slashed_index].pubkey]
    slot = state.slot

    header_1 = spec.BeaconBlockHeader(
        slot=slot,
        proposer_index=slashed_index,
        parent_root=b'\x33' * 32,
        state_root=b'\x44' * 32,
        body_root=b'\x55' * 32,
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
