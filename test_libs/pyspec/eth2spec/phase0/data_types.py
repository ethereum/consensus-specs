from typing import NewType

Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64
ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64
Bytes8 = NewType('Bytes8', bytes)  # bytes8
Bytes32 = NewType('Bytes32', bytes)  # bytes32
Bytes48 = NewType('Bytes48', bytes)  # bytes48
Bytes96 = NewType('Bytes96', bytes)  # bytes96
BLSPubkey = NewType('BLSPubkey', bytes)  # bytes48
BLSSignature = NewType('BLSSignature', bytes)  # bytes96
