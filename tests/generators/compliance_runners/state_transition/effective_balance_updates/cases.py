"""Concrete witnesses and their abstract effective-balance signatures."""

from __future__ import annotations

from functools import cache


def constants(spec):
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    hysteresis_increment = increment // int(spec.HYSTERESIS_QUOTIENT)
    return (
        increment,
        hysteresis_increment * int(spec.HYSTERESIS_DOWNWARD_MULTIPLIER),
        hysteresis_increment * int(spec.HYSTERESIS_UPWARD_MULTIPLIER),
        int(spec.MAX_EFFECTIVE_BALANCE),
        int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA),
    )


def witnesses(values):
    """Place balances on both sides of each guard and at increment/cap edges."""
    increment, downward, upward, standard_max, compounding_max = values
    # Prefer the former five scenarios for their abstract signatures.
    yield "STANDARD", standard_max, standard_max
    yield "STANDARD", standard_max, standard_max - increment - 1
    yield "STANDARD", 29 * increment, 31 * increment + 1
    yield "STANDARD", 30 * increment, 34 * increment
    yield "COMPOUNDING", 31 * increment, 33 * increment + 1
    for credential, maximum in (("STANDARD", standard_max), ("COMPOUNDING", compounding_max)):
        effective_levels = {
            0,
            increment,
            2 * increment,
            29 * increment,
            30 * increment,
            31 * increment,
            32 * increment,
            max(0, maximum - increment),
            maximum,
        }
        for effective in sorted(e for e in effective_levels if e <= maximum):
            centers = {
                0,
                increment,
                maximum,
                maximum + increment,
                effective - downward,
                effective + upward,
                effective,
                effective + increment,
            }
            balances = {
                center + offset
                for center in centers
                for offset in (-2, -1, 0, 1, 2)
                if center + offset >= 0
            }
            # Exercise each rounding bucket near every guard/cap center.
            balances.update(
                (center // increment + step) * increment + remainder
                for center in centers
                for step in (-1, 0, 1)
                for remainder in (0, 1, increment - 1, 2)
                if 0 <= remainder < increment
                and (center // increment + step) * increment + remainder >= 0
            )
            for balance in sorted(balances):
                yield credential, effective, balance


def signature(witness, values, comparisons):
    factors = {factor.name: factor for factor in comparisons}
    credential, effective, balance = witness
    increment, downward, upward, standard_max, compounding_max = values
    maximum = compounding_max if credential == "COMPOUNDING" else standard_max
    rounded = balance - balance % increment
    changed = balance + downward < effective or effective + upward < balance
    new_effective = min(rounded, maximum) if changed else effective
    outcome = (
        "UNCHANGED"
        if new_effective == effective
        else "EFFECTIVE_BALANCE_CAPPED"
        if new_effective == maximum
        else "EFFECTIVE_BALANCE_UPDATED"
    )
    return {
        "credential_type": credential,
        "downward_trigger": factors["downward_trigger"].abstract(balance + downward - effective),
        "upward_trigger": factors["upward_trigger"].abstract(effective + upward - balance),
        "rounded_vs_cap": factors["rounded_vs_cap"].abstract(rounded - maximum),
        "balance_remainder": (
            "ZERO"
            if balance % increment == 0
            else "ONE"
            if balance % increment == 1
            else "LAST"
            if balance % increment == increment - 1
            else "INTERIOR"
        ),
        "outcome": outcome,
    }


@cache
def representatives(values, comparisons):
    """One deterministic concrete witness per realizable full DSL assignment."""
    selected = {}
    for witness in witnesses(values):
        record = signature(witness, values, comparisons)
        key = tuple(sorted(record.items()))
        selected.setdefault(key, witness)
    return selected
