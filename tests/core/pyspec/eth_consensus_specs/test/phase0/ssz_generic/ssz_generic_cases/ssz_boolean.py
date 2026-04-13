from eth_consensus_specs.utils.ssz.ssz_typing import boolean

from .ssz_test_case import invalid_test_case, valid_test_case

INVALID_BOOL_CASES = [
    ("2", b"\x02"),
    ("rev_nibble", b"\x10"),
    ("0x80", b"\x80"),
    ("0xff", b"\xff"),
]


def valid_cases():
    yield "true", valid_test_case(lambda: boolean(True))
    yield "false", valid_test_case(lambda: boolean(False))


def invalid_cases():
    for description, data in INVALID_BOOL_CASES:
        yield f"byte_{description}", invalid_test_case(boolean, lambda data=data: data)
