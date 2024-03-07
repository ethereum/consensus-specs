# Definitions in context.py
PHASE0 = 'phase0'
ALTAIR = 'altair'
BELLATRIX = 'bellatrix'
CAPELLA = 'capella'
DENEB = 'deneb'
EIP6110 = 'eip6110'
EIP7002 = 'eip7002'
WHISK = 'whisk'
EIP7594 = 'eip7594'



# The helper functions that are used when defining constants
CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS = '''
def ceillog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"ceillog2 accepts only positive values, x={x}")
    return uint64((x - 1).bit_length())


def floorlog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"floorlog2 accepts only positive values, x={x}")
    return uint64(x.bit_length() - 1)
'''


OPTIMIZED_BLS_AGGREGATE_PUBKEYS = '''
def eth_aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    return bls.AggregatePKs(pubkeys)
'''


ETH2_SPEC_COMMENT_PREFIX = "eth2spec:"
