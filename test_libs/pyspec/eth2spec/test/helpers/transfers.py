from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.test.helpers.state import get_balance
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.ssz.ssz_impl import signing_root


def get_valid_transfer(spec, state, slot=None, sender_index=None, amount=None, fee=None, signed=False):
    if slot is None:
        slot = state.slot
    current_epoch = spec.get_current_epoch(state)
    if sender_index is None:
        sender_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    recipient_index = spec.get_active_validator_indices(state, current_epoch)[0]
    transfer_pubkey = pubkeys[-1]
    transfer_privkey = privkeys[-1]

    if fee is None:
        fee = get_balance(state, sender_index) // 32
    if amount is None:
        amount = get_balance(state, sender_index) - fee

    transfer = spec.Transfer(
        sender=sender_index,
        recipient=recipient_index,
        amount=amount,
        fee=fee,
        slot=slot,
        pubkey=transfer_pubkey,
    )
    if signed:
        sign_transfer(spec, state, transfer, transfer_privkey)

    # ensure withdrawal_credentials reproducible
    state.validators[transfer.sender].withdrawal_credentials = (
        spec.int_to_bytes(spec.BLS_WITHDRAWAL_PREFIX, length=1) + spec.hash(transfer.pubkey)[1:]
    )

    return transfer


def sign_transfer(spec, state, transfer, privkey):
    transfer.signature = bls_sign(
        message_hash=signing_root(transfer),
        privkey=privkey,
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_TRANSFER,
            message_epoch=spec.get_current_epoch(state),
        )
    )
    return transfer
