"""Coverage regression checks for effective-balance hysteresis boundaries."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import score

from .cases import constants, signature
from .coverage import build_profile, TARGET
from .target import COMPARISONS, PROFILES


def test_profiles_cover_their_dsl_obligations():
    target = TARGET.for_spec(spec)
    assert build_profile("exceptional", spec=spec) == ([], [])
    assert all(f.granularity == "cmp5" for f in COMPARISONS)
    counts = {}
    for name in PROFILES:
        records, chosen = build_profile(name, spec=spec)
        assert records == chosen
        report = score(target, records, target.profiles[name])
        assert report.uncovered == []
        assert report.unexpected == []
        counts[name] = len(records)
    assert counts["max"] > counts["standard"] > 5


def test_max_preserves_old_behaviors_and_exact_guard_boundaries():
    records, _ = build_profile("max", spec=spec)
    signatures = [
        {k: v for k, v in record.items() if k not in ("balance", "effective_balance")}
        for record in records
    ]
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
        assert signature(witness, constants(spec), COMPARISONS) in signatures
        assert witness in {
            (record["credential_type"], record["effective_balance"], record["balance"])
            for record in records
        }
    for guard in ("downward_trigger", "upward_trigger"):
        assert {record[guard] for record in records} == {"LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR"}
