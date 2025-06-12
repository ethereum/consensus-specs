from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_config_overrides,
    with_fulu_and_later,
)


@with_fulu_and_later
@spec_test
@single_phase
@with_config_overrides(
    {
        "ELECTRA_FORK_EPOCH": 9,
        "FULU_FORK_EPOCH": 100,
        "BLOB_SCHEDULE": [
            {"EPOCH": 9, "MAX_BLOBS_PER_BLOCK": 9},
            {"EPOCH": 100, "MAX_BLOBS_PER_BLOCK": 100},
            {"EPOCH": 150, "MAX_BLOBS_PER_BLOCK": 175},
            {"EPOCH": 200, "MAX_BLOBS_PER_BLOCK": 200},
            {"EPOCH": 250, "MAX_BLOBS_PER_BLOCK": 275},
            {"EPOCH": 300, "MAX_BLOBS_PER_BLOCK": 300},
        ],
    },
    emit=False,
)
def test_compute_fork_digest(spec):
    test_cases = [
        # Different epochs and blob limits:
        {
            "epoch": 9,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x39f8e7c3",
        },
        {
            "epoch": 10,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x39f8e7c3",
        },
        {
            "epoch": 11,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x39f8e7c3",
        },
        {
            "epoch": 99,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x39f8e7c3",
        },
        {
            "epoch": 100,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x44a571e8",
        },
        {
            "epoch": 101,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x44a571e8",
        },
        {
            "epoch": 150,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x1171afca",
        },
        {
            "epoch": 199,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x1171afca",
        },
        {
            "epoch": 200,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x427a30ab",
        },
        {
            "epoch": 201,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x427a30ab",
        },
        {
            "epoch": 250,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xd5310ef1",
        },
        {
            "epoch": 299,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xd5310ef1",
        },
        {
            "epoch": 300,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x51d229f7",
        },
        {
            "epoch": 301,
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x51d229f7",
        },
        # Different genesis validators roots:
        {
            "epoch": 9,
            "genesis_validators_root": b"\x01" * 32,
            "expected_fork_digest": "0xe41615ba",
        },
        {
            "epoch": 9,
            "genesis_validators_root": b"\x02" * 32,
            "expected_fork_digest": "0x46790ef9",
        },
        {
            "epoch": 9,
            "genesis_validators_root": b"\x03" * 32,
            "expected_fork_digest": "0xa072c2f5",
        },
        {
            "epoch": 100,
            "genesis_validators_root": b"\x01" * 32,
            "expected_fork_digest": "0xbfe98545",
        },
        {
            "epoch": 100,
            "genesis_validators_root": b"\x02" * 32,
            "expected_fork_digest": "0x9b7e4788",
        },
        {
            "epoch": 100,
            "genesis_validators_root": b"\x03" * 32,
            "expected_fork_digest": "0x8b5ce4af",
        },
    ]

    for case in test_cases:
        # Compute the fork digest given the inputs from the test case
        fork_digest = spec.compute_fork_digest(case["genesis_validators_root"], case["epoch"])
        # Check that the computed fork digest matches our expected value
        assert f"0x{fork_digest.hex()}" == case["expected_fork_digest"]
