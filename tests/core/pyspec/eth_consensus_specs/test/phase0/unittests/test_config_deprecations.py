from eth_consensus_specs.test.context import single_phase, spec_test, with_all_phases
from eth_consensus_specs.test.helpers.forks import is_post_eip8198


@with_all_phases
@spec_test
@single_phase
def test_slot_duration_config_deprecation(spec):
    expected = not is_post_eip8198(spec)
    assert ("SLOT_DURATION_MS" in spec.Configuration.__annotations__) == expected
    assert ("SLOT_DURATION_MS" in spec.config._asdict()) == expected
    assert hasattr(spec.config, "SLOT_DURATION_MS") == expected
