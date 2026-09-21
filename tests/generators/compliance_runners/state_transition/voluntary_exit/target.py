"""Coverage target for Gloas ``process_voluntary_exit``.

Aspects follow the structure of the handler slice and are written as capture
functions: their bodies *are* the factor declarations (parsed once) and are
interpreted with concrete values when ``observe`` calls them.

  epochs      the activity / exit-initiated / message-epoch / seasoning checks
  pending     ``get_pending_balance_to_withdraw(state, index) == 0`` and the
              shape of the loop that computes it
  signature   ``bls.Verify(...)``
  churn       ``initiate_validator_exit`` -> ``compute_exit_epoch_and_update_churn``
  outcome     accepted / rejected (built in)
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from typing import Literal

from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    ACCEPTED,
    capture_observations,
    capture_outcome,
    CAttribute,
    CEnum,
    CFactor,
    CGate,
    Cmp,
    Context,
    count_class,
    coverage_aspect,
    CPred,
    each,
    fix,
    NA,
    nwise,
    nwise_of,
    rules,
    Target,
    union,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

# --- aspects ------------------------------------------------------------------

COUNTS = ("ZERO", "ONE", "MANY")


@coverage_aspect("epochs")
def capture_epochs(
    validator_found: CGate,
    current_epoch: CAttribute[int],
    message_epoch: CAttribute[int],
    activation_epoch: CAttribute[int],
    exit_epoch: CAttribute[int],
    far_future_epoch: CAttribute[int],
    shard_committee_period: CAttribute[int],
):
    if validator_found:
        activation_le_current: CFactor = activation_epoch <= current_epoch
        current_lt_exit: CFactor = current_epoch < exit_epoch
        exit_not_initiated: CPred = exit_epoch == far_future_epoch
        current_ge_message_epoch: CFactor = current_epoch >= message_epoch
        current_ge_seasoned: CFactor = current_epoch >= activation_epoch + shard_committee_period


@coverage_aspect("pending")
def capture_pending(
    matching_pending: CAttribute[int],
    foreign_pending: CAttribute[int],
    pending_balance: CAttribute[int],
):
    pending_balance_zero: CPred = pending_balance == 0
    matching_pending_entries: CEnum[COUNTS] = count_class(matching_pending)
    foreign_pending_entries: CEnum[Literal["ZERO", "SOME"]] = (
        "ZERO" if foreign_pending == 0 else "SOME"
    )


@coverage_aspect("signature")
def capture_signature(validator_found: CGate, signature_valid: CAttribute[bool]):
    if validator_found:
        signature_ok: CPred = signature_valid


@coverage_aspect("churn")
def capture_churn(
    validator_found: CGate,
    earliest_exit_epoch: CAttribute[int],
    new_exit_epoch: CAttribute[int],
    exit_balance_to_consume: CAttribute[int],
    per_epoch_churn: CAttribute[int],
    effective_balance: CAttribute[int],
):
    earliest_lt_new: CFactor = earliest_exit_epoch < new_exit_epoch
    consumable = (
        per_epoch_churn if earliest_exit_epoch < new_exit_epoch else exit_balance_to_consume
    )
    if validator_found:
        balance_gt_consumable: CFactor = effective_balance > consumable
        if effective_balance > consumable:
            additional_epochs: CEnum[Literal["ONE", "MANY"]] = count_class(
                (effective_balance - consumable - 1) // per_epoch_churn + 1
            )


EPOCHS, PENDING, SIGNATURE, CHURN = (
    capture_epochs,
    capture_pending,
    capture_signature,
    capture_churn,
)
ASPECTS = (EPOCHS, PENDING, SIGNATURE, CHURN, capture_outcome)

# The handler's assertion chain: accepted <=> all of these hold.
GATES = (
    EPOCHS["activation_le_current"],
    EPOCHS["current_lt_exit"],
    EPOCHS["exit_not_initiated"],
    EPOCHS["current_ge_message_epoch"],
    EPOCHS["current_ge_seasoned"],
    PENDING["pending_balance_zero"],
    SIGNATURE["signature_ok"],
)

# --- observation --------------------------------------------------------------


def observe(ctx: Context) -> None:
    spec, pre, signed_exit = ctx.spec, ctx.pre, ctx.operation
    message = signed_exit.message
    validator_index = int(message.validator_index)
    validator_found = validator_index < len(pre.validators)
    current_epoch = int(spec.get_current_epoch(pre))
    message_epoch = int(message.epoch)
    capture_observations(validator_index, validator_found)

    activation_epoch = exit_epoch = effective_balance = signature_valid = NA
    if validator_found:
        validator = pre.validators[validator_index]
        activation_epoch = int(validator.activation_epoch)
        exit_epoch = int(validator.exit_epoch)
        effective_balance = int(validator.effective_balance)
        with bls_enabled():
            domain = spec.compute_domain(
                spec.DOMAIN_VOLUNTARY_EXIT,
                spec.config.CAPELLA_FORK_VERSION,
                pre.genesis_validators_root,
            )
            signing_root = spec.compute_signing_root(message, domain)
            signature_valid = bool(
                bls.Verify(validator.pubkey, signing_root, signed_exit.signature)
            )

    capture_epochs(
        validator_found,
        current_epoch,
        message_epoch,
        activation_epoch,
        exit_epoch,
        far_future_epoch=int(spec.FAR_FUTURE_EPOCH),
        shard_committee_period=int(spec.config.SHARD_COMMITTEE_PERIOD),
    )

    matching = [
        w for w in pre.pending_partial_withdrawals if int(w.validator_index) == validator_index
    ]
    capture_pending(
        matching_pending=len(matching),
        foreign_pending=len(pre.pending_partial_withdrawals) - len(matching),
        pending_balance=sum(int(w.amount) for w in matching),
    )

    capture_signature(validator_found, signature_valid)

    capture_churn(
        validator_found,
        earliest_exit_epoch=int(pre.earliest_exit_epoch),
        new_exit_epoch=int(spec.compute_activation_exit_epoch(spec.Epoch(current_epoch))),
        exit_balance_to_consume=int(pre.exit_balance_to_consume),
        per_epoch_churn=int(spec.get_exit_churn_limit(pre)),
        effective_balance=effective_balance,
    )


# --- feasibility --------------------------------------------------------------


def _holds(a: dict, f, g) -> bool | None:
    return None if f.name not in a else f.holds(a[f.name], g)


def _far_below(a: dict, f: Cmp, g: str) -> bool:
    """``lhs < rhs`` by more than one, as far as the granularity can tell."""
    return bool(_holds(a, f, g)) and f.far(a[f.name], g) is not False


def _uninitiated_exit_is_far(a: dict, g: str) -> bool:
    if _holds(a, EPOCHS["exit_not_initiated"], g) is True and "current_lt_exit" in a:
        return _far_below(a, EPOCHS["current_lt_exit"], g)
    return True


def _seasoned_is_activated_long_ago(a: dict, g: str) -> bool:
    if _holds(a, EPOCHS["current_ge_seasoned"], g) is True and "activation_le_current" in a:
        return _far_below(a, EPOCHS["activation_le_current"], g)
    return True


def _accepted_iff_all_gates(a: dict, g: str) -> bool:
    accepted = _holds(a, ACCEPTED, g)
    if accepted is None:
        return True
    gates = [_holds(a, f, g) for f in GATES]
    if accepted:
        return all(h is not False for h in gates)
    # Rejected, yet every gate is assigned and holds: impossible.
    return not all(h is True for h in gates)


def _additional_epochs_only_when_exceeding(a: dict, g: str) -> bool:
    if "additional_epochs" in a:
        return _holds(a, CHURN["balance_gt_consumable"], g) is not False
    return True


def _pending_balance_needs_entries(a: dict, g: str) -> bool:
    if _holds(a, PENDING["pending_balance_zero"], g) is False:
        return a.get("matching_pending_entries") != "ZERO"
    return True


FEASIBLE = rules(
    _uninitiated_exit_is_far,
    _seasoned_is_activated_long_ago,
    _accepted_iff_all_gates,
    _additional_epochs_only_when_exceeding,
    _pending_balance_needs_entries,
)

# --- profiles -----------------------------------------------------------------

NORMAL = fix(accepted=True)
EXCEPTIONAL = fix(accepted=False)
ALL_FACTORS = [f for a in ASPECTS for f in a.factors]

PROFILES = {
    # every value of every factor, regardless of behaviour
    "smoke": each(ALL_FACTORS).where(FEASIBLE),
    # accepted exits: churn arithmetic exhaustively, epoch boundaries pairwise
    "normal": (NORMAL * (CHURN.exhaustive() | EPOCHS.nwise(2))).where(FEASIBLE),
    # rejected exits: each failing gate in combination with every other factor value
    "exceptional": (EXCEPTIONAL * nwise(ALL_FACTORS, 2)).where(FEASIBLE),
    # each aspect on its own, then aspects pairwise against each other's values
    "standard": union(each(ALL_FACTORS), nwise_of([a.each() for a in ASPECTS], 2)).where(FEASIBLE),
    # deeper focus on the pending-withdrawal loop
    "pending_loop": (PENDING.exhaustive() * each([ACCEPTED])).where(FEASIBLE),
}

TARGET = Target("voluntary_exit", ASPECTS, observe, PROFILES, FEASIBLE)
