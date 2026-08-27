"""Independent validation of process_consolidation_request vectors.

Recovers every applicable coverage dimension from the decoded pre state and
ConsolidationRequest via the real spec predicates (source + target validators,
churn, both paths), and recomputes the 19-way outcome. Imports neither the
materializer nor the model.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from generators.compliance_runners.state_transition.validation import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

    from generators.compliance_runners.state_transition.validation import Check

_YAML = YAML(typ="safe")
_ACCEPT = {"SWITCHED_TO_COMPOUNDING", "CONSOLIDATED"}

def _tri(x: bool) -> str:
    return "T" if x else "F"

def _credential(v: Any) -> str:
    prefix = bytes(v.withdrawal_credentials[:1])
    if prefix == bytes(spec.COMPOUNDING_WITHDRAWAL_PREFIX):
        return "CRED_COMPOUNDING"
    if prefix == bytes(spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX):
        return "CRED_ETH1"
    return "CRED_BLS"

def recover(pre: Any, request: Any) -> dict[str, Any]:
    cur = spec.get_current_epoch(pre)
    scp = int(spec.config.SHARD_COMMITTEE_PERIOD)
    val_pubkeys = [v.pubkey for v in pre.validators]
    same = request.source_pubkey == request.target_pubkey
    source_found = request.source_pubkey in val_pubkeys

    r: dict[str, Any] = {
        "same_source_target": bool(same),
        "pending_consolidations_full":
            len(pre.pending_consolidations) == int(spec.PENDING_CONSOLIDATIONS_LIMIT),
        "sufficient_consolidation_churn":
            int(spec.get_consolidation_churn_limit(pre)) > int(spec.MIN_ACTIVATION_BALANCE),
        "validator_pubkey_found": bool(source_found),
    }

    if source_found:
        sv = pre.validators[val_pubkeys.index(request.source_pubkey)]
        sidx = spec.ValidatorIndex(val_pubkeys.index(request.source_pubkey))
        r["validator_credential"] = _credential(sv)
        r["validator_has_execution_credential"] = bool(spec.has_execution_withdrawal_credential(sv))
        r["validator_has_compounding_credential"] = bool(spec.has_compounding_withdrawal_credential(sv))
        r["source_address_matches"] = _tri(sv.withdrawal_credentials[12:] == request.source_address)
        r["validator_active"] = _tri(bool(spec.is_active_validator(sv, cur)))
        r["validator_exiting"] = _tri(sv.exit_epoch != spec.FAR_FUTURE_EPOCH)
        r["validator_old_enough"] = _tri(int(cur) >= int(sv.activation_epoch) + scp)
        r["has_pending_partial_withdrawal"] = _tri(int(spec.get_pending_balance_to_withdraw(pre, sidx)) > 0)
    else:
        r["validator_credential"] = "CRED_NA"
        r["validator_has_execution_credential"] = False
        r["validator_has_compounding_credential"] = False
        for n in ("source_address_matches", "validator_active", "validator_exiting",
                  "validator_old_enough", "has_pending_partial_withdrawal"):
            r[n] = "NA"

    # target role only on the consolidation path
    if same:
        r["target_found"] = "NA"
        r["target_credential"] = "CRED_NA"
        r["target_has_compounding_credential"] = False
        r["target_active"] = "NA"
        r["target_exiting"] = "NA"
    elif request.target_pubkey in val_pubkeys:
        tv = pre.validators[val_pubkeys.index(request.target_pubkey)]
        r["target_found"] = "T"
        r["target_credential"] = _credential(tv)
        r["target_has_compounding_credential"] = bool(spec.has_compounding_withdrawal_credential(tv))
        r["target_active"] = _tri(bool(spec.is_active_validator(tv, cur)))
        r["target_exiting"] = _tri(tv.exit_epoch != spec.FAR_FUTURE_EPOCH)
    else:
        r["target_found"] = "F"
        r["target_credential"] = "CRED_NA"
        r["target_has_compounding_credential"] = False
        for n in ("target_active", "target_exiting"):
            r[n] = "NA"

    r["outcome"] = _derive(r)
    r["state_effected"] = r["outcome"] in _ACCEPT
    return r

def _derive(r: dict) -> str:
    same = r["same_source_target"]
    src_found = r["validator_pubkey_found"]
    src_auth = r["source_address_matches"] == "T"
    src_eth1 = r["validator_credential"] == "CRED_ETH1"
    src_exec = r["validator_has_execution_credential"]
    src_active = r["validator_active"] == "T"
    src_exiting = r["validator_exiting"] == "T"
    src_old = r["validator_old_enough"] == "T"
    src_pending = r["has_pending_partial_withdrawal"] == "T"

    if same and src_found and src_auth and src_eth1 and src_active and not src_exiting:
        return "SWITCHED_TO_COMPOUNDING"
    if same:
        if not src_found:
            return "SWITCH_REJECTED_SOURCE_NOT_FOUND"
        if not src_auth:
            return "SWITCH_REJECTED_NOT_AUTHORIZED"
        if not src_eth1:
            return "SWITCH_REJECTED_NOT_ETH1"
        if not src_active:
            return "SWITCH_REJECTED_INACTIVE"
        return "SWITCH_REJECTED_EXITING"
    if r["pending_consolidations_full"]:
        return "REJECTED_QUEUE_FULL"
    if not r["sufficient_consolidation_churn"]:
        return "REJECTED_INSUFFICIENT_CHURN"
    if not src_found:
        return "REJECTED_SOURCE_NOT_FOUND"
    if r["target_found"] != "T":
        return "REJECTED_TARGET_NOT_FOUND"
    if not (src_exec and src_auth):
        return "REJECTED_SOURCE_CREDENTIALS"
    if not r["target_has_compounding_credential"]:
        return "REJECTED_TARGET_NOT_COMPOUNDING"
    if not src_active:
        return "REJECTED_SOURCE_INACTIVE"
    if r["target_active"] != "T":
        return "REJECTED_TARGET_INACTIVE"
    if src_exiting:
        return "REJECTED_SOURCE_EXITING"
    if r["target_exiting"] == "T":
        return "REJECTED_TARGET_EXITING"
    if not src_old:
        return "REJECTED_SOURCE_TOO_YOUNG"
    if src_pending:
        return "REJECTED_SOURCE_PENDING_WITHDRAWAL"
    return "CONSOLIDATED"

def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    request = decode(case_dir / "consolidation_request.ssz_snappy", spec.ConsolidationRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)
    return check_dimensions(claimed, actual)
