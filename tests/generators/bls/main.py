"""
BLS test vectors generator
"""

import milagro_bls_binding as milagro_bls

from eth_utils import encode_hex
from typing import Tuple, Iterable, Any, Callable, Dict

from eth2spec.utils import bls
from eth2spec.test.helpers.constants import ALTAIR
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.altair import spec


###############################################################################
# Helper functions
###############################################################################


def hex_to_int(x: str) -> int:
    return int(x, 16)


def expect_exception(func, *args):
    try:
        func(*args)
    except Exception:
        pass
    else:
        raise Exception("should have raised exception")


###############################################################################
# Precomputed constants
###############################################################################


MESSAGES = [
    bytes(b"\x00" * 32),
    bytes(b"\x56" * 32),
    bytes(b"\xab" * 32),
]
SAMPLE_MESSAGE = b"\x12" * 32

PRIVKEYS = [
    # Curve order is 256, so private keys use 32 bytes at most.
    # Also, not all integers are valid private keys. Therefore, using pre-generated keys.
    hex_to_int(
        "0x00000000000000000000000000000000263dbd792f5b1be47ed85f8938c0f29586af0d3ac7b977f21c278fe1462040e3"
    ),
    hex_to_int(
        "0x0000000000000000000000000000000047b8192d77bf871b62e87859d653922725724a5c031afeabc60bcef5ff665138"
    ),
    hex_to_int(
        "0x00000000000000000000000000000000328388aff0d4a5b7dc9205abd374e7e98f3cd9f3418edb4eafda5fb16473d216"
    ),
]

ZERO_PUBKEY = b"\x00" * 48
G1_POINT_AT_INFINITY = b"\xc0" + b"\x00" * 47

ZERO_SIGNATURE = b"\x00" * 96
G2_POINT_AT_INFINITY = b"\xc0" + b"\x00" * 95

ZERO_PRIVKEY = 0
ZERO_PRIVKEY_BYTES = b"\x00" * 32


###############################################################################
# Test cases for eth_aggregate_pubkeys
###############################################################################


def case_eth_aggregate_pubkeys():
    def get_test_runner(input_getter):
        def _runner():
            pubkeys = input_getter()
            try:
                aggregate_pubkey = None
                aggregate_pubkey = spec.eth_aggregate_pubkeys(pubkeys)
            except:
                expect_exception(milagro_bls._AggregatePKs, pubkeys)
            if aggregate_pubkey is not None:
                assert aggregate_pubkey == milagro_bls._AggregatePKs(pubkeys)
            return [
                (
                    "data",
                    "data",
                    {
                        "input": [encode_hex(pubkey) for pubkey in pubkeys],
                        "output": (
                            encode_hex(aggregate_pubkey) if aggregate_pubkey is not None else None
                        ),
                    },
                )
            ]

        return _runner

    # Valid pubkey
    for i, privkey in enumerate(PRIVKEYS):

        def get_inputs(privkey=privkey):
            return [bls.SkToPk(privkey)]

        yield f"eth_aggregate_pubkeys_valid_{i}", get_test_runner(get_inputs)

    # Valid pubkeys
    if True:

        def get_inputs():
            return [bls.SkToPk(privkey) for privkey in PRIVKEYS]

        yield "eth_aggregate_pubkeys_valid_pubkeys", get_test_runner(get_inputs)

    # Invalid pubkeys -- len(pubkeys) == 0
    if True:

        def get_inputs():
            return []

        yield "eth_aggregate_pubkeys_empty_list", get_test_runner(get_inputs)

    # Invalid pubkeys -- [ZERO_PUBKEY]
    if True:

        def get_inputs():
            return [ZERO_PUBKEY]

        yield "eth_aggregate_pubkeys_zero_pubkey", get_test_runner(get_inputs)

    # Invalid pubkeys -- G1 point at infinity
    if True:

        def get_inputs():
            return [G1_POINT_AT_INFINITY]

        yield "eth_aggregate_pubkeys_infinity_pubkey", get_test_runner(get_inputs)

    # Invalid pubkeys -- b'\x40\x00\x00\x00....\x00' pubkey
    if True:

        def get_inputs():
            return [b"\x40" + b"\00" * 47]

        yield "eth_aggregate_pubkeys_x40_pubkey", get_test_runner(get_inputs)


###############################################################################
# Test cases for eth_fast_aggregate_verify
###############################################################################


def case_eth_fast_aggregate_verify():
    def get_test_runner(input_getter):
        def _runner():
            pubkeys, message, aggregate_signature = input_getter()
            try:
                ok = None
                ok = spec.eth_fast_aggregate_verify(pubkeys, message, aggregate_signature)
            except:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "pubkeys": [encode_hex(pubkey) for pubkey in pubkeys],
                            "message": encode_hex(message),
                            "signature": encode_hex(aggregate_signature),
                        },
                        "output": ok if ok is not None else None,
                    },
                )
            ]

        return _runner

    # Valid signature
    for i, message in enumerate(MESSAGES):

        def get_inputs(i=i, message=message):
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
            return pubkeys, message, aggregate_signature

        yield f"eth_fast_aggregate_verify_valid_{i}", get_test_runner(get_inputs)

    # Invalid signature -- extra pubkey
    for i, message in enumerate(MESSAGES):

        def get_inputs(i=i, message=message):
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            # Add an extra pubkey to the end
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys] + [bls.SkToPk(PRIVKEYS[-1])]
            return pubkeys, message, aggregate_signature

        yield f"eth_fast_aggregate_verify_extra_pubkey_{i}", get_test_runner(get_inputs)

    # Invalid signature -- tampered with signature
    for i, message in enumerate(MESSAGES):

        def get_inputs(i=i, message=message):
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
            # Tamper with the signature
            tampered_signature = aggregate_signature[:-4] + b"\xff\xff\xff\xff"
            return pubkeys, message, tampered_signature

        yield f"eth_fast_aggregate_verify_tampered_signature_{i}", get_test_runner(get_inputs)

    # NOTE: Unlike `FastAggregateVerify`, len(pubkeys) == 0 and signature == G2_POINT_AT_INFINITY is VALID
    if True:

        def get_inputs():
            return [], MESSAGES[-1], G2_POINT_AT_INFINITY

        yield "eth_fast_aggregate_verify_na_pubkeys_and_infinity_signature", get_test_runner(
            get_inputs
        )

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == 0x00...
    if True:

        def get_inputs():
            return [], MESSAGES[-1], ZERO_SIGNATURE

        yield "eth_fast_aggregate_verify_na_pubkeys_and_zero_signature", get_test_runner(get_inputs)

    # Invalid pubkeys and signature -- pubkeys contains point at infinity
    if True:

        def get_inputs():
            pubkeys = [bls.SkToPk(privkey) for privkey in PRIVKEYS]
            pubkeys_with_infinity = pubkeys + [G1_POINT_AT_INFINITY]
            signatures = [bls.Sign(privkey, SAMPLE_MESSAGE) for privkey in PRIVKEYS]
            aggregate_signature = bls.Aggregate(signatures)
            return pubkeys_with_infinity, SAMPLE_MESSAGE, aggregate_signature

        yield "eth_fast_aggregate_verify_infinity_pubkey", get_test_runner(get_inputs)


###############################################################################
# Main logic
###############################################################################


def create_provider(
    fork_name: SpecForkName,
    handler_name: str,
    test_case_fn: Callable[[], Iterable[Tuple[str, Dict[str, Any]]]],
) -> gen_typing.TestProvider:

    def prepare_fn() -> None:
        # Nothing to load / change in spec. Maybe in future forks.
        # Put the tests into the general config category, to not require any particular configuration.
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for case_name, case_fn in test_case_fn():
            yield gen_typing.TestCase(
                fork_name=fork_name,
                preset_name="general",
                runner_name="bls",
                handler_name=handler_name,
                suite_name="bls",
                case_name=case_name,
                case_fn=case_fn,
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_py_ecc()  # Py-ecc is chosen instead of Milagro, since the code is better understood to be correct.
    gen_runner.run_generator(
        "bls",
        [
            create_provider(ALTAIR, "eth_aggregate_pubkeys", case_eth_aggregate_pubkeys),
            create_provider(ALTAIR, "eth_fast_aggregate_verify", case_eth_fast_aggregate_verify),
        ],
    )
