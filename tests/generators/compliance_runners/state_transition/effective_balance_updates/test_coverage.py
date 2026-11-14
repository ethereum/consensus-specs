"""Coverage regression checks for effective-balance hysteresis boundaries."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import score
from tests.generators.compliance_runners.state_transition.provider import load_provider

from .cases import constants, representatives, signature
from .target import COMPARISONS, PROFILES, TARGET

build_profile = load_provider("effective_balance_updates").build_profile


def test_profiles_cover_their_dsl_obligations():
    target = TARGET.for_spec(spec)
    assert build_profile("exceptional", spec=spec) == []
    assert all(f.granularity == "cmp5" for f in COMPARISONS)
    counts = {}
    for name in PROFILES:
        records = build_profile(name, spec=spec)
        assert records
        assert all(set(record) == {f.name for f in target.factors} for record in records)
        report = score(target, records, target.profiles[name])
        assert report.uncovered == []
        assert report.unexpected == []
        counts[name] = len(records)
    assert counts["max"] > counts["standard"] > 5


def test_max_preserves_old_behaviors_and_exact_guard_boundaries():
    records = build_profile("max", spec=spec)
    witnesses = representatives(constants(spec), COMPARISONS)
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    maximum = int(spec.MAX_EFFECTIVE_BALANCE)
    old_cases = (
        ("STANDARD", maximum, maximum),
        ("STANDARD", maximum, maximum - increment - 1),
        ("STANDARD", 29 * increment, 31 * increment + 1),
        ("STANDARD", 30 * increment, 34 * increment),
        ("COMPOUNDING", 31 * increment, 33 * increment + 1),
    )
    for witness in old_cases:
        record = signature(witness, constants(spec), COMPARISONS)
        assert any(record.items() <= case.items() for case in records)
        assert witnesses[tuple(sorted(record.items()))] == witness
    for guard in ("downward_trigger", "upward_trigger"):
        assert {record[guard] for record in records} == {"LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR"}


def test_rounding_buckets_have_concrete_witnesses_in_every_profile():
    increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
    witnesses = representatives(constants(spec), COMPARISONS)
    for profile in PROFILES:
        records = build_profile(profile, spec=spec)
        assert {record["balance_remainder"] for record in records} == {
            "ZERO",
            "ONE",
            "LAST",
            "INTERIOR",
        }
        for record in records:
            _, _, balance = witnesses[
                tuple(sorted((k, v) for k, v in record.items() if not k.startswith("_")))
            ]
            remainder = balance % increment
            bucket = record["balance_remainder"]
            if bucket == "ZERO":
                assert remainder == 0
            elif bucket == "ONE":
                assert remainder == 1
            elif bucket == "LAST":
                assert remainder == increment - 1
            else:
                assert 2 <= remainder <= increment - 2
