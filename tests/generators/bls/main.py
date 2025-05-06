"""
BLS test vectors generator
"""

from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import (
    encode_hex,
    int_to_big_endian,
)
import milagro_bls_binding as milagro_bls

from eth2spec.utils import bls
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.altair import spec


def to_bytes(i):
    return i.to_bytes(32, "big")


def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b"\x00")
    return encode_hex(byte_value)


def hex_to_int(x: str) -> int:
    return int(x, 16)


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


def expect_exception(func, *args):
    try:
        func(*args)
    except Exception:
        pass
    else:
        raise Exception("should have raised exception")


def case_sign():
    def get_test_runner(privkey, message):
        def _runner():
            try:
                sig = None
                sig = bls.Sign(privkey, message)
            except:
                expect_exception(milagro_bls.Sign, privkey, message)
            if sig is not None:
                assert sig == milagro_bls.Sign(to_bytes(privkey), message)
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "privkey": int_to_hex(privkey),
                            "message": encode_hex(message),
                        },
                        "output": encode_hex(sig),
                    },
                )
            ]

        return _runner

    # Valid cases
    for i, privkey in enumerate(PRIVKEYS):
        for j, message in enumerate(MESSAGES):
            yield f"sign_case_{i}_{j}", get_test_runner(privkey, message)

    # Edge case: privkey == 0
    yield "sign_case_zero_privkey", get_test_runner(privkey, message)


def case_verify():
    def get_test_runner(input_getter):
        def _runner():
            pubkey, message, signature = input_getter()
            try:
                ok = None
                ok = bls.Verify(pubkey, message, signature)
            except:
                expect_exception(milagro_bls.Verify, pubkey, message, signature)
            if ok is not None:
                assert ok == milagro_bls.Verify(pubkey, message, signature)
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "pubkey": encode_hex(pubkey),
                            "message": encode_hex(message),
                            "signature": encode_hex(signature),
                        },
                        "output": ok if ok is not None else None,
                    },
                )
            ]

        return _runner

    # Valid
    for i, privkey in enumerate(PRIVKEYS):
        for j, message in enumerate(MESSAGES):

            def get_inputs():
                signature = bls.Sign(privkey, message)
                pubkey = bls.SkToPk(privkey)
                return pubkey, message, signature

            yield f"verify_valid_case_{i}_{j}", get_test_runner(get_inputs)

    # Invalid signatures -- wrong pubkey
    for i, privkey in enumerate(PRIVKEYS):
        for j, message in enumerate(MESSAGES):

            def get_inputs():
                signature = bls.Sign(privkey, message)
                # This is the wrong pubkey
                pubkey = bls.SkToPk(PRIVKEYS[(i + 1) % len(PRIVKEYS)])
                return pubkey, message, signature

            yield f"verify_wrong_pubkey_case_{i}_{j}", get_test_runner(get_inputs)

    # Invalid signature -- tampered with signature
    for i, privkey in enumerate(PRIVKEYS):
        for j, message in enumerate(MESSAGES):

            def get_inputs():
                signature = bls.Sign(privkey, message)
                # Tamper with the signature
                signature = signature[:-4] + b"\xff\xff\xff\xff"
                pubkey = bls.SkToPk(privkey)
                return pubkey, message, signature

            yield f"verify_tampered_signature_case_{i}_{j}", get_test_runner(get_inputs)

    # Invalid pubkey and signature with the point at infinity
    if True:

        def get_inputs():
            return G1_POINT_AT_INFINITY, SAMPLE_MESSAGE, G2_POINT_AT_INFINITY

        yield "verify_infinity_pubkey_and_infinity_signature", get_test_runner(get_inputs)


def case_aggregate():
    def get_test_runner(input_getter):
        def _runner():
            sigs = input_getter()
            try:
                aggregate_sig = None
                aggregate_sig = bls.Aggregate(sigs)
            except:
                # XXX(jtraglia): Apparently milagro_bls.Aggregate doesn't throw an exception here?
                if len(sigs) != 0:
                    expect_exception(milagro_bls.Aggregate, sigs)
            if aggregate_sig is not None:
                assert aggregate_sig == milagro_bls.Aggregate(sigs)
            return [
                (
                    "data",
                    "data",
                    {
                        "input": [encode_hex(sig) for sig in sigs],
                        "output": encode_hex(aggregate_sig) if aggregate_sig is not None else None,
                    },
                )
            ]

        return _runner

    for i, message in enumerate(MESSAGES):

        def get_inputs():
            return [bls.Sign(privkey, message) for privkey in PRIVKEYS]

        yield f"aggregate_{i}", get_test_runner(get_inputs)

    # Invalid pubkeys -- len(pubkeys) == 0
    # No signatures to aggregate. Follow IETF BLS spec, return `None` to represent INVALID.
    # https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-04#section-2.8
    if True:

        def get_inputs():
            return []

        yield "aggregate_na_signatures", get_test_runner(get_inputs)

    # Valid to aggregate G2 point at infinity
    if True:

        def get_inputs():
            return [G2_POINT_AT_INFINITY]

        yield "aggregate_infinity_signature", get_test_runner(get_inputs)


def case_fast_aggregate_verify():
    def get_test_runner(input_getter):
        def _runner():
            pubkeys, message, aggregate_signature = input_getter()
            try:
                ok = None
                ok = bls.FastAggregateVerify(pubkeys, message, aggregate_signature)
            except:
                expect_exception(
                    milagro_bls.FastAggregateVerify, pubkeys, message, aggregate_signature
                )
            if ok is not None:
                assert ok == milagro_bls.FastAggregateVerify(pubkeys, message, aggregate_signature)
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

        def get_inputs():
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
            return pubkeys, message, aggregate_signature

        yield f"fast_aggregate_verify_valid_{i}", get_test_runner(get_inputs)

    # Invalid signature -- extra pubkey
    for i, message in enumerate(MESSAGES):

        def get_inputs():
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            # Add an extra pubkey to the end
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys] + [bls.SkToPk(PRIVKEYS[-1])]
            return pubkeys, message, aggregate_signature

        yield f"fast_aggregate_verify_extra_pubkey_{i}", get_test_runner(get_inputs)

    # Invalid signature -- tampered with signature
    for i, message in enumerate(MESSAGES):

        def get_inputs():
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
            # Tamper with the signature
            aggregate_signature = aggregate_signature[:-4] + b"\xff\xff\xff\xff"
            return pubkeys, message, aggregate_signature

        yield f"fast_aggregate_verify_tampered_signature_{i}", get_test_runner(get_inputs)

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == Z1_SIGNATURE
    if True:

        def get_inputs():
            return [], MESSAGES[-1], G2_POINT_AT_INFINITY

        yield "fast_aggregate_verify_na_pubkeys_and_infinity_signature", get_test_runner(get_inputs)

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == 0x00...
    if True:

        def get_inputs():
            return [], MESSAGES[-1], ZERO_SIGNATURE

        yield "fast_aggregate_verify_na_pubkeys_and_zero_signature", get_test_runner(get_inputs)

    # Invalid pubkeys and signature -- pubkeys contains point at infinity
    if True:

        def get_inputs():
            pubkeys = [bls.SkToPk(privkey) for privkey in PRIVKEYS]
            pubkeys_with_infinity = pubkeys + [G1_POINT_AT_INFINITY]
            signatures = [bls.Sign(privkey, SAMPLE_MESSAGE) for privkey in PRIVKEYS]
            aggregate_signature = bls.Aggregate(signatures)
            return pubkeys_with_infinity, SAMPLE_MESSAGE, aggregate_signature

        yield "fast_aggregate_verify_infinity_pubkey", get_test_runner(get_inputs)


def case_aggregate_verify():
    def get_test_runner(input_getter):
        def _runner():
            pubkeys, messages, aggregate_signature = input_getter()
            try:
                ok = None
                ok = bls.AggregateVerify(pubkeys, messages, aggregate_signature)
            except:
                expect_exception(
                    milagro_bls.AggregateVerify, pubkeys, messages, aggregate_signature
                )
            if ok is not None:
                assert ok == milagro_bls.AggregateVerify(pubkeys, messages, aggregate_signature)
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "pubkeys": [encode_hex(pubkey) for pubkey in pubkeys],
                            "messages": [encode_hex(message) for message in messages],
                            "signature": encode_hex(aggregate_signature),
                        },
                        "output": ok if ok is not None else None,
                    },
                )
            ]

        return _runner

    if True:

        def get_inputs():
            pubkeys = []
            pubkeys_serial = []
            messages = []
            messages_serial = []
            sigs = []
            for privkey, message in zip(PRIVKEYS, MESSAGES):
                sig = bls.Sign(privkey, message)
                pubkey = bls.SkToPk(privkey)
                pubkeys.append(pubkey)
                pubkeys_serial.append(encode_hex(pubkey))
                messages.append(message)
                messages_serial.append(encode_hex(message))
                sigs.append(sig)
            aggregate_signature = bls.Aggregate(sigs)
            return pubkeys, messages, aggregate_signature

        yield "aggregate_verify_valid", get_test_runner(get_inputs)

    # Invalid signature
    if True:

        def get_inputs():
            pubkeys = []
            pubkeys_serial = []
            messages = []
            messages_serial = []
            sigs = []
            for privkey, message in zip(PRIVKEYS, MESSAGES):
                sig = bls.Sign(privkey, message)
                pubkey = bls.SkToPk(privkey)
                pubkeys.append(pubkey)
                pubkeys_serial.append(encode_hex(pubkey))
                messages.append(message)
                messages_serial.append(encode_hex(message))
                sigs.append(sig)
            aggregate_signature = bls.Aggregate(sigs)
            tampered_signature = aggregate_signature[:4] + b"\xff\xff\xff\xff"
            return pubkeys, messages, tampered_signature

        yield "aggregate_verify_tampered_signature", get_test_runner(get_inputs)

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == Z1_SIGNATURE
    if True:

        def get_inputs():
            return [], [], G2_POINT_AT_INFINITY

        yield "aggregate_verify_na_pubkeys_and_infinity_signature", get_test_runner(get_inputs)

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == 0x00...
    if True:

        def get_inputs():
            return [], [], ZERO_SIGNATURE

        yield "aggregate_verify_na_pubkeys_and_zero_signature", get_test_runner(get_inputs)

    # Invalid pubkeys and signature -- pubkeys contains point at infinity
    if True:

        def get_inputs():
            pubkeys = []
            pubkeys_serial = []
            messages = []
            messages_serial = []
            sigs = []
            for privkey, message in zip(PRIVKEYS, MESSAGES):
                sig = bls.Sign(privkey, message)
                pubkey = bls.SkToPk(privkey)
                pubkeys.append(pubkey)
                pubkeys_serial.append(encode_hex(pubkey))
                messages.append(message)
                messages_serial.append(encode_hex(message))
                sigs.append(sig)
            aggregate_signature = bls.Aggregate(sigs)

            # Add a point at infinity pubkey
            pubkeys_with_infinity = pubkeys + [G1_POINT_AT_INFINITY]
            messages_with_sample = messages + [SAMPLE_MESSAGE]
            return pubkeys_with_infinity, messages_with_sample, aggregate_signature

        yield "aggregate_verify_infinity_pubkey", get_test_runner(get_inputs)


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
        def get_inputs():
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


def case_eth_fast_aggregate_verify():
    """
    Similar to `case04_fast_aggregate_verify` except for the empty case
    """

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

        def get_inputs():
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
            return pubkeys, message, aggregate_signature

        yield f"eth_fast_aggregate_verify_valid_{i}", get_test_runner(get_inputs)

    # Invalid signature -- extra pubkey
    for i, message in enumerate(MESSAGES):

        def get_inputs():
            privkeys = PRIVKEYS[: i + 1]
            sigs = [bls.Sign(privkey, message) for privkey in privkeys]
            aggregate_signature = bls.Aggregate(sigs)
            # Add an extra pubkey to the end
            pubkeys = [bls.SkToPk(privkey) for privkey in privkeys] + [bls.SkToPk(PRIVKEYS[-1])]
            return pubkeys, message, aggregate_signature

        yield f"eth_fast_aggregate_verify_extra_pubkey_{i}", get_test_runner(get_inputs)

    # Invalid signature -- tampered with signature
    for i, message in enumerate(MESSAGES):

        def get_inputs():
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
            create_provider(PHASE0, "sign", case_sign),
            create_provider(PHASE0, "verify", case_verify),
            create_provider(PHASE0, "aggregate", case_aggregate),
            create_provider(PHASE0, "fast_aggregate_verify", case_fast_aggregate_verify),
            create_provider(PHASE0, "aggregate_verify", case_aggregate_verify),
            create_provider(ALTAIR, "eth_aggregate_pubkeys", case_eth_aggregate_pubkeys),
            create_provider(ALTAIR, "eth_fast_aggregate_verify", case_eth_fast_aggregate_verify),
        ],
    )
