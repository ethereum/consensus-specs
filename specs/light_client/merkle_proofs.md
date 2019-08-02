# Merkle proof formats

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Merkle proof formats](#merkle-proof-formats)
   - [Table of contents](#table-of-contents)
   - [Constants](#constants)
   - [Generalized Merkle tree index](#generalized-merkle-tree-index)
   - [SSZ object to index](#ssz-object-to-index)
   - [Merkle multiproofs](#merkle-multiproofs)
   - [MerklePartial](#merklepartial)
       - [`SSZMerklePartial`](#sszmerklepartial)
       - [Proofs for execution](#proofs-for-execution)

<!-- /TOC -->

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
    padded_length = next_power_of_2(len(leaves))
    o = [ZERO_HASH] * padded_length + leaves + [ZERO_HASH] * (padded_length - len(leaves))
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
def item_length(typ: SSZType) -> int:
    """
    Returns the number of bytes in a basic type, or 32 (a full hash) for compound types.
    """
    if issubclass(typ, BasicValue):
        return typ.byte_len
    else:
        return 32
        
        
def get_elem_type(typ: ComplexType, index: Union[int, str]) -> Type:
    """
    Returns the type of the element of an object of the given type with the given index
    or member variable name (eg. `7` for `x[7]`, `"foo"` for `x.foo`)
    """
    return typ.get_fields()[index] if issubclass(typ, Container) else typ.elem_type        


def chunk_count(typ: SSZType) -> int:
    """
    Returns the number of hashes needed to represent the top-level elements in the given type
    (eg. `x.foo` or `x[7]` but not `x[7].bar` or `x.foo.baz`). In all cases except lists/vectors
    of basic types, this is simply the number of top-level elements, as each element gets one
    hash. For lists/vectors of basic types, it is often fewer because multiple basic elements
    can be packed into one 32-byte chunk.
    """
    if issubclass(typ, BasicValue):
        return 1
    elif issubclass(typ, Bits):
        return (typ.length + 255) // 256
    elif issubclass(typ, Elements):
        return (typ.length * item_length(typ.elem_type) + 31) // 32
    elif issubclass(typ, Container):
        return len(typ.get_fields())
    else:
        raise Exception(f"Type not supported: {typ}")


def get_item_position(typ: SSZType, index: Union[int, str]) -> Tuple[int, int, int]:
    """
    Returns three variables: (i) the index of the chunk in which the given element of the item is
    represented, (ii) the starting byte position within the chunk, (iii) the ending byte position within the chunk. For example for
    a 6-item list of uint64 values, index=2 will return (0, 16, 24), index=5 will return (1, 8, 16)
    """
    if issubclass(typ, Elements):
        start = index * item_length(typ.elem_type)
        return start // 32, start % 32, start % 32 + item_length(typ.elem_type)
    elif issubclass(typ, Container):
        return typ.get_field_names().index(index), 0, item_length(get_elem_type(typ, index))
    else:
        raise Exception("Only lists/vectors/containers supported")


def get_generalized_index(typ: Type, path: List[Union[int, str]]) -> GeneralizedIndex:
    """
    Converts a path (eg. `[7, "foo", 3]` for `x[7].foo[3]`, `[12, "bar", "__len__"]` for
    `len(x[12].bar)`) into the generalized index representing its position in the Merkle tree.
    """
    root = 1
    for p in path:
        assert not issubclass(typ, BasicValue)  # If we descend to a basic type, the path cannot continue further
        if p == '__len__':
            typ, root = uint64, root * 2 + 1 if issubclass(typ, (List, Bytes)) else None
        else:
            pos, _, _ = get_item_position(typ, p)
            root = root * (2 if issubclass(typ, (List, Bytes)) else 1) * next_power_of_two(chunk_count(typ)) + pos
            typ = get_elem_type(typ, p)
    return root
```

### Helpers for generalized indices

#### `concat_generalized_indices`

```python
def concat_generalized_indices(*indices: Sequence[GeneralizedIndex]) -> GeneralizedIndex:
    """
    Given generalized indices i1 for A -> B, i2 for B -> C .... i_n for Y -> Z, returns
    the generalized index for A -> Z.
    """
    o = GeneralizedIndex(1)
    for i in indices:
        o = o * get_previous_power_of_2(i) + i
    return o
```

#### `get_generalized_index_length`

```python
def get_generalized_index_length(index: GeneralizedIndex) -> int:
   """
   Returns the length of a path represented by a generalized index.
   """
   return log(index)
```

#### `get_generalized_index_bit`

```python
def get_generalized_index_bit(index: GeneralizedIndex, position: int) -> bool:
   """
   Returns the given bit of a generalized index.
   """
   return (index & (1 << position)) > 0
```

#### `generalized_index_sibling`

```python
def generalized_index_sibling(index: GeneralizedIndex) -> GeneralizedIndex:
   return index ^ 1
```

#### `generalized_index_child`

```python
def generalized_index_child(index: GeneralizedIndex, right_side: bool) -> GeneralizedIndex:
   return index * 2 + right_side
```

#### `generalized_index_parent`

```python
def generalized_index_parent(index: GeneralizedIndex) -> GeneralizedIndex:
   return index // 2
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

First, we provide a method for computing the generalized indices of the auxiliary tree nodes that a proof of a given set of generalized indices will require:

```python
def get_branch_indices(tree_index: GeneralizedIndex) -> List[GeneralizedIndex]:
    """
    Get the generalized indices of the sister chunks along the path from the chunk with the
    given tree index to the root.
    """
    o = [generalized_index_sibling(tree_index)]
    while o[-1] > 1:
        o.append(generalized_index_sibling(generalized_index_parent(o[-1])))
    return o[:-1]

def get_helper_indices(indices: List[GeneralizedIndex]) -> List[GeneralizedIndex]:
    """
    Get the generalized indices of all "extra" chunks in the tree needed to prove the chunks with the given
    generalized indices. Note that the decreasing order is chosen deliberately to ensure equivalence to the
    order of hashes in a regular single-item Merkle proof in the single-item case.
    """
    all_indices = set()
    for index in indices:
        all_indices = all_indices.union(set(get_branch_indices(index) + [index]))
    
    return sorted([
        x for x in all_indices if not
        (generalized_index_child(x, 0) in all_indices and generalized_index_child(x, 1) in all_indices) and not
        (x in indices)
    ])[::-1]
```

Now we provide the Merkle proof verification functions. First, for single item proofs:

```python
def verify_merkle_proof(leaf: Hash, proof: Sequence[Hash], index: GeneralizedIndex, root: Hash) -> bool:
    assert len(proof) == get_generalized_index_length(index)
    for i, h in enumerate(proof):
        if get_generalized_index_bit(index, i):
            leaf = hash(h + leaf)
        else:
            leaf = hash(leaf + h)
    return leaf == root
```

Now for multi-item proofs:

```python
def verify_merkle_multiproof(leaves: Sequence[Hash], proof: Sequence[Hash], indices: Sequence[GeneralizedIndex], root: Hash) -> bool:
    assert len(leaves) == len(indices)
    helper_indices = get_helper_indices(indices)
    assert len(proof) == len(helper_indices)
    objects = {
        **{index:node for index, node in zip(indices, leaves)},
        **{index:node for index, node in zip(helper_indices, proof)}
    }
    keys = sorted(objects.keys())[::-1]
    pos = 0
    while pos < len(keys):
        k = keys[pos]
        if k in objects and k ^ 1 in objects and k // 2 not in objects:
            objects[k // 2] = hash(objects[k & -2] + objects[k | 1])
            keys.append(k // 2)
        pos += 1
    return objects[1] == root
```

Note that the single-item proof is a special case of a multi-item proof; a valid single-item proof verifies correctly when put into the multi-item verification function (making the natural trivial changes to input arguments, `index -> [index]` and `leaf -> [leaf]`).
