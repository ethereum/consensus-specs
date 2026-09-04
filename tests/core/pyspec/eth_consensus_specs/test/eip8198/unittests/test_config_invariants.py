from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_eip8198_and_later,
)
from eth_consensus_specs.test.helpers.eip8198.schedule import DEADLINE_BPS

DEADLINE_FIELDS = list(DEADLINE_BPS)


@with_eip8198_and_later
@spec_test
@single_phase
def test_invariants(spec):
    schedule = spec.config.SLOT_DURATION_SCHEDULE
    assert len(schedule) > 0
    assert schedule[0]["EPOCH"] == spec.GENESIS_EPOCH
    previous_epoch = None
    for entry in schedule:
        assert entry["SLOT_DURATION_MS"] > 0
        assert entry["SLOT_DURATION_MS"] % 1000 == 0
        for field in DEADLINE_FIELDS:
            assert 0 < entry[field] < entry["SLOT_DURATION_MS"]
        assert entry["PROPOSER_REORG_CUTOFF_MS"] < entry["ATTESTATION_DUE_MS"]
        assert entry["ATTESTATION_DUE_MS"] < entry["AGGREGATE_DUE_MS"]
        assert entry["SYNC_MESSAGE_DUE_MS"] < entry["CONTRIBUTION_DUE_MS"]
        assert entry["PAYLOAD_DUE_MS"] < entry["PAYLOAD_ATTESTATION_DUE_MS"]
        if previous_epoch is not None:
            assert entry["EPOCH"] > previous_epoch
            assert entry["EPOCH"] >= spec.config.EIP8198_FORK_EPOCH
            assert entry["EPOCH"] != spec.FAR_FUTURE_EPOCH
            assert spec.compute_fork_version(entry["EPOCH"]) != spec.compute_fork_version(
                spec.Epoch(entry["EPOCH"] - 1)
            )
        previous_epoch = entry["EPOCH"]
    assert spec.compute_fork_version(spec.config.EIP8198_FORK_EPOCH) == (
        spec.config.EIP8198_FORK_VERSION
    )
