"""Concrete numeric witnesses for abstract voluntary-exit dimensions."""

from functools import cache

BUCKET_DELTAS = {"LT_FAR": -2, "LT_1": -1, "EQ": 0, "GT_1": 1, "GT_FAR": 2}


def cmp5_bucket(delta):
    if delta < -1:
        return "LT_FAR"
    if delta > 1:
        return "GT_FAR"
    return {-1: "LT_1", 0: "EQ", 1: "GT_1"}[delta]


@cache
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
                key = (fresh, cmp5_bucket(delta), "NA" if kind == "ZERO" else kind)
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
                    "earliest_lt_new": fresh,
                    "balance_gt_consumable": cmp5_bucket(delta),
                    "additional_epochs": "NA" if kind == "ZERO" else kind,
                    "effective_balance": balance,
                    "churn_budget": budget,
                }
    return tuple(selected.values())


def churn_witness(spec, assignment):
    """Select balance and budget without adding dimensions to coverage generation."""
    active = assignment.activation_le_current and assignment.current_lt_exit
    for witness in churn_witnesses(spec, active=active):
        if all(
            getattr(assignment, name) == witness[name]
            for name in ("earliest_lt_new", "balance_gt_consumable", "additional_epochs")
        ):
            return witness["effective_balance"], witness["churn_budget"]
    raise ValueError("no aligned balance and churn-budget witness for target assignment")
