"""Observe the preconditions for a BLS-to-execution change."""

from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def observe_attributes(ctx):
    spec, pre, signed_change = ctx.spec, ctx.pre, ctx.operation
    message = signed_change.message
    index_in_range = int(message.validator_index) < len(pre.validators)
    if index_in_range:
        validator = pre.validators[message.validator_index]
        has_bls_credential = validator.withdrawal_credentials[:1] == spec.BLS_WITHDRAWAL_PREFIX
        from_pubkey_matches = (
            validator.withdrawal_credentials[1:] == spec.sha256(message.from_bls_pubkey)[1:]
        )
    else:
        has_bls_credential = False
        from_pubkey_matches = False

    domain = spec.compute_domain(
        spec.DOMAIN_BLS_TO_EXECUTION_CHANGE,
        genesis_validators_root=pre.genesis_validators_root,
    )
    with bls_enabled():
        signature_valid = bool(
            bls.Verify(
                message.from_bls_pubkey,
                spec.compute_signing_root(message, domain),
                signed_change.signature,
            )
        )
    return {
        "observed_validator_index_in_range": bool(index_in_range),
        "observed_has_bls_withdrawal_credential": bool(has_bls_credential),
        "observed_from_pubkey_matches": bool(from_pubkey_matches),
        "observed_signature_valid": signature_valid,
    }
