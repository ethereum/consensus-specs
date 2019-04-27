from py_ecc import bls

import eth2spec.phase1.spec as spec
from eth2spec.phase0.spec import (
    # constants
    ZERO_HASH,
    CUSTODY_PERIOD_TO_RANDAO_PADDING,
    # SSZ
    RandaoKeyReveal,
    # functions
    get_active_validator_indices,
    get_current_epoch,
    get_domain,
    hash_tree_root,
)

def get_valid_randao_key_reveal(state, epoch=None):
    current_epoch = get_current_epoch(state)
    revealed_index = get_active_validator_indices(state, current_epoch)[-1]
    masker_index = get_active_validator_indices(state, current_epoch)[0]

    if epoch is None:
        epoch = current_epoch + CUSTODY_PERIOD_TO_RANDAO_PADDING

    reveal = bls.sign(
        message_hash=hash_tree_root(epoch),
        privkey=pubkey_to_privkey[state.validator_registry[revealed_index].pubkey],
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )
    mask = bls.sign(
        message_hash=hash_tree_root(epoch),
        privkey=pubkey_to_privkey[state.validator_registry[masker_index].pubkey],
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )

    return RandaoKeyReveal(
        revealed_index=revealed_index,
        epoch=epoch,
        reveal=reveal,
        masker_index=masker_index,
        mask=mask,
    )
