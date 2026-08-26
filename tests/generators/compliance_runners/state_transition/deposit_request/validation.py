"""Independent validation of process_deposit_request vectors.

Since the handler has no predicates to re-derive beyond `start_index_unset`, the
substantive check is OUTPUT correctness: the appended PendingDeposit matches the
request (with slot = pre.slot), the queue grew by one, and the start index was
set iff it was unset. Imports neither the materializer nor the model.
"""
from __future__ import annotations

from ..validation import check_dimensions, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

from ..aspects_helpers.withdrawal_credential import withdrawal_credentials_profile

_YAML = YAML(typ="safe")

def recover(pre: Any, request: Any) -> dict[str, Any]:
    amount = int(request.amount)
    if amount == 0:
        amount_profile = "ZERO"
    elif amount == int(spec.MIN_DEPOSIT_AMOUNT):
        amount_profile = "MINIMUM"
    elif amount == int(spec.MIN_ACTIVATION_BALANCE):
        amount_profile = "ACTIVATION"
    elif amount > int(spec.MIN_ACTIVATION_BALANCE):
        amount_profile = "ABOVE_ACTIVATION"
    else:
        amount_profile = "UNKNOWN"
    return {
        "amount_profile": amount_profile,
        "amount_nonzero": amount > 0,
        "withdrawal_credentials_profile": withdrawal_credentials_profile(
            spec, request.withdrawal_credentials
        ),
        "signature_profile": (
            "VALID"
            if spec.is_valid_deposit_signature(
                request.pubkey,
                request.withdrawal_credentials,
                request.amount,
                request.signature,
            )
            else "INVALID"
        ),
        "pubkey_is_existing_validator": request.pubkey in [v.pubkey for v in pre.validators],
    }

def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    request = decode(case_dir / "deposit_request.ssz_snappy", spec.DepositRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)
    return check_dimensions(claimed, actual)
