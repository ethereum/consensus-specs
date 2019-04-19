from .hash_function import hash


zerohashes = [b'\x00' * 32]
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
