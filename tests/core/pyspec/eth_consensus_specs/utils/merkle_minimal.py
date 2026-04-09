from math import log2

from eth_consensus_specs.utils.hash_function import hash

ZERO_BYTES32 = b"\x00" * 32

zerohashes = [ZERO_BYTES32]
for layer in range(1, 100):
    zerohashes.append(hash(zerohashes[layer - 1] + zerohashes[layer - 1]))


def calc_merkle_tree_from_leaves(values, layer_count=32):
    values = list(values)
    tree = [values[::]]
    for h in range(layer_count):
        if len(values) % 2 == 1:
            values.append(zerohashes[h])
        values = [hash(values[i] + values[i + 1]) for i in range(0, len(values), 2)]
        tree.append(values[::])
    return tree


def get_merkle_tree(values, pad_to=None):
    layer_count = (len(values) - 1).bit_length() if pad_to is None else (pad_to - 1).bit_length()
    if len(values) == 0:
        return zerohashes[layer_count]
    return calc_merkle_tree_from_leaves(values, layer_count)


def get_merkle_root(values, pad_to=1):
    if pad_to == 0:
        return zerohashes[0]
    layer_count = int(log2(pad_to))
    if len(values) == 0:
        return zerohashes[layer_count]
    return calc_merkle_tree_from_leaves(values, layer_count)[-1][0]


def get_merkle_proof(tree, item_index, tree_len=None):
    proof = []
    for i in range(tree_len if tree_len is not None else len(tree)):
        subindex = (item_index // 2**i) ^ 1
        proof.append(tree[i][subindex] if subindex < len(tree[i]) else zerohashes[i])
    return proof


def merkleize_chunks(chunks, limit=None):
    # If no limit is defined, we are just merkleizing chunks (e.g. SSZ container).
    if limit is None:
        limit = len(chunks)

    count = len(chunks)
    # See if the input is within expected size.
    # If not, a list-limit is set incorrectly, or a value is unexpectedly large.
    assert count <= limit

    if limit == 0:
        return zerohashes[0]

    depth = max(count - 1, 0).bit_length()
    max_depth = (limit - 1).bit_length()
    tmp = [None for _ in range(max_depth + 1)]

    def merge(h, i):
        j = 0
        while True:
            if i & (1 << j) == 0:
                if i == count and j < depth:
                    h = hash(
                        h + zerohashes[j]
                    )  # keep going if we are complementing the void to the next power of 2
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
