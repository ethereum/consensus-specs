from remerkleable.tree import gindex_bit_iter


def build_proof(anchor, leaf_index):
    if leaf_index <= 1:
        return []  # Nothing to prove / invalid index
    node = anchor
    proof = []
    # Walk down, top to bottom to the leaf
    bit_iter, _ = gindex_bit_iter(leaf_index)
    for bit in bit_iter:
        # Always take the opposite hand for the proof.
        # 1 = right as leaf, thus get left
        if bit:
            proof.append(node.get_left().merkle_root())
            node = node.get_right()
        else:
            proof.append(node.get_right().merkle_root())
            node = node.get_left()

    return list(reversed(proof))
