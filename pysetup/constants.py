# Definitions in context.py
PHASE0 = "phase0"
ALTAIR = "altair"
BELLATRIX = "bellatrix"
CAPELLA = "capella"
DENEB = "deneb"
ELECTRA = "electra"
FULU = "fulu"
GLOAS = "gloas"
EIP6800 = "eip6800"
EIP7441 = "eip7441"
EIP7805 = "eip7805"
EIP7928 = "eip7928"
EIP8025 = "eip8025"
EIP8148 = "eip8148"


# The helper functions that are used when defining constants
CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS = """
def ceillog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"ceillog2 accepts only positive values, x={x}")
    return uint64((x - 1).bit_length())


def floorlog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"floorlog2 accepts only positive values, x={x}")
    return uint64(x.bit_length() - 1)
"""


OPTIMIZED_BLS_AGGREGATE_PUBKEYS = """
def eth_aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    return bls.AggregatePKs(pubkeys)
"""
