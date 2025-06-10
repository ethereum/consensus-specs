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
        # The lower bound max blobs per block limit:
        {
            "epoch": 10,
            "max_blobs_per_block": 0,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0570c363",
        },
        # Various max blobs per block limits:
        {
            "epoch": 11,
            "max_blobs_per_block": 1,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0570c362",
        },
        {
            "epoch": 12,
            "max_blobs_per_block": 15,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0570c36c",
        },
        {
            "epoch": 13,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0570c3e3",
        },
        # The upper max blobs per block limit, minus one:
        {
            "epoch": 14,
            "max_blobs_per_block": 4095,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0570cc9c",
        },
        # The upper max blobs per block limit:
        {
            "epoch": 15,
            "max_blobs_per_block": 4096,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x0570d363",
        },
        # Different fork versions:
        {
            "epoch": 10,
            "max_blobs_per_block": 128,
            "fork_version": "0x07000000",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xaa78d082",
        },
        {
            "epoch": 10,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0x9eb2e770",
        },
        {
            "epoch": 10,
            "max_blobs_per_block": 128,
            "fork_version": "0x07000001",
            "genesis_validators_root": b"\x00" * 32,
            "expected_fork_digest": "0xc023835a",
        },
        # Different genesis validators roots:
        {
            "epoch": 10,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x01" * 32,
            "expected_fork_digest": "0x272d343a",
        },
        {
            "epoch": 10,
            "max_blobs_per_block": 128,
            "fork_version": "0x06000000",
            "genesis_validators_root": b"\x02" * 32,
            "expected_fork_digest": "0x5ad12b0f",
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
