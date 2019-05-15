from copy import deepcopy

from eth2spec.phase0.spec import get_current_epoch, get_active_validator_indices, BeaconBlockHeader, ZERO_HASH, ProposerSlashing
from eth2spec.test.helpers.block_header import sign_block_header
from eth2spec.test.helpers.keys import pubkey_to_privkey


def get_valid_proposer_slashing(state):
    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]
    slot = state.slot

    header_1 = BeaconBlockHeader(
        slot=slot,
        previous_block_root=ZERO_HASH,
        state_root=ZERO_HASH,
        block_body_root=ZERO_HASH,
    )
    header_2 = deepcopy(header_1)
    header_2.previous_block_root = b'\x02' * 32
    header_2.slot = slot + 1

    sign_block_header(state, header_1, privkey)
    sign_block_header(state, header_2, privkey)

    return ProposerSlashing(
        proposer_index=validator_index,
        header_1=header_1,
        header_2=header_2,
    )
