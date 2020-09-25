"""
BLS test vectors generator
"""

from hashlib import sha256
from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import (
    encode_hex,
    int_to_big_endian,
)
import milagro_bls_binding as milagro_bls

from eth2spec.utils import bls
from eth2spec.test.context import PHASE0
from gen_base import gen_runner, gen_typing


def to_bytes(i):
    return i.to_bytes(32, "big")


def hash(x):
    return sha256(x).digest()


def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b'\x00')
    return encode_hex(byte_value)


def hex_to_int(x: str) -> int:
    return int(x, 16)


MESSAGES = [
    bytes(b'\x00' * 32),
    bytes(b'\x56' * 32),
    bytes(b'\xab' * 32),
]
SAMPLE_MESSAGE = b'\x12' * 32

PRIVKEYS = [
    # Curve order is 256 so private keys are 32 bytes at most.
    # Also not all integers is a valid private key, so using pre-generated keys
    hex_to_int('0x00000000000000000000000000000000263dbd792f5b1be47ed85f8938c0f29586af0d3ac7b977f21c278fe1462040e3'),
    hex_to_int('0x0000000000000000000000000000000047b8192d77bf871b62e87859d653922725724a5c031afeabc60bcef5ff665138'),
    hex_to_int('0x00000000000000000000000000000000328388aff0d4a5b7dc9205abd374e7e98f3cd9f3418edb4eafda5fb16473d216'),
]
PUBKEYS = [bls.SkToPk(privkey) for privkey in PRIVKEYS]

Z1_PUBKEY = b'\xc0' + b'\x00' * 47
NO_SIGNATURE = b'\x00' * 96
Z2_SIGNATURE = b'\xc0' + b'\x00' * 95
ZERO_PRIVKEY = 0
ZERO_PRIVKEY_BYTES = b'\x00' * 32


def expect_exception(func, *args):
    try:
        func(*args)
    except Exception:
        pass
    else:
        raise Exception("should have raised exception")


def case01_sign():
    # Valid cases
    for privkey in PRIVKEYS:
        for message in MESSAGES:
            sig = bls.Sign(privkey, message)
            assert sig == milagro_bls.Sign(to_bytes(privkey), message)  # double-check with milagro
            identifier = f'{int_to_hex(privkey)}_{encode_hex(message)}'
            yield f'sign_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'privkey': int_to_hex(privkey),
                    'message': encode_hex(message),
                },
                'output': encode_hex(sig)
            }
    # Edge case: privkey == 0
    expect_exception(bls.Sign, ZERO_PRIVKEY, message)
    # expect_exception(milagro_bls.Sign, ZERO_PRIVKEY_BYTES, message)  # TODO: enable it when milagro is ready
    yield f'sign_case_zero_privkey', {
        'input': {
            'privkey': encode_hex(ZERO_PRIVKEY_BYTES),
            'message': encode_hex(message),
        },
        'output': None
    }


def case02_verify():
    for i, privkey in enumerate(PRIVKEYS):
        for message in MESSAGES:
            # Valid signature
            signature = bls.Sign(privkey, message)
            pubkey = bls.SkToPk(privkey)

            assert milagro_bls.SkToPk(to_bytes(privkey)) == pubkey
            assert milagro_bls.Sign(to_bytes(privkey), message) == signature

            identifier = f'{encode_hex(pubkey)}_{encode_hex(message)}'

            assert bls.Verify(pubkey, message, signature)
            assert milagro_bls.Verify(pubkey, message, signature)

            yield f'verify_valid_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'pubkey': encode_hex(pubkey),
                    'message': encode_hex(message),
                    'signature': encode_hex(signature),
                },
                'output': True,
            }

            # Invalid signatures -- wrong pubkey
            wrong_pubkey = bls.SkToPk(PRIVKEYS[(i + 1) % len(PRIVKEYS)])
            identifier = f'{encode_hex(wrong_pubkey)}_{encode_hex(message)}'
            assert not bls.Verify(wrong_pubkey, message, signature)
            assert not milagro_bls.Verify(wrong_pubkey, message, signature)
            yield f'verify_wrong_pubkey_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'pubkey': encode_hex(wrong_pubkey),
                    'message': encode_hex(message),
                    'signature': encode_hex(signature),
                },
                'output': False,
            }

            # Invalid signature -- tampered with signature
            tampered_signature = signature[:-4] + b'\xFF\xFF\xFF\xFF'
            identifier = f'{encode_hex(pubkey)}_{encode_hex(message)}'
            assert not bls.Verify(pubkey, message, tampered_signature)
            assert not milagro_bls.Verify(pubkey, message, tampered_signature)
            yield f'verify_tampered_signature_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'pubkey': encode_hex(pubkey),
                    'message': encode_hex(message),
                    'signature': encode_hex(tampered_signature),
                },
                'output': False,
            }

    # Invalid pubkey and signature with the point at infinity
    assert not bls.Verify(Z1_PUBKEY, SAMPLE_MESSAGE, Z2_SIGNATURE)
    # assert not milagro_bls.Verify(Z1_PUBKEY, SAMPLE_MESSAGE, Z2_SIGNATURE)  # TODO: enable it when milagro is ready
    yield f'verify_infinity_pubkey_and_infinity_signature', {
        'input': {
            'pubkey': encode_hex(Z1_PUBKEY),
            'message': encode_hex(SAMPLE_MESSAGE),
            'signature': encode_hex(Z2_SIGNATURE),
        },
        'output': False,
    }


def case03_aggregate():
    for message in MESSAGES:
        sigs = [bls.Sign(privkey, message) for privkey in PRIVKEYS]
        aggregate_sig = bls.Aggregate(sigs)
        assert aggregate_sig == milagro_bls.Aggregate(sigs)
        yield f'aggregate_{encode_hex(message)}', {
            'input': [encode_hex(sig) for sig in sigs],
            'output': encode_hex(aggregate_sig),
        }

    # Invalid pubkeys -- len(pubkeys) == 0
    expect_exception(bls.Aggregate, [])
    # No signatures to aggregate. Follow IETF BLS spec, return `None` to represent INVALID.
    # https://tools.ietf.org/html/draft-irtf-cfrg-bls-signature-04#section-2.8
    yield f'aggregate_na_signatures', {
        'input': [],
        'output': None,
    }

    # Valid to aggregate G2 point at infinity
    aggregate_sig = bls.Aggregate([Z2_SIGNATURE])
    assert aggregate_sig == milagro_bls.Aggregate([Z2_SIGNATURE]) == Z2_SIGNATURE
    yield f'aggregate_infinity_signature', {
        'input': [encode_hex(Z2_SIGNATURE)],
        'output': encode_hex(aggregate_sig),
    }


def case04_fast_aggregate_verify():
    for i, message in enumerate(MESSAGES):
        privkeys = PRIVKEYS[:i + 1]
        sigs = [bls.Sign(privkey, message) for privkey in privkeys]
        aggregate_signature = bls.Aggregate(sigs)
        pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
        pubkeys_serial = [encode_hex(pubkey) for pubkey in pubkeys]

        # Valid signature
        identifier = f'{pubkeys_serial}_{encode_hex(message)}'
        assert bls.FastAggregateVerify(pubkeys, message, aggregate_signature)
        assert milagro_bls.FastAggregateVerify(pubkeys, message, aggregate_signature)
        yield f'fast_aggregate_verify_valid_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'pubkeys': pubkeys_serial,
                'message': encode_hex(message),
                'signature': encode_hex(aggregate_signature),
            },
            'output': True,
        }

        # Invalid signature -- extra pubkey
        pubkeys_extra = pubkeys + [bls.SkToPk(PRIVKEYS[-1])]
        pubkeys_extra_serial = [encode_hex(pubkey) for pubkey in pubkeys_extra]
        identifier = f'{pubkeys_extra_serial}_{encode_hex(message)}'
        assert not bls.FastAggregateVerify(pubkeys_extra, message, aggregate_signature)
        assert not milagro_bls.FastAggregateVerify(pubkeys_extra, message, aggregate_signature)
        yield f'fast_aggregate_verify_extra_pubkey_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'pubkeys': pubkeys_extra_serial,
                'message': encode_hex(message),
                'signature': encode_hex(aggregate_signature),
            },
            'output': False,
        }

        # Invalid signature -- tampered with signature
        tampered_signature = aggregate_signature[:-4] + b'\xff\xff\xff\xff'
        identifier = f'{pubkeys_serial}_{encode_hex(message)}'
        assert not bls.FastAggregateVerify(pubkeys, message, tampered_signature)
        assert not milagro_bls.FastAggregateVerify(pubkeys, message, tampered_signature)
        yield f'fast_aggregate_verify_tampered_signature_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'pubkeys': pubkeys_serial,
                'message': encode_hex(message),
                'signature': encode_hex(tampered_signature),
            },
            'output': False,
        }

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == Z1_SIGNATURE
    assert not bls.FastAggregateVerify([], message, Z2_SIGNATURE)
    assert not milagro_bls.FastAggregateVerify([], message, Z2_SIGNATURE)
    yield f'fast_aggregate_verify_na_pubkeys_and_infinity_signature', {
        'input': {
            'pubkeys': [],
            'message': encode_hex(message),
            'signature': encode_hex(Z2_SIGNATURE),
        },
        'output': False,
    }

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == 0x00...
    assert not bls.FastAggregateVerify([], message, NO_SIGNATURE)
    assert not milagro_bls.FastAggregateVerify([], message, NO_SIGNATURE)
    yield f'fast_aggregate_verify_na_pubkeys_and_na_signature', {
        'input': {
            'pubkeys': [],
            'message': encode_hex(message),
            'signature': encode_hex(NO_SIGNATURE),
        },
        'output': False,
    }

    # Invalid pubkeys and signature -- pubkeys contains point at infinity
    pubkeys = PUBKEYS.copy()
    pubkeys_with_infinity = pubkeys + [Z1_PUBKEY]
    signatures = [bls.Sign(privkey, SAMPLE_MESSAGE) for privkey in PRIVKEYS]
    aggregate_signature = bls.Aggregate(signatures)
    assert not bls.FastAggregateVerify(pubkeys_with_infinity, SAMPLE_MESSAGE, aggregate_signature)
    # TODO: enable it when milagro is ready
    # assert not milagro_bls.FastAggregateVerify(pubkeys_with_infinity, SAMPLE_MESSAGE, aggregate_signature)
    yield f'fast_aggregate_verify_infinity_pubkey', {
        'input': {
            'pubkeys': [encode_hex(pubkey) for pubkey in pubkeys_with_infinity],
            'messages': encode_hex(SAMPLE_MESSAGE),
            'signature': encode_hex(aggregate_signature),
        },
        'output': False,
    }


def case05_aggregate_verify():
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
    assert bls.AggregateVerify(pubkeys, messages, aggregate_signature)
    assert milagro_bls.AggregateVerify(pubkeys, messages, aggregate_signature)
    yield f'aggregate_verify_valid', {
        'input': {
            'pubkeys': pubkeys_serial,
            'messages': messages_serial,
            'signature': encode_hex(aggregate_signature),
        },
        'output': True,
    }

    tampered_signature = aggregate_signature[:4] + b'\xff\xff\xff\xff'
    assert not bls.AggregateVerify(pubkey, messages, tampered_signature)
    assert not milagro_bls.AggregateVerify(pubkeys, messages, tampered_signature)
    yield f'aggregate_verify_tampered_signature', {
        'input': {
            'pubkeys': pubkeys_serial,
            'messages': messages_serial,
            'signature': encode_hex(tampered_signature),
        },
        'output': False,
    }

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == Z1_SIGNATURE
    assert not bls.AggregateVerify([], [], Z2_SIGNATURE)
    assert not milagro_bls.AggregateVerify([], [], Z2_SIGNATURE)
    yield f'aggregate_verify_na_pubkeys_and_infinity_signature', {
        'input': {
            'pubkeys': [],
            'messages': [],
            'signature': encode_hex(Z2_SIGNATURE),
        },
        'output': False,
    }

    # Invalid pubkeys and signature -- len(pubkeys) == 0 and signature == 0x00...
    assert not bls.AggregateVerify([], [], NO_SIGNATURE)
    assert not milagro_bls.AggregateVerify([], [], NO_SIGNATURE)
    yield f'aggregate_verify_na_pubkeys_and_na_signature', {
        'input': {
            'pubkeys': [],
            'messages': [],
            'signature': encode_hex(NO_SIGNATURE),
        },
        'output': False,
    }

    # Invalid pubkeys and signature -- pubkeys contains point at infinity
    pubkeys_with_infinity = pubkeys + [Z1_PUBKEY]
    messages_with_sample = messages + [SAMPLE_MESSAGE]
    assert not bls.AggregateVerify(pubkeys_with_infinity, messages_with_sample, aggregate_signature)
    # TODO: enable it when milagro is ready
    # assert not milagro_bls.AggregateVerify(pubkeys_with_infinity, messages_with_sample, aggregate_signature)
    yield f'aggregate_verify_infinity_pubkey', {
        'input': {
            'pubkeys': [encode_hex(pubkey) for pubkey in pubkeys_with_infinity],
            'messages': [encode_hex(message) for message in messages_with_sample],
            'signature': encode_hex(aggregate_signature),
        },
        'output': False,
    }


def create_provider(handler_name: str,
                    test_case_fn: Callable[[], Iterable[Tuple[str, Dict[str, Any]]]]) -> gen_typing.TestProvider:

    def prepare_fn(configs_path: str) -> str:
        # Nothing to load / change in spec. Maybe in future forks.
        # Put the tests into the general config category, to not require any particular configuration.
        return 'general'

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for data in test_case_fn():
            print(data)
            (case_name, case_content) = data
            yield gen_typing.TestCase(
                fork_name=PHASE0,
                runner_name='bls',
                handler_name=handler_name,
                suite_name='small',
                case_name=case_name,
                case_fn=lambda: [('data', 'data', case_content)]
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_py_ecc()  # Py-ecc is chosen instead of Milagro, since the code is better understood to be correct.
    gen_runner.run_generator("bls", [
        create_provider('sign', case01_sign),
        create_provider('verify', case02_verify),
        create_provider('aggregate', case03_aggregate),
        create_provider('fast_aggregate_verify', case04_fast_aggregate_verify),
        create_provider('aggregate_verify', case05_aggregate_verify),
    ])
