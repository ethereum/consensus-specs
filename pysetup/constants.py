# Definitions in context.py
PHASE0 = "phase0"
ALTAIR = "altair"
BELLATRIX = "bellatrix"
CAPELLA = "capella"
DENEB = "deneb"
ELECTRA = "electra"
FULU = "fulu"
GLOAS = "gloas"
HEZE = "heze"
EIP7928 = "eip7928"
EIP8025 = "eip8025"


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


OPTIMIZED_BALANCE_WEIGHTED_SELECTION = """
_effective_balance_cache: LRU = LRU(size=4)

def _get_effective_balances(state: BeaconState) -> list[int]:
    key = _cached_htr(state.validators)
    if key in _effective_balance_cache:
        return _effective_balance_cache[key]
    balances = [int(v.effective_balance) for v in state.validators]
    _effective_balance_cache[key] = balances
    return balances


def compute_balance_weighted_selection(
    state: BeaconState,
    indices: Sequence[ValidatorIndex],
    seed: Bytes32,
    size: uint64,
    shuffle_indices: bool,
) -> Sequence[ValidatorIndex]:
    total = int(len(indices))
    assert total > 0

    all_balances = _get_effective_balances(state)
    effective_balances = [all_balances[int(index)] for index in indices]
    max_effective_balance = int(MAX_EFFECTIVE_BALANCE_ELECTRA)
    MAX_RANDOM_VALUE = 2**16 - 1
    seed = bytes(seed)

    selected: List[ValidatorIndex] = []
    i = 0
    prev_hash_group = -1
    random_bytes = b""

    while len(selected) < size:
        next_index = i % total
        if shuffle_indices:
            next_index = int(compute_shuffled_index(uint64(next_index), uint64(total), seed))
        candidate_index = indices[next_index]

        hash_group = i // 16
        if hash_group != prev_hash_group:
            random_bytes = hash(seed + uint_to_bytes(uint64(hash_group)))
            prev_hash_group = hash_group
        offset = i % 16 * 2
        random_value = int.from_bytes(random_bytes[offset:offset + 2], 'little')

        if effective_balances[next_index] * MAX_RANDOM_VALUE >= max_effective_balance * random_value:
            selected.append(candidate_index)

        i += 1

    return selected
"""
