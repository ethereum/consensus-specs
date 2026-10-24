"""Recover builder-deposit inputs independently from serialized vectors."""

from tests.generators.compliance_runners.state_transition.aspects_helpers.deposit_amount import (
    deposit_amount_profile,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_profile,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import NA
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def observe_attributes(ctx):
    spec, pre, request = ctx.spec, ctx.pre, ctx.operation
    pubkeys = [b.pubkey for b in pre.builders]
    found = request.pubkey in pubkeys
    credential_profile = withdrawal_credentials_profile(spec, request.withdrawal_credentials)
    with bls_enabled():
        signature_valid = bool(spec.is_valid_builder_deposit_signature(request))
    r = {
        "withdrawal_credentials_profile": credential_profile,
        "builder_pubkey_found": found,
        "builder_signature_valid": signature_valid,
        "amount_profile": deposit_amount_profile(spec, request.amount),
    }

    if found:
        b = pre.builders[pubkeys.index(request.pubkey)]
        wset = b.withdrawable_epoch != spec.FAR_FUTURE_EPOCH
        bzero = int(b.balance) == 0
        r["builder_withdrawable_epoch_set"] = bool(wset)
        r["builder_balance_zero"] = bool(bzero)
    else:
        r["builder_withdrawable_epoch_set"] = NA
        r["builder_balance_zero"] = NA

    r["reuses_swept_slot"] = bool(int(spec.get_index_for_new_builder(pre)) < len(pre.builders))
    return {f"observed_{name}": value for name, value in r.items()}
