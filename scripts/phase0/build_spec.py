import sys
import function_puller


def build_spec(sourcefile, outfile):
    code_lines = []

    code_lines.append("from build.phase0.utils.minimal_ssz import *")
    code_lines.append("from build.phase0.utils.bls_stub import *")
    for i in (1, 2, 3, 4, 8, 32, 48, 96):
        code_lines.append("def int_to_bytes%d(x): return x.to_bytes(%d, 'little')" % (i, i))
    code_lines.append("SLOTS_PER_EPOCH = 64")  # stub, will get overwritten by real var
    code_lines.append("def slot_to_epoch(x): return x // SLOTS_PER_EPOCH")

    code_lines.append("""
from typing import (
    Any,
    Callable,
    List,
    NewType,
    Tuple,
)


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
# Monkey patch validator shuffling cache
_get_shuffling = get_shuffling
shuffling_cache = {}
def get_shuffling(seed: Bytes32,
                  validators: List[Validator],
                  epoch: Epoch) -> List[List[ValidatorIndex]]:

    param_hash = (seed, hash_tree_root(validators, [Validator]), epoch)

    if param_hash in shuffling_cache:
        # print("Cache hit, epoch={0}".format(epoch))
        return shuffling_cache[param_hash]
    else:
        # print("Cache miss, epoch={0}".format(epoch))
        ret = _get_shuffling(seed, validators, epoch)
        shuffling_cache[param_hash] = ret
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
