import sys
import function_puller


def build_phase0_spec(sourcefile, outfile):
    code_lines = []
    code_lines.append("""
from typing import (
    Any,
    Dict,
    List,
    NewType,
    Tuple,
)
from eth2spec.utils.ssz.ssz_impl import (
    hash_tree_root,
    signing_root,
)
from eth2spec.utils.ssz.ssz_typing import (
    uint8, uint16, uint32, uint64, uint128, uint256,
    Container, Vector, BytesN
)
from eth2spec.utils.bls_stub import (
    bls_aggregate_pubkeys,
    bls_verify,
    bls_verify_multiple,
)
from eth2spec.utils.hash_function import hash

# Note: 'int' type defaults to being interpreted as a uint64 by SSZ implementation.
Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64
ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64

Bytes4 = BytesN[4]
Bytes32 = BytesN[32]
Bytes48 = BytesN[48]
Bytes96 = BytesN[96]

""")

    code_lines += function_puller.get_spec(sourcefile)

    code_lines.append("""
# Monkey patch validator compute committee code
_compute_committee = compute_committee
committee_cache = {}


def compute_committee(indices: List[ValidatorIndex], seed: Bytes32, index: int, count: int) -> List[ValidatorIndex]:
    param_hash = (hash_tree_root(indices), seed, index, count)

    if param_hash in committee_cache:
        return committee_cache[param_hash]
    else:
        ret = _compute_committee(indices, seed, index, count)
        committee_cache[param_hash] = ret
        return ret


# Monkey patch hash cache
_hash = hash
hash_cache = {}


def hash(x):
    if x in hash_cache:
        return hash_cache[x]
    else:
        ret = _hash(x)
        hash_cache[x] = ret
        return ret


# Access to overwrite spec constants based on configuration
def apply_constants_preset(preset: Dict[str, Any]):
    global_vars = globals()
    for k, v in preset.items():
        global_vars[k] = v

    # Deal with derived constants
    global_vars['GENESIS_EPOCH'] = slot_to_epoch(GENESIS_SLOT)

    # Initialize SSZ types again, to account for changed lengths
    init_SSZ_types()
""")

    with open(outfile, 'w') as out:
        out.write("\n".join(code_lines))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: <source phase0> <output phase0 pyspec>")
    build_phase0_spec(sys.argv[1], sys.argv[2])

