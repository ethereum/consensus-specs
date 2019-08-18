from .ssz_gen_index import (
    GeneralizedIndex, generalized_index_sibling, generalized_index_parent,
    generalized_index_child, get_generalized_index_length, get_generalized_index_bit
)
from typing import Sequence
from .ssz_typing import Bytes32


def get_branch_indices(tree_index: GeneralizedIndex) -> Sequence[GeneralizedIndex]:
    """
    Get the generalized indices of the sister chunks along the path from the chunk with the
    given tree index to the root.
    """
    o = [generalized_index_sibling(tree_index)]
    while o[-1] > 1:
        o.append(generalized_index_sibling(generalized_index_parent(o[-1])))
    return o[:-1]


def get_helper_indices(indices: Sequence[GeneralizedIndex]) -> Sequence[GeneralizedIndex]:
    """
    Get the generalized indices of all "extra" chunks in the tree needed to prove the chunks with the given
    generalized indices. Note that the decreasing order is chosen deliberately to ensure equivalence to the
    order of hashes in a regular single-item Merkle proof in the single-item case.
    """
    all_indices = set()
    for index in indices:
        all_indices = all_indices.union(set(get_branch_indices(index) + [index]))

    return sorted([
        x for x in all_indices if not (
                generalized_index_child(x, 0) in all_indices and
                generalized_index_child(x, 1) in all_indices
        )
        and not (x in indices)
    ], reverse=True)


def verify_merkle_proof(leaf: Bytes32, proof: Sequence[Bytes32], index: GeneralizedIndex, root: Bytes32) -> bool:
    assert len(proof) == get_generalized_index_length(index)
    for i, h in enumerate(proof):
        if get_generalized_index_bit(index, i):
            leaf = hash(h + leaf)
        else:
            leaf = hash(leaf + h)
    return leaf == root


def verify_merkle_multiproof(leaves: Sequence[Bytes32], proof: Sequence[Bytes32], indices: Sequence[GeneralizedIndex],
                             root: Bytes32) -> bool:
    assert len(leaves) == len(indices)
    helper_indices = get_helper_indices(indices)
    assert len(proof) == len(helper_indices)
    objects = {
        **{index: node for index, node in zip(indices, leaves)},
        **{index: node for index, node in zip(helper_indices, proof)}
    }
    keys = sorted(objects.keys(), reverse=True)
    pos = 0
    while pos < len(keys):
        k = keys[pos]
        if k in objects and k ^ 1 in objects and k // 2 not in objects:
            objects[k // 2] = hash(objects[(k | 1) ^ 1] + objects[k | 1])
            keys.append(k // 2)
        pos += 1
    return objects[1] == root
