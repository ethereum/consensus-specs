"""
BLS test vectors generator
Usage:
    "python tgen_bls path/to/output.yml"
"""

# Standard library
import sys
from typing import Tuple

# Third-party
import yaml

# Ethereum
from eth_utils import int_to_big_endian, big_endian_to_int

# Local imports
from py_ecc import bls


def int_to_hex(n: int) -> str:
    return '0x' + int_to_big_endian(n).hex()


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
    b'\x00' * 32,
    b'\x56' * 32,
    b'\xab' * 32,
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
            int_to_hex(fq2.coeffs[0]),
            int_to_hex(fq2.coeffs[1]),
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
    return [int_to_hex(z1), int_to_hex(z2)]


if __name__ == '__main__':

    # Order not preserved - https://github.com/yaml/pyyaml/issues/110
    metadata = {
        'title': 'BLS signature and aggregation tests',
        'summary': 'Test vectors for BLS signature',
        'test_suite': 'bls',
        'fork': 'phase0-0.5.0',
    }

    case01_message_hash_G2_uncompressed = []
    for msg in MESSAGES:
        for domain in DOMAINS:
            case01_message_hash_G2_uncompressed.append({
                'input': {'message': '0x' + msg.hex(), 'domain': int_to_hex(domain)},
                'output': hash_message(msg, domain)
            })

    case02_message_hash_G2_compressed = []
    for msg in MESSAGES:
        for domain in DOMAINS:
            case02_message_hash_G2_compressed.append({
                'input': {'message': '0x' + msg.hex(), 'domain': int_to_hex(domain)},
                'output': hash_message_compressed(msg, domain)
            })

    case03_private_to_public_key = []
    #  Used in later cases
    pubkeys = [bls.privtopub(privkey) for privkey in PRIVKEYS]
    #  Used in public key aggregation
    pubkeys_serial = ['0x' + pubkey.hex() for pubkey in pubkeys]
    case03_private_to_public_key = [
        {
            'input': int_to_hex(privkey),
            'output': pubkey_serial,
        }
        for privkey, pubkey_serial in zip(PRIVKEYS, pubkeys_serial)
    ]

    case04_sign_messages = []
    sigs = []  # used in verify
    for privkey in PRIVKEYS:
        for message in MESSAGES:
            for domain in DOMAINS:
                sig = bls.sign(message, privkey, domain)
                case04_sign_messages.append({
                    'input': {
                        'privkey': int_to_hex(privkey),
                        'message': '0x' + message.hex(),
                        'domain': int_to_hex(domain)
                    },
                    'output': '0x' + sig.hex()
                })
                sigs.append(sig)

    # TODO: case05_verify_messages: Verify messages signed in case04
    # It takes too long, empty for now

    case06_aggregate_sigs = []
    for domain in DOMAINS:
        for message in MESSAGES:
            sigs = []
            for privkey in PRIVKEYS:
                sig = bls.sign(message, privkey, domain)
                sigs.append(sig)
            case06_aggregate_sigs.append({
                'input': ['0x' + sig.hex() for sig in sigs],
                'output': '0x' + bls.aggregate_signatures(sigs).hex(),
            })

    case07_aggregate_pubkeys = [
        {
            'input': pubkeys_serial,
            'output': '0x' + bls.aggregate_pubkeys(pubkeys).hex(),
        }
    ]

    # TODO
    # Aggregate verify

    # TODO
    # Proof-of-possession

    with open(sys.argv[2] + "test_bls.yml", 'w') as outfile:
        # Dump at top level
        yaml.dump(metadata, outfile, default_flow_style=False)
        # default_flow_style will unravel "ValidatorRecord" and "committee" line,
        # exploding file size
        yaml.dump(
            {'case01_message_hash_G2_uncompressed': case01_message_hash_G2_uncompressed},
            outfile,
        )
        yaml.dump(
            {'case02_message_hash_G2_compressed': case02_message_hash_G2_compressed},
            outfile,
        )
        yaml.dump(
            {'case03_private_to_public_key': case03_private_to_public_key},
            outfile,
        )
        yaml.dump({'case04_sign_messages': case04_sign_messages}, outfile)

        # Too time consuming to generate
        # yaml.dump({'case05_verify_messages': case05_verify_messages}, outfile)
        yaml.dump({'case06_aggregate_sigs': case06_aggregate_sigs}, outfile)
        yaml.dump({'case07_aggregate_pubkeys': case07_aggregate_pubkeys}, outfile)
