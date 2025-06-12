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
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xab3ae6c8",
        },
        {
            "epoch": 10,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xab3ae6c8",
        },
        {
            "epoch": 11,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xab3ae6c8",
        },
        {
            "epoch": 99,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xab3ae6c8",
        },
        {
            "epoch": 100,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xdf67557b",
        },
        {
            "epoch": 101,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xdf67557b",
        },
        {
            "epoch": 150,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x8ab38b59",
        },
        {
            "epoch": 199,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x8ab38b59",
        },
        {
            "epoch": 200,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xd9b81438",
        },
        {
            "epoch": 201,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xd9b81438",
        },
        {
            "epoch": 250,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x4ef32a62",
        },
        {
            "epoch": 299,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x4ef32a62",
        },
        {
            "epoch": 300,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xca100d64",
        },
        {
            "epoch": 301,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xca100d64",
        },
        # Different genesis validators roots:
        {
            "epoch": 9,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x01" * 32,
            "expected_fork_digest": "0x89671111",
        },
        {
            "epoch": 9,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x02" * 32,
            "expected_fork_digest": "0xf49b0e24",
        },
        {
            "epoch": 9,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x03" * 32,
            "expected_fork_digest": "0x86544e4f",
        },
        {
            "epoch": 100,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x01" * 32,
            "expected_fork_digest": "0xfd3aa2a2",
        },
        {
            "epoch": 100,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x02" * 32,
            "expected_fork_digest": "0x80c6bd97",
        },
        {
            "epoch": 100,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x03" * 32,
            "expected_fork_digest": "0xf209fdfc",
        },
        # Different fork versions
        {
            "epoch": 9,
            "fork_version": "0x06000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x30f8c25b",
        },
        {
            "epoch": 9,
            "fork_version": "0x07000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0432f5a9",
        },
        {
            "epoch": 9,
            "fork_version": "0x07000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x6e69a671",
        },
        {
            "epoch": 100,
            "fork_version": "0x06000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x44a571e8",
        },
        {
            "epoch": 100,
            "fork_version": "0x07000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x706f461a",
        },
        {
            "epoch": 100,
            "fork_version": "0x07000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x1a3415c2",
        },
    ]

    for case in test_cases:
        # Override function to return fork version in test case
        spec.compute_fork_version = lambda _: case["fork_version"]
        # Compute the fork digest given the inputs from the test case
        fork_digest = spec.compute_fork_digest(case["genesis_validators_root"], case["epoch"])
        # Check that the computed fork digest matches our expected value
        assert f"0x{fork_digest.hex()}" == case["expected_fork_digest"]
