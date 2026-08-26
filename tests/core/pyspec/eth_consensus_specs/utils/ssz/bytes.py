"""
The fixed-width byte arrays the consensus specs name.

The library ships no application-specific widths, so the specs' own are declared
here. It also relates two byte arrays only by inheritance, which would leave the
several names the specs give the same 32 bytes refusing to be compared with one
another. These compare by content instead.
"""

from ssz.byte_arrays import ByteVector
from ssz.merkleization import Root


class BytesN(ByteVector):
    def __eq__(self, other: object) -> bool:
        """Equal when the bytes are equal, whatever each side is called."""
        if isinstance(other, (ByteVector, bytes, bytearray)):
            return bytes(self) == bytes(other)
        return super().__eq__(other)

    def __ne__(self, other: object) -> bool:
        """The negation of the above, so both directions agree."""
        if isinstance(other, (ByteVector, bytes, bytearray)):
            return bytes(self) != bytes(other)
        return super().__ne__(other)

    def __hash__(self) -> int:
        """Hash by content, so equal byte arrays of any width hash alike."""
        return hash(bytes(self))


class Bytes1(BytesN):
    LENGTH = 1


class Bytes4(BytesN):
    LENGTH = 4


class Bytes8(BytesN):
    LENGTH = 8


class Bytes20(BytesN):
    LENGTH = 20


class Bytes31(BytesN):
    LENGTH = 31


# Descends from the library's root as well, because `hash_tree_root` is a method
# on every value and the library's returns a `Root`. Left unrelated, that root
# would be a sibling of every `Bytes32` it is compared against or keyed beside.
class Bytes32(BytesN, Root):
    LENGTH = 32


class Bytes48(BytesN):
    LENGTH = 48


class Bytes96(BytesN):
    LENGTH = 96
