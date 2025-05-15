from .ssz_test_case import valid_test_case, invalid_test_case
from eth2spec.utils.ssz.ssz_typing import boolean


def valid_cases():
    yield "true", valid_test_case(lambda: boolean(True))
    yield "false", valid_test_case(lambda: boolean(False))


def invalid_cases():
    yield "byte_2", invalid_test_case(lambda: b"\x02")
    yield "byte_rev_nibble", invalid_test_case(lambda: b"\x10")
    yield "byte_0x80", invalid_test_case(lambda: b"\x80")
    yield "byte_full", invalid_test_case(lambda: b"\xff")
