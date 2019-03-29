import sys
import function_puller


def build_spec(sourcefile, outfile):
    code_lines = []
    code_lines.append("""
    
from typing import (
    Any,
    Callable,
    List,
    NewType,
    Tuple,
)
from pyspec.utils.minimal_ssz import *
from pyspec.utils.bls_stub import *


    """)
    for i in (1, 2, 3, 4, 8, 32, 48, 96):
        code_lines.append("def int_to_bytes%d(x): return x.to_bytes(%d, 'little')" % (i, i))

    code_lines.append("""
# stub, will get overwritten by real var
SLOTS_PER_EPOCH = 64


def slot_to_epoch(x): return x // SLOTS_PER_EPOCH


Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64
ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64
Bytes32 = NewType('Bytes32', bytes)  # bytes32
BLSPubkey = NewType('BLSPubkey', bytes)  # bytes48
BLSSignature = NewType('BLSSignature', bytes)  # bytes96
Any = None
Store = None
    """)

    code_lines += function_puller.get_lines(sourcefile)

    code_lines.append("""
# Monkey patch validator get committee code
_compute_committee = compute_committee
committee_cache = {}


def compute_committee(validator_indices: List[ValidatorIndex],
                      seed: Bytes32,
                      index: int,
                      total_committees: int) -> List[ValidatorIndex]:

    param_hash = (hash_tree_root(validator_indices), seed, index, total_committees)

    if param_hash in committee_cache:
        # print("Cache hit, epoch={0}".format(epoch))
        return committee_cache[param_hash]
    else:
        # print("Cache miss, epoch={0}".format(epoch))
        ret = _compute_committee(validator_indices, seed, index, total_committees)
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
    """)

    with open(outfile, 'w') as out:
        out.write("\n".join(code_lines))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Error: spec source and outfile must defined")
    build_spec(sys.argv[1], sys.argv[2])
