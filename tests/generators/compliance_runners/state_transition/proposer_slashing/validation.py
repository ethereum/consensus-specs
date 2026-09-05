"""Independent validation for Gloas proposer-slashing compliance vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check

_YAML = YAML(typ="safe")


def recover(pre: Any, slashing: Any) -> dict[str, Any]:
    h1, h2 = slashing.signed_header_1, slashing.signed_header_2
    m1, m2 = h1.message, h2.message
    current, proposer = spec.get_current_epoch(pre), pre.validators[m1.proposer_index]

    def valid(signed: Any) -> bool:
        domain = spec.get_domain(
            pre,
            spec.DOMAIN_BEACON_PROPOSER,
            spec.compute_epoch_at_slot(signed.message.slot),
        )
        return bool(
            bls.Verify(
                pre.validators[signed.message.proposer_index].pubkey,
                spec.compute_signing_root(signed.message, domain),
                signed.signature,
            )
        )

    epoch = spec.compute_epoch_at_slot(m1.slot)
    if epoch == current:
        window, payment_index = (
            "CURRENT",
            int(spec.SLOTS_PER_EPOCH) + int(m1.slot) % int(spec.SLOTS_PER_EPOCH),
        )
    elif epoch == spec.get_previous_epoch(pre):
        window, payment_index = "PREVIOUS", int(m1.slot) % int(spec.SLOTS_PER_EPOCH)
    else:
        window, payment_index = "OLD", None
    payment_matches = (
        "NA"
        if payment_index is None
        else (
            "T"
            if pre.builder_pending_payments[payment_index].proposer_index == m1.proposer_index
            else "F"
        )
    )
    r = {
        "slots_match": m1.slot == m2.slot,
        "proposers_match": m1.proposer_index == m2.proposer_index,
        "headers_different": m1 != m2,
        "signature_1_valid": "T" if valid(h1) else "F",
        "signature_2_valid": "T" if valid(h2) else "F",
        "proposer_slashed": bool(proposer.slashed),
        "proposer_activated": proposer.activation_epoch <= current,
        "proposer_withdrawable": proposer.withdrawable_epoch <= current,
        "proposer_exited": proposer.exit_epoch <= current,
        "payment_window": window,
        "payment_proposer_matches": payment_matches,
    }
    slashable = spec.is_slashable_validator(proposer, current)
    if not r["slots_match"]:
        outcome = "REJECT_SLOT_MISMATCH"
    elif not r["proposers_match"]:
        outcome = "REJECT_PROPOSER_MISMATCH"
    elif not r["headers_different"]:
        outcome = "REJECT_HEADERS_EQUAL"
    elif not slashable:
        if r["proposer_slashed"]:
            outcome = "REJECT_NOT_SLASHABLE_SLASHED"
        elif not r["proposer_activated"]:
            outcome = "REJECT_NOT_ACTIVATED"
        else:
            outcome = "REJECT_NOT_SLASHABLE_WITHDRAWABLE"
    elif r["signature_1_valid"] != "T":
        outcome = "REJECT_SIGNATURE_1"
    elif r["signature_2_valid"] != "T":
        outcome = "REJECT_SIGNATURE_2"
    elif window == "OLD":
        outcome = "ACCEPT_OLD"
    else:
        outcome = f"ACCEPT_{window}_PAYMENT_{'CLEARED' if payment_matches == 'T' else 'RETAINED'}"
    r.update(
        outcome=outcome,
        pending_payment_cleared=outcome.endswith("CLEARED"),
        state_effected=outcome.startswith("ACCEPT_"),
    )
    return r


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    operation = decode(case_dir / "proposer_slashing.ssz_snappy", spec.ProposerSlashing)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, operation)
    return check_dimensions(claimed, actual)
