# Access constants from spec pkg reference.
import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import get_current_epoch, get_active_validator_indices, Transfer, ZERO_HASH, get_domain
from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.test.helpers.state import get_balance
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.minimal_ssz import signing_root


def get_valid_transfer(state, slot=None, sender_index=None, amount=None, fee=None):
    if slot is None:
        slot = state.slot
    current_epoch = get_current_epoch(state)
    if sender_index is None:
        sender_index = get_active_validator_indices(state, current_epoch)[-1]
    recipient_index = get_active_validator_indices(state, current_epoch)[0]
    transfer_pubkey = pubkeys[-1]
    transfer_privkey = privkeys[-1]

    if fee is None:
        fee = get_balance(state, sender_index) // 32
    if amount is None:
        amount = get_balance(state, sender_index) - fee

    transfer = Transfer(
        sender=sender_index,
        recipient=recipient_index,
        amount=amount,
        fee=fee,
        slot=slot,
        pubkey=transfer_pubkey,
        signature=ZERO_HASH,
    )
    transfer.signature = bls_sign(
        message_hash=signing_root(transfer),
        privkey=transfer_privkey,
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_TRANSFER,
            message_epoch=get_current_epoch(state),
        )
    )

    # ensure withdrawal_credentials reproducable
    state.validator_registry[transfer.sender].withdrawal_credentials = (
            spec.BLS_WITHDRAWAL_PREFIX_BYTE + spec.hash(transfer.pubkey)[1:]
    )

    return transfer
