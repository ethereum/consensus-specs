from eth2spec.test.helpers.block_header import sign_block_header
from eth2spec.test.helpers.keys import pubkey_to_privkey


def get_valid_proposer_slashing(spec, state, signed_1=False, signed_2=False):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    slot = state.slot

    header_1 = spec.BeaconBlockHeader(
        slot=slot,
        parent_root=b'\x33' * 32,
        state_root=b'\x44' * 32,
        body_root=b'\x55' * 32,
    )
    header_2 = header_1.copy()
    header_2.parent_root = b'\x99' * 32

    if signed_1:
        signed_header_1 = sign_block_header(spec, state, header_1, privkey)
    else:
        signed_header_1 = spec.SignedBeaconBlockHeader(message=header_1)
    if signed_2:
        signed_header_2 = sign_block_header(spec, state, header_2, privkey)
    else:
        signed_header_2 = spec.SignedBeaconBlockHeader(message=header_2)

    return spec.ProposerSlashing(
        proposer_index=validator_index,
        signed_header_1=signed_header_1,
        signed_header_2=signed_header_2,
    )
