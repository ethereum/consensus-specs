from eth_consensus_specs.utils.ssz.ssz_typing import Boolean

from .ssz_test_case import invalid_test_case, valid_test_case

INVALID_BOOL_CASES = [
    ("2", b"\x02"),
    ("rev_nibble", b"\x10"),
    ("0x80", b"\x80"),
    ("0xff", b"\xff"),
]


def valid_cases():
    yield "true", valid_test_case(lambda: Boolean(True))  # noqa: FBT003
    yield "false", valid_test_case(lambda: Boolean(False))  # noqa: FBT003


def invalid_cases():
    for description, data in INVALID_BOOL_CASES:
        yield f"byte_{description}", invalid_test_case(Boolean, lambda data=data: data)
