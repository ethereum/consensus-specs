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
    assert spec.config.SLOT_DURATION_MS % 1000 == 0
    previous_epoch = None
    for entry in spec.config.SLOT_DURATION_SCHEDULE:
        assert entry["EPOCH"] >= spec.config.EIP8198_FORK_EPOCH
        assert entry["SLOT_DURATION_MS"] > 0
        assert entry["SLOT_DURATION_MS"] % 1000 == 0
        if previous_epoch is not None:
            assert entry["EPOCH"] > previous_epoch
        previous_epoch = entry["EPOCH"]
    assert spec.compute_fork_version(spec.config.EIP8198_FORK_EPOCH) == (
        spec.config.EIP8198_FORK_VERSION
    )
