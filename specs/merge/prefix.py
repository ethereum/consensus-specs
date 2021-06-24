from typing import Protocol
_temp = __import__("eth2spec.phase0", globals(), locals(), [PRESET_NAME])
phase0: Any = getattr(_temp, PRESET_NAME)
from eth2spec.utils.ssz.ssz_typing import Bytes20, ByteList, ByteVector, uint256, Union

MAX_BYTES_PER_OPAQUE_TRANSACTION = uint64(2**20)
