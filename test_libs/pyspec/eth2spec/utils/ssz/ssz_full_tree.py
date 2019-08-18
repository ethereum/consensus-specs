from .ssz_zero_hashes import zerohashes
from .ssz_math import previous_power_of_two


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
    layer_count = previous_power_of_two(pad_to)
    if len(values) == 0:
        return zerohashes[layer_count]
    return calc_merkle_tree_from_leaves(values, layer_count)[-1][0]


def get_merkle_proof(tree, item_index, tree_len=None):
    proof = []
    for i in range(tree_len if tree_len is not None else len(tree)):
        subindex = (item_index // 2**i) ^ 1
        proof.append(tree[i][subindex] if subindex < len(tree[i]) else zerohashes[i])
    return proof
