from py_ecc import bls

import eth2spec.phase1.spec as spec
from eth2spec.phase1.spec import (
    # constants
    ZERO_HASH,
    CUSTODY_PERIOD_TO_RANDAO_PADDING,
    # SSZ
    EarlyDerivedSecretReveal,
    # functions
    get_active_validator_indices,
    get_current_epoch,
    get_domain,
    hash_tree_root,
)

from tests.phase0.helpers import (
    advance_slot,
    get_balance,
    build_deposit_data,
    build_empty_block_for_next_slot,
    fill_aggregate_attestation,
    get_state_root,
    get_valid_attestation,
    get_valid_attester_slashing,
    get_valid_proposer_slashing,
    next_slot,
    privkeys,
    pubkeys,
)

def get_valid_early_derived_secret_reveal(state, epoch=None):
    current_epoch = get_current_epoch(state)
    revealed_index = get_active_validator_indices(state, current_epoch)[-1]
    masker_index = get_active_validator_indices(state, current_epoch)[0]

    if epoch is None:
        epoch = current_epoch + CUSTODY_PERIOD_TO_RANDAO_PADDING

    reveal = bls.sign(
        message_hash=hash_tree_root(epoch),
        privkey=privkeys[revealed_index],
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )
    mask = bls.sign(
        message_hash=hash_tree_root(epoch),
        privkey=privkeys[masker_index],
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )

    return EarlyDerivedSecretReveal(
        revealed_index=revealed_index,
        epoch=epoch,
        reveal=reveal,
        masker_index=masker_index,
        mask=mask,
    )
