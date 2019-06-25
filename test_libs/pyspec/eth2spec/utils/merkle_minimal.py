from .hash_function import hash


ZERO_BYTES32 = b'\x00' * 32

zerohashes = [ZERO_BYTES32]
for layer in range(1, 100):
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
    Get the next power of 2. (for 64 bit range ints).
    0 is a special case, to have non-empty defaults.
    Examples:
    0 -> 1, 1 -> 1, 2 -> 2, 3 -> 4, 32 -> 32, 33 -> 64
    """
    if v == 0:
        return 1
    return 1 << (v - 1).bit_length()


def merkleize_chunks(chunks, pad_to: int = 1):
    count = len(chunks)
    depth = max(count - 1, 0).bit_length()
    max_depth = max(depth, (pad_to - 1).bit_length())
    tmp = [None for _ in range(max_depth + 1)]

    def merge(h, i):
        j = 0
        while True:
            if i & (1 << j) == 0:
                if i == count and j < depth:
                    h = hash(h + zerohashes[j])  # keep going if we are complementing the void to the next power of 2
                else:
                    break
            else:
                h = hash(tmp[j] + h)
            j += 1
        tmp[j] = h

    # merge in leaf by leaf.
    for i in range(count):
        merge(chunks[i], i)

    # complement with 0 if empty, or if not the right power of 2
    if 1 << depth != count:
        merge(zerohashes[0], count)

    # the next power of two may be smaller than the ultimate virtual size, complement with zero-hashes at each depth.
    for j in range(depth, max_depth):
        tmp[j + 1] = hash(tmp[j] + zerohashes[j])

    return tmp[max_depth]
