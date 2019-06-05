def set_bitfield_bit(bitfield, i):
    """
    Set the bit in ``bitfield`` at position ``i`` to ``1``.
    """
    byte_index = i // 8
    bit_index = i % 8
    return (
        bitfield[:byte_index] +
        bytes([bitfield[byte_index] | (1 << bit_index)]) +
        bitfield[byte_index + 1:]
    )
