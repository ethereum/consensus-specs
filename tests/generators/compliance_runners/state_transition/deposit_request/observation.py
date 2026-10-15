"""Observe the deposit request's declared input profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.generators.compliance_runners.state_transition.aspects_helpers.deposit_amount import (
    deposit_amount_profile,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_profile,
)

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
        Context,
    )


def observe_attributes(ctx: Context) -> dict[str, object]:
    spec, pre, request = ctx.spec, ctx.pre, ctx.operation
    return {
        "observed_amount_profile": deposit_amount_profile(spec, request.amount),
        "observed_withdrawal_credentials_profile": withdrawal_credentials_profile(
            spec, request.withdrawal_credentials
        ),
        "observed_signature_valid": bool(
            spec.is_valid_deposit_signature(
                request.pubkey,
                request.withdrawal_credentials,
                request.amount,
                request.signature,
            )
        ),
        "observed_pubkey_is_existing_validator": any(
            request.pubkey == validator.pubkey for validator in pre.validators
        ),
    }
