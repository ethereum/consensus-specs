"""
BLS test vectors generator
"""

from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import (
    encode_hex,
    int_to_big_endian,
)
from gen_base import gen_runner, gen_typing

from py_ecc import bls
from hashlib import sha256


def hash(x):
    return sha256(x).digest()


F2Q_COEFF_LEN = 48
G2_COMPRESSED_Z_LEN = 48
DST = b'BLS_SIG_BLS12381G2-SHA256-SSWU-RO_POP_'


def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b'\x00')
    return encode_hex(byte_value)


def int_to_bytes(n: int, byte_length: int = None) -> bytes:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b'\x00')
    return byte_value


def hex_to_int(x: str) -> int:
    return int(x, 16)


DOMAINS = [
    b'\x00\x00\x00\x00\x00\x00\x00\x00',
    b'\x00\x00\x00\x00\x00\x00\x00\x01',
    b'\x01\x00\x00\x00\x00\x00\x00\x00',
    b'\x80\x00\x00\x00\x00\x00\x00\x00',
    b'\x01\x23\x45\x67\x89\xab\xcd\xef',
    b'\xff\xff\xff\xff\xff\xff\xff\xff'
]

MESSAGES = [
    bytes(b'\x00' * 32),
    bytes(b'\x56' * 32),
    bytes(b'\xab' * 32),
]

PRIVKEYS = [
    # Curve order is 256 so private keys are 32 bytes at most.
    # Also not all integers is a valid private key, so using pre-generated keys
    hex_to_int('0x00000000000000000000000000000000263dbd792f5b1be47ed85f8938c0f29586af0d3ac7b977f21c278fe1462040e3'),
    hex_to_int('0x0000000000000000000000000000000047b8192d77bf871b62e87859d653922725724a5c031afeabc60bcef5ff665138'),
    hex_to_int('0x00000000000000000000000000000000328388aff0d4a5b7dc9205abd374e7e98f3cd9f3418edb4eafda5fb16473d216'),
]


def hash_message(msg: bytes) -> Tuple[Tuple[str, str], Tuple[str, str], Tuple[str, str]]:
    """
    Hash message
    Input:
        - Message as bytes32
    Output:
        - Message hash as a G2 point
    """
    return [
        [
            int_to_hex(fq2.coeffs[0], F2Q_COEFF_LEN),
            int_to_hex(fq2.coeffs[1], F2Q_COEFF_LEN),
        ]
        for fq2 in bls.hash_to_curve.hash_to_G2(msg, DST)
    ]


def hash_message_compressed(msg: bytes) -> Tuple[str, str]:
    """
    Hash message
    Input:
        - Message as bytes32
    Output:
        - Message hash as a compressed G2 point
    """
    z1, z2 = bls.point_compression.compress_G2(bls.hash_to_curve.hash_to_G2(msg, DST))
    return [int_to_hex(z1, G2_COMPRESSED_Z_LEN), int_to_hex(z2, G2_COMPRESSED_Z_LEN)]


def case01_message_hash_G2_uncompressed():
    for msg in MESSAGES:
        yield f'uncom_g2_hash_{encode_hex(msg)}', {
            'input': {
                'message': encode_hex(msg),
            },
            'output': hash_message(msg)
        }


def case02_message_hash_G2_compressed():
    for msg in MESSAGES:
        yield f'com_g2_hash_{encode_hex(msg)}', {
            'input': {
                'message': encode_hex(msg),
            },
            'output': hash_message_compressed(msg)
        }


def case03_private_to_public_key():
    pubkeys = [bls.G2Basic.PrivToPub(privkey) for privkey in PRIVKEYS]
    pubkeys_serial = ['0x' + pubkey.hex() for pubkey in pubkeys]
    for privkey, pubkey_serial in zip(PRIVKEYS, pubkeys_serial):
        yield f'priv_to_pub_{int_to_hex(privkey)}', {
            'input': int_to_hex(privkey),
            'output': pubkey_serial,
        }


def case04_sign_messages():
    for privkey in PRIVKEYS:
        for message in MESSAGES:
            sig = bls.G2ProofOfPossession.Sign(privkey, message)
            full_name = f'{int_to_hex(privkey)}_{encode_hex(message)}'
            yield f'sign_msg_case_{(hash(bytes(full_name, "utf-8"))[:8]).hex()}', {
                'input': {
                    'privkey': int_to_hex(privkey),
                    'message': encode_hex(message),
                },
                'output': encode_hex(sig)
            }


# TODO: case05_verify_messages: Verify messages signed in case04
# It takes too long, empty for now


def case06_aggregate_sigs():
    for message in MESSAGES:
        sigs = [bls.G2ProofOfPossession.Sign(privkey, message) for privkey in PRIVKEYS]
        yield f'agg_sigs_{encode_hex(message)}', {
            'input': [encode_hex(sig) for sig in sigs],
            'output': encode_hex(bls.G2ProofOfPossession.Aggregate(sigs)),
        }


def case07_aggregate_pubkeys():
    pubkeys = [bls.G2Basic.PrivToPub(privkey) for privkey in PRIVKEYS]
    pubkeys_serial = [encode_hex(pubkey) for pubkey in pubkeys]
    yield f'agg_pub_keys', {
        'input': pubkeys_serial,
        'output': encode_hex(bls.G2ProofOfPossession._AggregatePKs(pubkeys)),
    }


# TODO
# Aggregate verify

# TODO
# Proof-of-possession


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
                fork_name='phase0',
                runner_name='bls',
                handler_name=handler_name,
                suite_name='small',
                case_name=case_name,
                case_fn=lambda: [('data', 'data', case_content)]
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    gen_runner.run_generator("bls", [
        create_provider('msg_hash_uncompressed', case01_message_hash_G2_uncompressed),
        create_provider('msg_hash_compressed', case02_message_hash_G2_compressed),
        create_provider('priv_to_pub', case03_private_to_public_key),
        create_provider('sign_msg', case04_sign_messages),
        create_provider('aggregate_sigs', case06_aggregate_sigs),
        create_provider('aggregate_pubkeys', case07_aggregate_pubkeys),
    ])
