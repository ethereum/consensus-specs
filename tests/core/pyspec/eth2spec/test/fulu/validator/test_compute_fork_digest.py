from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_fulu_and_later,
)


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_fork_digest(spec):
    test_cases = [
        # Different fork versions:
        {
            "epoch": 1,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x539df823",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 128,
            "fork_version": "0x07000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x6757cfd1",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 128,
            "fork_version": "0x07000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0d0c9c09",
        },
        # Different genesis validators roots:
        {
            "epoch": 1,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x01" * 32,
            "expected_fork_digest": "0xea022b69",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x02" * 32,
            "expected_fork_digest": "0x97fe345c",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x03" * 32,
            "expected_fork_digest": "0xe5317437",
        },
        # Different fork epochs:
        {
            "epoch": 2,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x6caefc94",
        },
        {
            "epoch": 3,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x817e4fab",
        },
        {
            "epoch": 4,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x44605a08",
        },
        # Different max blobs per block limits:
        {
            "epoch": 1,
            "max_blobs_per_block": 0,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xd6ba12a0",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 1,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0570c363",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 15,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xdd52eb85",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 4095,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xf79d2d35",
        },
        {
            "epoch": 1,
            "max_blobs_per_block": 4096,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xd9c58740",
        },
    ]

    for case in test_cases:
        # Override helper function to return our blob limit
        spec.get_max_blobs_per_block = lambda _: case["max_blobs_per_block"]
        # Compute the fork digest given the inputs from the test case
        fork_digest = spec.compute_fork_digest(
            case["fork_version"], case["genesis_validators_root"], case["epoch"]
        )
        # Check that the computed fork digest matches our expected value
        assert f"0x{fork_digest.hex()}" == case["expected_fork_digest"]
