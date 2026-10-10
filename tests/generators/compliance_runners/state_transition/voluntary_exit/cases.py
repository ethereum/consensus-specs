"""Epoch witnesses for voluntary-exit boundary coverage."""

BUCKET_DELTAS = {"LT_FAR": -2, "LT_1": -1, "EQ": 0, "GT_1": 1, "GT_FAR": 2}
SCENARIOS = (
    "VALID",
    "VALID_CARRIED_CHURN",
    "VALID_EXHAUSTED_CHURN",
    "INACTIVE",
    "ALREADY_EXITED",
    "FUTURE_EXIT_EPOCH",
    "TOO_YOUNG",
    "PENDING_WITHDRAWAL",
    "INVALID_SIGNATURE",
)


def cmp5_bucket(delta):
    if delta < -1:
        return "LT_FAR"
    if delta > 1:
        return "GT_FAR"
    return {-1: "LT_1", 0: "EQ", 1: "GT_1"}[delta]


def epoch_witness(period, scenario, message_bucket, seasoned_bucket):
    current = period + 4
    message = current - BUCKET_DELTAS[message_bucket]
    activation = (
        current + 1 if scenario == "INACTIVE" else current - period - BUCKET_DELTAS[seasoned_bucket]
    )
    if cmp5_bucket(current - activation - period) != seasoned_bucket:
        raise ValueError("seasoning bucket conflicts with the inactive-validator scenario")
    return current, message, activation


def scenario_record(period, scenario, message_bucket, seasoned_bucket):
    current, message, activation = epoch_witness(period, scenario, message_bucket, seasoned_bucket)
    record = {
        "scenario": scenario,
        "validator_active": activation <= current,
        "exit_not_initiated": scenario != "ALREADY_EXITED",
        "exit_epoch_valid": current >= message,
        "active_long_enough": current >= activation + period,
        "exit_churn_state": (
            "CARRIED_AVAILABLE"
            if scenario == "VALID_CARRIED_CHURN"
            else "CARRIED_EXHAUSTED"
            if scenario == "VALID_EXHAUSTED_CHURN"
            else "NEW_EPOCH"
        ),
        "no_pending_withdrawal": scenario != "PENDING_WITHDRAWAL",
        "signature_valid": scenario != "INVALID_SIGNATURE",
        "current_ge_message_epoch": message_bucket,
        "current_ge_seasoned": seasoned_bucket,
    }
    gates = (
        ("validator_active", "REJECT_INACTIVE"),
        ("exit_not_initiated", "REJECT_ALREADY_EXITED"),
        ("exit_epoch_valid", "REJECT_EXIT_EPOCH"),
        ("active_long_enough", "REJECT_TOO_YOUNG"),
        ("no_pending_withdrawal", "REJECT_PENDING_WITHDRAWAL"),
        ("signature_valid", "REJECT_SIGNATURE"),
    )
    record["outcome"] = next((outcome for gate, outcome in gates if not record[gate]), "ACCEPT")
    record["_rank"] = record["_nfaults"] = int(record["outcome"] != "ACCEPT")
    return record


def churn_witnesses(spec, *, active=True):
    """Aligned effective-balance witnesses for a 64-validator vector.

    Changing the exiting balance also changes total active balance and hence
    the fresh budget. Compute that relationship for each candidate witness.
    Carried budgets also include one-Gwei residuals left by partial withdrawals.
    """
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    standard = int(spec.MAX_EFFECTIVE_BALANCE)
    maximum = int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA)
    minimum_churn = int(spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA)
    quotient = int(spec.config.CHURN_LIMIT_QUOTIENT_GLOAS)
    selected = {}
    for balance in range(standard, maximum + 1, increment):
        total = 63 * standard + (balance if active else 0)
        churn = max(minimum_churn, total // quotient)
        churn -= churn % increment
        for fresh in (True, False):
            budgets = (
                [churn]
                if fresh
                else list(
                    dict.fromkeys(
                        (
                            balance + 1,
                            balance - 1,
                            balance + increment,
                            balance,
                            balance - increment,
                            churn,
                            0,
                            increment,
                            balance - churn,
                            balance - 2 * churn,
                        )
                    )
                )
            )
            for budget in budgets:
                if not fresh and not 0 <= budget <= churn:
                    continue
                delta = balance - budget
                additional = 0 if delta <= 0 else (delta - 1) // churn + 1
                kind = "ZERO" if additional == 0 else "ONE" if additional == 1 else "MANY"
                state = (
                    "NEW_EPOCH"
                    if fresh
                    else ("CARRIED_EXHAUSTED" if delta > 0 else "CARRIED_AVAILABLE")
                )
                key = (state, cmp5_bucket(delta), kind)
                if key in selected:
                    previous = selected[key]
                    if not (
                        fresh
                        and delta < 0
                        and abs(delta)
                        < abs(previous["effective_balance"] - previous["churn_budget"])
                    ):
                        continue
                selected[key] = {
                    "exit_churn_state": state,
                    "balance_gt_consumable": cmp5_bucket(delta),
                    "churn_additional_epochs": kind,
                    "effective_balance": balance,
                    "churn_budget": budget,
                    "churn_fresh": fresh,
                }
    return list(selected.values())
