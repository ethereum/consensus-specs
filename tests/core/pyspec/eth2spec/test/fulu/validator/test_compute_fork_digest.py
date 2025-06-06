from eth2spec.test.context import (
    spec_state_test,
    with_config_overrides,
    with_fulu_and_later,
)


@with_fulu_and_later
@spec_state_test
@with_config_overrides(
    {
        "MAX_BLOBS_PER_BLOCK_ELECTRA": 9,
        "FULU_FORK_EPOCH": 5,
        "BLOB_SCHEDULE": [
            {"EPOCH": 6, "MAX_BLOBS_PER_BLOCK": 12},
            {"EPOCH": 10, "MAX_BLOBS_PER_BLOCK": 15},
        ],
    },
    emit=False,
)
def test_compute_fork_digest(spec, state):
    test_cases = [
        (5, 9),  # FULU_FORK_EPOCH, should use MAX_BLOBS_PER_BLOCK_ELECTRA
        (6, 12),  # First BLOB_SCHEDULE entry
        (10, 15),  # Second BLOB_SCHEDULE entry
        (11, 15),  # After last BLOB_SCHEDULE entry, should stay at 15
    ]

    def xor_bytes(a, b):
        return bytes(x ^ y for x, y in zip(a, b))

    for epoch, expected_max_blobs in test_cases:
        expected_fork_data_root = spec.hash_tree_root(
            spec.ForkData(
                current_version=state.fork.current_version,
                genesis_validators_root=state.genesis_validators_root,
            )
        )
        actual_fork_digest = spec.compute_fork_digest(
            state.fork.current_version, state.genesis_validators_root, epoch
        )
        expected_max_blobs_bytes = expected_max_blobs.to_bytes(4, "big")
        expected_fork_digest = spec.ForkDigest(
            xor_bytes(expected_fork_data_root[:4], expected_max_blobs_bytes)
        )
        assert actual_fork_digest == expected_fork_digest
