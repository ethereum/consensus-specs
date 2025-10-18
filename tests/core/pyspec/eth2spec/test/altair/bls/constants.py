###############################################################################
# Precomputed constants
###############################################################################


def _hex_to_int(x: str) -> int:
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
    _hex_to_int(
        "0x00000000000000000000000000000000263dbd792f5b1be47ed85f8938c0f29586af0d3ac7b977f21c278fe1462040e3"
    ),
    _hex_to_int(
        "0x0000000000000000000000000000000047b8192d77bf871b62e87859d653922725724a5c031afeabc60bcef5ff665138"
    ),
    _hex_to_int(
        "0x00000000000000000000000000000000328388aff0d4a5b7dc9205abd374e7e98f3cd9f3418edb4eafda5fb16473d216"
    ),
]

ZERO_PUBKEY = b"\x00" * 48
G1_POINT_AT_INFINITY = b"\xc0" + b"\x00" * 47

ZERO_SIGNATURE = b"\x00" * 96
G2_POINT_AT_INFINITY = b"\xc0" + b"\x00" * 95

ZERO_PRIVKEY = 0
ZERO_PRIVKEY_BYTES = b"\x00" * 32
