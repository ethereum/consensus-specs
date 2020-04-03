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

from eth2spec.test.context import PHASE0

def hash(x):
    return sha256(x).digest()


F2Q_COEFF_LEN = 48
G2_COMPRESSED_Z_LEN = 48
DST = bls.G2ProofOfPossession.DST


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

PRIVKEYS = [
    # Curve order is 256 so private keys are 32 bytes at most.
    # Also not all integers is a valid private key, so using pre-generated keys
    hex_to_int('0x00000000000000000000000000000000263dbd792f5b1be47ed85f8938c0f29586af0d3ac7b977f21c278fe1462040e3'),
    hex_to_int('0x0000000000000000000000000000000047b8192d77bf871b62e87859d653922725724a5c031afeabc60bcef5ff665138'),
    hex_to_int('0x00000000000000000000000000000000328388aff0d4a5b7dc9205abd374e7e98f3cd9f3418edb4eafda5fb16473d216'),
]


def case01_sign():
    for privkey in PRIVKEYS:
        for message in MESSAGES:
            sig = bls.G2ProofOfPossession.Sign(privkey, message)
            identifier = f'{int_to_hex(privkey)}_{encode_hex(message)}'
            yield f'sign_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'privkey': int_to_hex(privkey),
                    'message': encode_hex(message),
                },
                'output': encode_hex(sig)
            }


def case02_verify():
    for i, privkey in enumerate(PRIVKEYS):
        for message in MESSAGES:
            # Valid signature
            signature = bls.G2ProofOfPossession.Sign(privkey, message)
            pubkey = bls.G2ProofOfPossession.PrivToPub(privkey)
            identifier = f'{encode_hex(pubkey)}_{encode_hex(message)}'
            yield f'verify_valid_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'pubkey': encode_hex(pubkey),
                    'message': encode_hex(message),
                    'signature': encode_hex(signature),
                },
                'output': True,
            }

            # Invalid signatures -- wrong pubkey
            wrong_pubkey = bls.G2ProofOfPossession.PrivToPub(PRIVKEYS[(i + 1) % len(PRIVKEYS)])
            identifier = f'{encode_hex(wrong_pubkey)}_{encode_hex(message)}'
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
            yield f'verify_tampered_signature_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'pubkey': encode_hex(pubkey),
                    'message': encode_hex(message),
                    'signature': encode_hex(tampered_signature),
                },
                'output': False,
            }


def case03_aggregate():
    for message in MESSAGES:
        sigs = [bls.G2ProofOfPossession.Sign(privkey, message) for privkey in PRIVKEYS]
        yield f'aggregate_{encode_hex(message)}', {
            'input': [encode_hex(sig) for sig in sigs],
            'output': encode_hex(bls.G2ProofOfPossession.Aggregate(sigs)),
        }


def case04_fast_aggregate_verify():
    for i, message in enumerate(MESSAGES):
        privkeys = PRIVKEYS[:i + 1]
        sigs = [bls.G2ProofOfPossession.Sign(privkey, message) for privkey in privkeys]
        aggregate_signature = bls.G2ProofOfPossession.Aggregate(sigs)
        pubkeys = [bls.G2ProofOfPossession.PrivToPub(privkey) for privkey in privkeys]
        pubkeys_serial = [encode_hex(pubkey) for pubkey in pubkeys]

        # Valid signature
        identifier = f'{pubkeys_serial}_{encode_hex(message)}'
        yield f'fast_aggregate_verify_valid_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'pubkeys': pubkeys_serial,
                'message': encode_hex(message),
                'signature': encode_hex(aggregate_signature),
            },
            'output': True,
        }

        # Invalid signature -- extra pubkey
        pubkeys_extra = pubkeys + [bls.G2ProofOfPossession.PrivToPub(PRIVKEYS[-1])]
        pubkeys_extra_serial = [encode_hex(pubkey) for pubkey in pubkeys_extra]
        identifier = f'{pubkeys_extra_serial}_{encode_hex(message)}'
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
        yield f'fast_aggregate_verify_tampered_signature_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'pubkeys': pubkeys_serial,
                'message': encode_hex(message),
                'signature': encode_hex(tampered_signature),
            },
            'output': False,
        }


def case05_aggregate_verify():
    pairs = []
    sigs = []
    for privkey, message in zip(PRIVKEYS, MESSAGES):
        sig = bls.G2ProofOfPossession.Sign(privkey, message)
        pubkey = bls.G2ProofOfPossession.PrivToPub(privkey)
        pairs.append({
            'pubkey': encode_hex(pubkey),
            'message': encode_hex(message),
        })
        sigs.append(sig)

    aggregate_signature = bls.G2ProofOfPossession.Aggregate(sigs)
    yield f'aggregate_verify_valid', {
        'input': {
            'pairs': pairs,
            'signature': encode_hex(aggregate_signature),
        },
        'output': True,
    }

    tampered_signature = aggregate_signature[:4] + b'\xff\xff\xff\xff'
    yield f'aggregate_verify_tampered_signature', {
        'input': {
            'pairs': pairs,
            'signature': encode_hex(tampered_signature),
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
    gen_runner.run_generator("bls", [
        create_provider('sign', case01_sign),
        create_provider('verify', case02_verify),
        create_provider('aggregate', case03_aggregate),
        create_provider('fast_aggregate_verify', case04_fast_aggregate_verify),
        create_provider('aggregate_verify', case05_aggregate_verify),
    ])
