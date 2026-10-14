"""Translate complete declaration assignments to the existing concrete witness format."""

from .target import ASSERTIONS


def assignment_from_legacy(record):
    """Adapt old signatures for coverage comparison; effects are conditional."""
    accepted = record["state_effected"]
    result = {
        "slots_match": record["slots_match"],
        "proposers_match": record["proposers_match"],
        "headers_different": record["headers_different"],
        "proposer_not_slashed": not record["proposer_slashed"],
        "proposer_activated": record["proposer_activated"],
        "proposer_not_withdrawable": not record["proposer_withdrawable"],
        "exit_initiated": record["proposer_exited"],
        "signature_1_valid": record["signature_1_valid"] == "T",
        "signature_2_valid": record["signature_2_valid"] == "T",
        "payment_window": record["payment_window"],
        "accepted": accepted,
    }
    if record["payment_window"] != "OLD":
        result["payment_proposer_matches"] = record["payment_proposer_matches"] == "T"
        if accepted:
            result["pending_payment_cleared"] = record["pending_payment_cleared"]
    if accepted and not record["proposer_exited"]:
        result["churn_variant"] = record["churn_variant"]
    return result


def materializer_record(assignment):
    """Keep rejection labels and generation hints separate from observed acceptance."""
    summary = ASSERTIONS.evaluate(assignment)
    if summary.unknown:
        raise ValueError(f"incomplete assertion witness: {summary.unknown}")
    labels = (
        ("slots_match", "REJECT_SLOT_MISMATCH"),
        ("proposers_match", "REJECT_PROPOSER_MISMATCH"),
        ("headers_different", "REJECT_HEADERS_EQUAL"),
        ("proposer_not_slashed", "REJECT_NOT_SLASHABLE_SLASHED"),
        ("proposer_activated", "REJECT_NOT_ACTIVATED"),
        ("proposer_not_withdrawable", "REJECT_NOT_SLASHABLE_WITHDRAWABLE"),
        ("signature_1_valid", "REJECT_SIGNATURE_1"),
        ("signature_2_valid", "REJECT_SIGNATURE_2"),
    )
    window = assignment["payment_window"]
    cleared = assignment.get("pending_payment_cleared", False)
    outcome = next((label for name, label in labels if name in summary.failed), None)
    if outcome is None:
        outcome = (
            "ACCEPT_OLD"
            if window == "OLD"
            else f"ACCEPT_{window}_PAYMENT_{'CLEARED' if cleared else 'RETAINED'}"
        )
    return {
        "slots_match": assignment["slots_match"],
        "proposers_match": assignment["proposers_match"],
        "headers_different": assignment["headers_different"],
        "proposer_slashed": not assignment["proposer_not_slashed"],
        "proposer_activated": assignment["proposer_activated"],
        "proposer_withdrawable": not assignment["proposer_not_withdrawable"],
        "proposer_exited": assignment["exit_initiated"],
        "signature_1_valid": "T" if assignment["signature_1_valid"] else "F",
        "signature_2_valid": "T" if assignment["signature_2_valid"] else "F",
        "payment_window": window,
        "payment_proposer_matches": "NA"
        if window == "OLD"
        else "T"
        if assignment["payment_proposer_matches"]
        else "F",
        "churn_variant": assignment.get("churn_variant", "QUEUE_CHURN_NA"),
        "pending_payment_cleared": cleared,
        "state_effected": assignment["accepted"],
        "outcome": outcome,
        "_nfaults": summary.fault_count,
        "_rank": summary.fault_count,
    }
