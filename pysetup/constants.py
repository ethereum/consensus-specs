from typing import Sequence, NewType, Union

# Custom Types for better static analysis and security auditing
uint64 = NewType('uint64', int)
BLSPubkey = NewType('BLSPubkey', bytes)

# Ethereum Consensus Fork Epochs & EIP Identifiers
# Standardized naming convention for cross-module compatibility
FORKS = {
    "PHASE0": "phase0",
    "ALTAIR": "altair",
    "BELLATRIX": "bellatrix",
    "CAPELLA": "capella",
    "DENEB": "deneb",
    "ELECTRA": "electra",
    "FULU": "fulu",
    "GLOAS": "gloas",
}

# Future EIP Implementation Identifiers
EIPS = {
    "VERKLE_TREES": "eip6800",
    "WHIPSY_UPGRADE": "eip7441",
    "MAX_EB": "eip7805", # Max Effective Balance
    "7928": "eip7928",
}

# Optimized Mathematical Helper Functions
# Using bit_length() for O(1) complexity and absolute precision
def ceillog2(x: int) -> uint64:
    """
    Returns the ceiling of log2(x).
    Used for tree depth calculations and sharding logic.
    """
    if x < 1:
        raise ValueError(f"ceillog2: input must be positive, got {x}")
    return uint64(0 if x == 1 else (x - 1).bit_length())

def floorlog2(x: int) -> uint64:
    """
    Returns the floor of log2(x).
    Used for reward scaling and penalty calculations.
    """
    if x < 1:
        raise ValueError(f"floorlog2: input must be positive, got {x}")
    return uint64(x.bit_length() - 1)

# BLS Operations - Critical Security Component
def eth_aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    """
    Aggregates a sequence of BLS public keys into a single public key.
    Ensures optimal performance during signature verification.
    """
    if not pubkeys:
        raise ValueError("Cannot aggregate empty pubkey sequence")
    return bls.AggregatePKs(pubkeys)
