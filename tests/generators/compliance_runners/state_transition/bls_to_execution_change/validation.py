"""Independent semantic validation for BLS-to-execution-change vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check


_YAML = YAML(typ="safe")


def recover_dimensions(pre: Any, signed_change: Any) -> dict[str, Any]:
    message = signed_change.message
    index_in_range = message.validator_index < len(pre.validators)
    if index_in_range:
        validator = pre.validators[message.validator_index]
        has_bls_credential = validator.withdrawal_credentials[:1] == spec.BLS_WITHDRAWAL_PREFIX
        from_pubkey_matches = validator.withdrawal_credentials[1:] == spec.sha256(message.from_bls_pubkey)[1:]
    else:
        has_bls_credential = False
        from_pubkey_matches = False
    with bls_enabled():
        domain = spec.compute_domain(
            spec.DOMAIN_BLS_TO_EXECUTION_CHANGE,
            genesis_validators_root=pre.genesis_validators_root,
        )
        signature_valid = bool(
            bls.Verify(
                message.from_bls_pubkey,
                spec.compute_signing_root(message, domain),
                signed_change.signature,
            )
        )
    if not index_in_range:
        outcome = "REJECT_INDEX"
    elif not has_bls_credential:
        outcome = "REJECT_CREDENTIAL_PREFIX"
    elif not from_pubkey_matches:
        outcome = "REJECT_PUBKEY_MISMATCH"
    elif not signature_valid:
        outcome = "REJECT_SIGNATURE"
    else:
        outcome = "ACCEPT"
    return {
        "validator_index_in_range": bool(index_in_range),
        "has_bls_withdrawal_credential": bool(has_bls_credential),
        "from_pubkey_matches": bool(from_pubkey_matches),
        "signature_valid": signature_valid,
        "outcome": outcome,
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    signed_change = decode(case_dir / "address_change.ssz_snappy", spec.SignedBLSToExecutionChange)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    return check_dimensions(claimed, recover_dimensions(pre, signed_change))
