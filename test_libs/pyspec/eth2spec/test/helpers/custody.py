from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import bls_sign


def get_valid_early_derived_secret_reveal(spec, state, epoch=None):
    current_epoch = spec.get_current_epoch(state)
    revealed_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    masker_index = spec.get_active_validator_indices(state, current_epoch)[0]

    if epoch is None:
        epoch = current_epoch + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING

    reveal = bls_sign(
        message_hash=spec.hash_tree_root(spec.Epoch(epoch)),
        privkey=privkeys[revealed_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )
    mask = bls_sign(
        message_hash=spec.hash_tree_root(spec.Epoch(epoch)),
        privkey=privkeys[masker_index],
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_RANDAO,
            message_epoch=epoch,
        ),
    )

    return spec.EarlyDerivedSecretReveal(
        revealed_index=revealed_index,
        epoch=epoch,
        reveal=reveal,
        masker_index=masker_index,
        mask=mask,
    )
