"""Independent semantic validation for voluntary-exit vectors."""

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


def recover_dimensions(pre: Any, signed_exit: Any) -> dict[str, Any]:
    message = signed_exit.message
    validator = pre.validators[message.validator_index]
    current_epoch = spec.get_current_epoch(pre)
    pending_balance = spec.get_pending_balance_to_withdraw(pre, message.validator_index)
    with bls_enabled():
        domain = spec.compute_domain(
            spec.DOMAIN_VOLUNTARY_EXIT,
            spec.config.CAPELLA_FORK_VERSION,
            pre.genesis_validators_root,
        )
        signature_valid = bool(
            bls.Verify(validator.pubkey, spec.compute_signing_root(message, domain), signed_exit.signature)
        )
    validator_active = bool(spec.is_active_validator(validator, current_epoch))
    exit_not_initiated = validator.exit_epoch == spec.FAR_FUTURE_EPOCH
    exit_epoch_valid = current_epoch >= message.epoch
    active_long_enough = current_epoch >= validator.activation_epoch + spec.config.SHARD_COMMITTEE_PERIOD
    no_pending_withdrawal = pending_balance == 0
    new_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    if pre.earliest_exit_epoch < new_exit_epoch:
        exit_churn_state = "NEW_EPOCH"
    elif validator.effective_balance > pre.exit_balance_to_consume:
        exit_churn_state = "CARRIED_EXHAUSTED"
    else:
        exit_churn_state = "CARRIED_AVAILABLE"
    if not validator_active:
        outcome = "REJECT_INACTIVE"
    elif not exit_not_initiated:
        outcome = "REJECT_ALREADY_EXITED"
    elif not exit_epoch_valid:
        outcome = "REJECT_EXIT_EPOCH"
    elif not active_long_enough:
        outcome = "REJECT_TOO_YOUNG"
    elif not no_pending_withdrawal:
        outcome = "REJECT_PENDING_WITHDRAWAL"
    elif not signature_valid:
        outcome = "REJECT_SIGNATURE"
    else:
        outcome = "ACCEPT"
    return {
        "validator_active": validator_active,
        "exit_not_initiated": exit_not_initiated,
        "exit_epoch_valid": exit_epoch_valid,
        "active_long_enough": active_long_enough,
        "exit_churn_state": exit_churn_state,
        "no_pending_withdrawal": no_pending_withdrawal,
        "signature_valid": signature_valid,
        "outcome": outcome,
    }


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    signed_exit = decode(case_dir / "voluntary_exit.ssz_snappy", spec.SignedVoluntaryExit)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    return check_dimensions(claimed, recover_dimensions(pre, signed_exit))
