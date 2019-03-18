import sys
import function_puller

code_lines = []

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


code_lines += function_puller.get_lines(sys.argv[1])

print(open(sys.argv[2]).read())
print(open(sys.argv[3]).read())

for line in code_lines:
    print(line)

print(open(sys.argv[4]).read())
print(open(sys.argv[5]).read())
