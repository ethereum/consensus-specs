"""
BLS test vectors generator
"""

from typing import Tuple

from eth_utils import (
    to_tuple, int_to_big_endian
)
from gen_base import gen_runner, gen_suite, gen_typing

from py_ecc import bls


F2Q_COEFF_LEN = 48
G2_COMPRESSED_Z_LEN = 48


def int_to_hex(n: int, byte_length: int=None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b'\x00')
    return '0x' + byte_value.hex()


def hex_to_int(x: str) -> int:
    return int(x, 16)


# Note: even though a domain is only an uint64,
# To avoid issues with YAML parsers that are limited to 53-bit (JS language limit)
# It is serialized as an hex string as well.
DOMAINS = [
    0,
    1,
    1234,
    2**32-1,
    2**64-1
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


def hash_message(msg: bytes,
                 domain: int) ->Tuple[Tuple[str, str], Tuple[str, str], Tuple[str, str]]:
    """
    Hash message
    Input:
        - Message as bytes
        - domain as uint64
    Output:
        - Message hash as a G2 point
    """
    return [
        [
            int_to_hex(fq2.coeffs[0], F2Q_COEFF_LEN),
            int_to_hex(fq2.coeffs[1], F2Q_COEFF_LEN),
        ]
        for fq2 in bls.utils.hash_to_G2(msg, domain)
    ]


def hash_message_compressed(msg: bytes, domain: int) -> Tuple[str, str]:
    """
    Hash message
    Input:
        - Message as bytes
        - domain as uint64
    Output:
        - Message hash as a compressed G2 point
    """
    z1, z2 = bls.utils.compress_G2(bls.utils.hash_to_G2(msg, domain))
    return [int_to_hex(z1, G2_COMPRESSED_Z_LEN), int_to_hex(z2, G2_COMPRESSED_Z_LEN)]


@to_tuple
def case01_message_hash_G2_uncompressed():
    for msg in MESSAGES:
        for domain in DOMAINS:
            yield {
                'input': {
                    'message': '0x' + msg.hex(),
                    'domain': int_to_hex(domain)
                },
                'output': hash_message(msg, domain)
            }

@to_tuple
def case02_message_hash_G2_compressed():
    for msg in MESSAGES:
        for domain in DOMAINS:
            yield {
                'input': {
                    'message': '0x' + msg.hex(),
                    'domain': int_to_hex(domain)
                },
                'output': hash_message_compressed(msg, domain)
            }

@to_tuple
def case03_private_to_public_key():
    pubkeys = [bls.privtopub(privkey) for privkey in PRIVKEYS]
    pubkeys_serial = ['0x' + pubkey.hex() for pubkey in pubkeys]
    for privkey, pubkey_serial in zip(PRIVKEYS, pubkeys_serial):
        yield {
            'input': int_to_hex(privkey),
            'output': pubkey_serial,
        }

@to_tuple
def case04_sign_messages():
    for privkey in PRIVKEYS:
        for message in MESSAGES:
            for domain in DOMAINS:
                sig = bls.sign(message, privkey, domain)
                yield {
                    'input': {
                        'privkey': int_to_hex(privkey),
                        'message': '0x' + message.hex(),
                        'domain': int_to_hex(domain)
                    },
                    'output': '0x' + sig.hex()
                }

# TODO: case05_verify_messages: Verify messages signed in case04
# It takes too long, empty for now


@to_tuple
def case06_aggregate_sigs():
    for domain in DOMAINS:
        for message in MESSAGES:
            sigs = [bls.sign(message, privkey, domain) for privkey in PRIVKEYS]
            yield {
                'input': ['0x' + sig.hex() for sig in sigs],
                'output': '0x' + bls.aggregate_signatures(sigs).hex(),
            }

@to_tuple
def case07_aggregate_pubkeys():
    pubkeys = [bls.privtopub(privkey) for privkey in PRIVKEYS]
    pubkeys_serial = ['0x' + pubkey.hex() for pubkey in pubkeys]
    yield {
        'input': pubkeys_serial,
        'output': '0x' + bls.aggregate_pubkeys(pubkeys).hex(),
    }


# TODO
# Aggregate verify

# TODO
# Proof-of-possession


def bls_msg_hash_uncompressed_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("g2_uncompressed", "msg_hash_g2_uncompressed", gen_suite.render_suite(
        title="BLS G2 Uncompressed msg hash",
        summary="BLS G2 Uncompressed msg hash",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="bls",
        handler="msg_hash_uncompressed",
        test_cases=case01_message_hash_G2_uncompressed()))


def bls_msg_hash_compressed_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("g2_compressed", "msg_hash_g2_compressed", gen_suite.render_suite(
        title="BLS G2 Compressed msg hash",
        summary="BLS G2 Compressed msg hash",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="bls",
        handler="msg_hash_compressed",
        test_cases=case02_message_hash_G2_compressed()))



def bls_priv_to_pub_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("priv_to_pub", "priv_to_pub", gen_suite.render_suite(
        title="BLS private key to pubkey",
        summary="BLS Convert private key to public key",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="bls",
        handler="priv_to_pub",
        test_cases=case03_private_to_public_key()))


def bls_sign_msg_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("sign_msg", "sign_msg", gen_suite.render_suite(
        title="BLS sign msg",
        summary="BLS Sign a message",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="bls",
        handler="sign_msg",
        test_cases=case04_sign_messages()))


def bls_aggregate_sigs_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("aggregate_sigs", "aggregate_sigs", gen_suite.render_suite(
        title="BLS aggregate sigs",
        summary="BLS Aggregate signatures",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="bls",
        handler="aggregate_sigs",
        test_cases=case06_aggregate_sigs()))


def bls_aggregate_pubkeys_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    return ("aggregate_pubkeys", "aggregate_pubkeys", gen_suite.render_suite(
        title="BLS aggregate pubkeys",
        summary="BLS Aggregate public keys",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        runner="bls",
        handler="aggregate_pubkeys",
        test_cases=case07_aggregate_pubkeys()))


if __name__ == "__main__":
    gen_runner.run_generator("bls", [
        bls_msg_hash_compressed_suite,
        bls_msg_hash_uncompressed_suite,
        bls_priv_to_pub_suite,
        bls_sign_msg_suite,
        bls_aggregate_sigs_suite,
        bls_aggregate_pubkeys_suite
    ])
