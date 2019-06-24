from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import bls_sign, bls_aggregate_signatures


def get_valid_early_derived_secret_reveal(spec, state, epoch=None):
    current_epoch = spec.get_current_epoch(state)
    revealed_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    masker_index = spec.get_active_validator_indices(state, current_epoch)[0]

    if epoch is None:
        epoch = current_epoch + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING

    # Generate the secret that is being revealed
    reveal = bls_sign(
        message_hash=spec.hash_tree_root(epoch),
        privkey=privkeys[revealed_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )
    # Generate the mask (any random 32 bytes will do)
    mask = hash(reveal)
    # Generate masker's signature on the mask
    masker_signature = bls_sign(
        message_hash=mask,
        privkey=privkeys[masker_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )
    masked_reveal = bls_aggregate_signatures([reveal, masker_signature])

    return spec.EarlyDerivedSecretReveal(
        revealed_index=revealed_index,
        epoch=epoch,
        reveal=masked_reveal,
        masker_index=masker_index,
        mask=mask,
    )
