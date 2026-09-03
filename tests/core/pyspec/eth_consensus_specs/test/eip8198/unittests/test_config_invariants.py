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
    assert spec.config.SLOT_DURATION_MS > 0
    assert spec.config.SLOT_DURATION_MS % 1000 == 0
    previous_epoch = None
    previous_duration_ms = spec.config.SLOT_DURATION_MS
    for entry in spec.config.SLOT_DURATION_SCHEDULE:
        assert entry["EPOCH"] >= spec.config.EIP8198_FORK_EPOCH
        assert entry["SLOT_DURATION_MS"] > 0
        assert entry["SLOT_DURATION_MS"] % 1000 == 0
        # Every deadline fits in the slot and preserves the inherited ordering
        for field in DEADLINE_FIELDS:
            assert 0 < entry[field] < entry["SLOT_DURATION_MS"]
        assert entry["PROPOSER_REORG_CUTOFF_MS"] < entry["ATTESTATION_DUE_MS"]
        assert entry["ATTESTATION_DUE_MS"] < entry["AGGREGATE_DUE_MS"]
        assert entry["SYNC_MESSAGE_DUE_MS"] < entry["CONTRIBUTION_DUE_MS"]
        assert entry["PAYLOAD_DUE_MS"] < entry["PAYLOAD_ATTESTATION_DUE_MS"]
        if previous_epoch is not None:
            assert entry["EPOCH"] > previous_epoch
        previous_epoch = entry["EPOCH"]
        # A duration change must come with a blob schedule entry
        if entry["EPOCH"] != spec.FAR_FUTURE_EPOCH:
            if entry["SLOT_DURATION_MS"] != previous_duration_ms:
                blob_entries = [
                    blob_entry
                    for blob_entry in spec.config.BLOB_SCHEDULE
                    if blob_entry["EPOCH"] == entry["EPOCH"]
                ]
                assert len(blob_entries) == 1
            previous_duration_ms = entry["SLOT_DURATION_MS"]
    assert spec.compute_fork_version(spec.config.EIP8198_FORK_EPOCH) == (
        spec.config.EIP8198_FORK_VERSION
    )
