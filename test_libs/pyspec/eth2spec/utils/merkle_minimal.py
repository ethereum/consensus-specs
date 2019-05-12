from .hash_function import hash


ZERO_BYTES32 = b'\x00' * 32

zerohashes = [ZERO_BYTES32]
for layer in range(1, 32):
    zerohashes.append(hash(zerohashes[layer - 1] + zerohashes[layer - 1]))


# Compute a Merkle root of a right-zerobyte-padded 2**32 sized tree
def calc_merkle_tree_from_leaves(values):
    values = list(values)
    tree = [values[::]]
    for h in range(32):
        if len(values) % 2 == 1:
            values.append(zerohashes[h])
        values = [hash(values[i] + values[i + 1]) for i in range(0, len(values), 2)]
        tree.append(values[::])
    return tree


def get_merkle_root(values):
    return calc_merkle_tree_from_leaves(values)[-1][0]


def get_merkle_proof(tree, item_index):
    proof = []
    for i in range(32):
        subindex = (item_index // 2**i) ^ 1
        proof.append(tree[i][subindex] if subindex < len(tree[i]) else zerohashes[i])
    return proof


def next_power_of_two(v: int) -> int:
    """
    Get the next power of 2. (for 64 bit range ints)
    Examples:
    0 -> 0, 1 -> 1, 2 -> 2, 3 -> 4, 32 -> 32, 33 -> 64
    """
    # effectively fill the bitstring (1 less, do not want to  with ones, then increment for next power of 2.
    v -= 1
    v |= v >> (1 << 0)
    v |= v >> (1 << 1)
    v |= v >> (1 << 2)
    v |= v >> (1 << 3)
    v |= v >> (1 << 4)
    v |= v >> (1 << 5)
    v += 1
    return v


def merkleize_chunks(chunks):
    tree = chunks[::]
    margin = next_power_of_two(len(chunks)) - len(chunks)
    tree.extend([ZERO_BYTES32] * margin)
    tree = [ZERO_BYTES32] * len(tree) + tree
    for i in range(len(tree) // 2 - 1, 0, -1):
        tree[i] = hash(tree[i * 2] + tree[i * 2 + 1])
    return tree[1]
