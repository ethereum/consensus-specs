**NOTICE**: This document is a work-in-progress for researchers and implementers.

## Table of Contents
<!-- TOC -->

- [Table of Contents](#table-of-contents)
- [Constants](#constants)
- [Generalized Merkle tree index](#generalized-merkle-tree-index)
- [SSZ object to index](#ssz-object-to-index)
- [Merkle multiproofs](#merkle-multiproofs)
- [MerklePartial](#merklepartial)
    - [`SSZMerklePartial`](#sszmerklepartial)
    - [Proofs for execution](#proofs-for-execution)

<!-- /TOC -->

## Constants

| Name | Value |
| - | - |
| `LENGTH_FLAG` | `2**64 - 1` | 

## Generalized Merkle tree index

In a binary Merkle tree, we define a "generalized index" of a node as `2**depth + index`. Visually, this looks as follows:

```
    1
 2     3
4 5   6 7
   ...
```

Note that the generalized index has the convenient property that the two children of node `k` are `2k` and `2k+1`, and also that it equals the position of a node in the linear representation of the Merkle tree that's computed by this function:

```python
def merkle_tree(leaves: List[Bytes32]) -> List[Bytes32]:
    o = [0] * len(leaves) + leaves
    for i in range(len(leaves) - 1, 0, -1):
        o[i] = hash(o[i * 2] + o[i * 2 + 1])
    return o
```

We will define Merkle proofs in terms of generalized indices.

## SSZ object to index

We can describe the hash tree of any SSZ object, rooted in `hash_tree_root(object)`, as a binary Merkle tree whose depth may vary. For example, an object `{x: bytes32, y: List[uint64]}` would look as follows:

```
     root
    /    \
   x    y_root
        /    \
y_data_root  len(y)
    / \
   /\ /\
  .......
```

We can now define a concept of a "path", a way of describing a function that takes as input an SSZ object and outputs some specific (possibly deeply nested) member. For example, `foo -> foo.x` is a path, as are `foo -> len(foo.y)` and `foo -> foo.y[5].w`. We'll describe paths as lists, which can have two representations. In "human-readable form", they are `["x"]`, `["y", "__len__"]` and `["y", 5, "w"]` respectively. In "encoded form", they are lists of `uint64` values, in these cases (assuming the fields of `foo` in order are `x` then `y`, and `w` is the first field of `y[i]`) `[0]`, `[1, 2**64-1]`, `[1, 5, 0]`.

```python
def path_to_encoded_form(obj: Any, path: List[Union[str, int]]) -> List[int]:
    if len(path) == 0:
        return []
    elif isinstance(path[0], "__len__"):
        assert len(path) == 1
        return [LENGTH_FLAG]
    elif isinstance(path[0], str) and hasattr(obj, "fields"):
        return [list(obj.fields.keys()).index(path[0])] + path_to_encoded_form(getattr(obj, path[0]), path[1:])
    elif isinstance(obj, (Vector, List)):
        return [path[0]] + path_to_encoded_form(obj[path[0]], path[1:])
    else:
        raise Exception("Unknown type / path")
```

We can now define a function `get_generalized_indices(object: Any, path: List[int], root: int=1) -> List[int]` that converts an object and a path to a set of generalized indices (note that for constant-sized objects, there is only one generalized index and it only depends on the path, but for dynamically sized objects the indices may depend on the object itself too). For dynamically-sized objects, the set of indices will have more than one member because of the need to access an array's length to determine the correct generalized index for some array access.

```python
def get_generalized_indices(obj: Any, path: List[int], root: int=1) -> List[int]:
    if len(path) == 0:
        return [root]
    elif isinstance(obj, Vector):
        items_per_chunk = (32 // len(serialize(x))) if isinstance(x, int) else 1
        new_root = root * next_power_of_2(len(obj) // items_per_chunk) + path[0] // items_per_chunk
        return get_generalized_indices(obj[path[0]], path[1:], new_root)
    elif isinstance(obj, List) and path[0] == LENGTH_FLAG:
        return [root * 2 + 1]
    elif isinstance(obj, List) and isinstance(path[0], int):
        assert path[0] < len(obj)
        items_per_chunk = (32 // len(serialize(x))) if isinstance(x, int) else 1
        new_root = root * 2 * next_power_of_2(len(obj) // items_per_chunk) + path[0] // items_per_chunk
        return [root *2 + 1] + get_generalized_indices(obj[path[0]], path[1:], new_root)
    elif hasattr(obj, "fields"):
        field = list(fields.keys())[path[0]]
        new_root = root * next_power_of_2(len(fields)) + path[0]
        return get_generalized_indices(getattr(obj, field), path[1:], new_root)
    else:
        raise Exception("Unknown type / path")
```

## Merkle multiproofs

We define a Merkle multiproof as a minimal subset of nodes in a Merkle tree needed to fully authenticate that a set of nodes actually are part of a Merkle tree with some specified root, at a particular set of generalized indices. For example, here is the Merkle multiproof for positions 0, 1, 6 in an 8-node Merkle tree (i.e. generalized indices 8, 9, 14):

```
       .
   .       .
 .   *   *   .
x x . . . . x *
```

. are unused nodes, * are used nodes, x are the values we are trying to prove. Notice how despite being a multiproof for 3 values, it requires only 3 auxiliary nodes, only one node more than would be required to prove a single value. Normally the efficiency gains are not quite that extreme, but the savings relative to individual Merkle proofs are still significant. As a rule of thumb, a multiproof for k nodes at the same level of an n-node tree has size `k * (n/k + log(n/k))`.

Here is code for creating and verifying a multiproof. First, a method for computing the generalized indices of the auxiliary tree nodes that a proof of a given set of generalized indices will require:

```python
def get_proof_indices(tree_indices: List[int]) -> List[int]:
    # Get all indices touched by the proof
    maximal_indices = set()
    for i in tree_indices:
        x = i
        while x > 1:
            maximal_indices.add(x ^ 1)
            x //= 2
    maximal_indices = tree_indices + sorted(list(maximal_indices))[::-1]
    # Get indices that cannot be recalculated from earlier indices
    redundant_indices = set()
    proof = []
    for index in maximal_indices:
        if index not in redundant_indices:
            proof.append(index)
            while index > 1:
                redundant_indices.add(index)
                if (index ^ 1) not in redundant_indices:
                    break
                index //= 2
    return [i for i in proof if i not in tree_indices]
```

Generating a proof is simply a matter of taking the node of the SSZ hash tree with the union of the given generalized indices for each index given by `get_proof_indices`, and outputting the list of nodes in the same order.

Here is the verification function:

```python
def verify_multi_proof(root: Bytes32, indices: List[int], leaves: List[Bytes32], proof: List[Bytes32]) -> bool:
    tree = {}
    for index, leaf in zip(indices, leaves):
        tree[index] = leaf
    for index, proof_item in zip(get_proof_indices(indices), proof):
        tree[index] = proof_item
    index_queue = sorted(tree.keys())[:-1]
    i = 0
    while i < len(index_queue):
        index = index_queue[i]
        if index >= 2 and index ^ 1 in tree:
            tree[index // 2] = hash(tree[index - index % 2] + tree[index - index % 2 + 1])
            index_queue.append(index // 2)
        i += 1
    return (indices == []) or (1 in tree and tree[1] == root)
```

## MerklePartial

We define:

### `SSZMerklePartial`


```python
{
    "root": "bytes32",
    "indices": ["uint64"],
    "values": ["bytes32"],
    "proof": ["bytes32"]
}
```

### Proofs for execution

We define `MerklePartial(f, arg1, arg2..., focus=0)` as being a `SSZMerklePartial` object wrapping a Merkle multiproof of the set of nodes in the hash tree of the SSZ object `arg[focus]` that is needed to authenticate the parts of the object needed to compute `f(arg1, arg2...)`.

Ideally, any function which accepts an SSZ object should also be able to accept a `SSZMerklePartial` object as a substitute.
