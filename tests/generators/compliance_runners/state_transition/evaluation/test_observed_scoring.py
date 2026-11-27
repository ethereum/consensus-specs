"""Observed-only scoring agrees with exhaustive raw coverage on small models."""

from itertools import product

import pytest

from .coverage_dsl import NA, score
from .declarations import (
    _within_faults,
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    coverage_spec,
    dimension,
    each,
    exhaustive,
    fix,
    nwise,
    union,
)


@pytest.fixture(scope="module")
def target():
    gate = assertion("gate", attribute("gate_input", Boolean()))
    enabled = dimension("enabled", attribute("enabled_input", Boolean()), when=gate)
    alternate = dimension("alternate", attribute("alternate_input", Boolean()), when=~gate)
    check = assertion("check", attribute("check_input", Boolean()), when=enabled)
    other = dimension("other", attribute("other_input", Boolean()))
    accepted = dimension("accepted", attribute("accepted_input", Boolean()))
    factors = (gate, enabled, alternate, check, other, accepted)
    checks = assertion_set(gate, check, observed=accepted, complete=True)
    return bind(
        coverage_spec(
            "observed_scoring",
            focus="conditional projections and branch fault scopes",
            record="one vector",
            aspects=(aspect("all", *factors),),
            assertions=checks,
            constraints=(other == gate,),
            profiles={
                "pairs": nwise(factors, 2),
                "all": exhaustive(factors),
                "partial": exhaustive((enabled, alternate)),
                "fixed": fix(enabled=True) * each((other,)),
                "conflict": each((enabled,)) * each((alternate,)),
                "cross_witness": exhaustive((enabled, other)) * fix(gate=True),
                "product": each((gate,)) * each((other,)),
                "normal": checks.normal(each((gate, other))),
                "single": checks.exceptional(nwise(factors, 2), faults=1),
                "mixed": union(
                    checks.normal(each((other,))), checks.exceptional(each((gate,)), faults=2)
                ),
            },
        ),
        observe_attributes=lambda ctx: {},
    ).for_spec(object(), backend="python")


def exhaustive_covered(formula, record):
    # The previous scoring algorithm: enumerate all raw rows, then retain
    # obligations covered by this record within the corresponding fault scope.
    return {
        obligation
        for scopes, _, obligations in formula._compiled(filtered=False)
        if all(_within_faults(scope, record, formula.owner.bound_constants) for scope in scopes)
        for obligation in obligations
        if all(
            record.get(name, NA) is not NA and record[name] == value for name, value in obligation
        )
    }


@pytest.mark.parametrize(
    "profile",
    [
        "pairs",
        "all",
        "partial",
        "fixed",
        "conflict",
        "cross_witness",
        "product",
        "normal",
        "single",
        "mixed",
    ],
)
def test_scoring_matches_exhaustive_raw_projection(target, profile):
    formula = target.profiles[profile]
    wanted = formula.run()
    names = tuple(target.definition.by_name)
    # Includes complete, partial, unavailable, and structurally inconsistent
    # records; absent values must not make an n-wise obligation shorter.
    for values in product((False, True, NA), repeat=len(names)):
        record = dict(zip(names, values, strict=True))
        expected = exhaustive_covered(formula, record)
        assert formula.covered([record], filtered=False) == expected
        report = score(target, [record], formula)
        assert {frozenset(o.items()) for o in report.unexpected} == expected - wanted


def test_projection_does_not_require_the_whole_record_to_be_structurally_valid(target):
    record = {"gate": False, "enabled": True, "alternate": True, "other": True, "accepted": False}
    formula = target.profiles["pairs"]
    assert formula.covered([record], filtered=False) == exhaustive_covered(formula, record)
    assert frozenset((("gate", False), ("other", True))) in formula.covered(
        [record], filtered=False
    )
