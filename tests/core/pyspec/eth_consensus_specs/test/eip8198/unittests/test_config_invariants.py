from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_eip8198_and_later,
)


@with_eip8198_and_later
@spec_test
@single_phase
def test_invariants(spec):
    assert spec.config.SLOT_DURATION_MS > 0
    assert spec.config.SLOT_DURATION_MS_EIP8198 > 0
    assert spec.config.SLOT_DURATION_MS % 1000 == 0
    assert spec.config.SLOT_DURATION_MS_EIP8198 % 1000 == 0
    assert spec.config.SLOT_DURATION_MS_EIP8198 < spec.config.SLOT_DURATION_MS
    assert spec.config.EIP8198_FORK_EPOCH == spec.FAR_FUTURE_EPOCH or (
        spec.config.EIP8198_FORK_EPOCH > spec.config.HEZE_FORK_EPOCH
    )
    assert spec.compute_fork_version(spec.config.EIP8198_FORK_EPOCH) == (
        spec.config.EIP8198_FORK_VERSION
    )
