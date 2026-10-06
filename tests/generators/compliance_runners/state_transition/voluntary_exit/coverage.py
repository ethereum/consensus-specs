"""Scenario and epoch-boundary profiles for Gloas ``process_voluntary_exit``."""

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    cover,
    dedup,
)

from .cases import BUCKET_DELTAS, churn_witnesses, cmp5_bucket, scenario_record, SCENARIOS
from .target import TARGET

ASPECTS = {
    "activity": ["validator_active", "exit_not_initiated"],
    "epoch": [
        "exit_epoch_valid",
        "active_long_enough",
        "current_ge_message_epoch",
        "current_ge_seasoned",
    ],
    "exit_churn": ["exit_churn_state", "balance_gt_consumable", "churn_additional_epochs"],
    "withdrawals": ["no_pending_withdrawal"],
    "signature": ["signature_valid"],
    "outcome": ["outcome"],
}


def _recs(spec):
    period = int(spec.config.SHARD_COMMITTEE_PERIOD)
    records = []
    for scenario in SCENARIOS:
        for message_bucket in BUCKET_DELTAS:
            for seasoned_bucket in BUCKET_DELTAS:
                if scenario.startswith("VALID") and (
                    BUCKET_DELTAS[message_bucket] < 0 or BUCKET_DELTAS[seasoned_bucket] < 0
                ):
                    continue
                if scenario == "FUTURE_EXIT_EPOCH" and BUCKET_DELTAS[message_bucket] >= 0:
                    continue
                if scenario == "TOO_YOUNG" and BUCKET_DELTAS[seasoned_bucket] >= 0:
                    continue
                if scenario == "INACTIVE" and seasoned_bucket != cmp5_bucket(-period - 1):
                    continue
                records.append(scenario_record(period, scenario, message_bucket, seasoned_bucket))
    plans = {active: churn_witnesses(spec, active=active) for active in (False, True)}
    return dedup(
        [
            {**record, **witness}
            for record in records
            for witness in plans[record["validator_active"]]
        ],
        ASPECTS,
    )


def build_profile(name: str, *, spec):
    records = _recs(spec)
    if name == "smoke":
        return cover(
            records,
            {
                "message_epoch": ["current_ge_message_epoch"],
                "seasoning": ["current_ge_seasoned"],
                "outcome": ["outcome"],
                "exit_churn": ASPECTS["exit_churn"],
            },
            1,
        )
    return _build_profile(
        records,
        name,
        ASPECTS,
        ASPECTS,
        {"outcome": ["outcome"]},
        exceptional_aspects={"epoch": ASPECTS["epoch"], "outcome": ["outcome"]},
    )


__all__ = ("TARGET", "build_profile")
