# Tree Key Derivation Function

The tree KDF describes how to take a parent key and a child-leaf index and arrive at a child key. This is very useful as one can start with a single source of entropy and from there build out a practically unlimited number of keys. The specification can be broken into two sub-components: generating the master key, and constructing a child key from its parent. The master key is used as the root of the tree and then the tree is built in layers on top of this root.

## The Tree Structure

The key tree is defined purely through the relationship between a child-node and its parents. Starting with the root of the tree, the *master key*, a child node can be derived by knowing the parent's private key (or its hash in non-hardened cases) and the index of the child. The tree is broken up into depths which are indicated by `/` and the master node is described as `m`. The first child of the master node is therefore described as `m / 0`.

```text
      [m / 0] - [m / 0 / 0]
     /        \
    /           [m / 0 / 1]
[m] - [m / 1]
    \
     ...
      [m / i]
```

## Hardened keys

This specification provides the functionality of both *non-hardened* and *hardened* keys. A hardened key has the property that given a the parent public key and the siblings of the desired child, it is not possible to derive any information about the child key. Hardened keys should be considered the default key type and should be used unless there is an explicit reason not to do so. Hardened keys are defined as all keys with index `i >= 2**31`. For ease of notation, hardened keys are indicated with a `'` where `i'` means the key at index `i + 2**31`, thus `m / 0 / 42'` should be parsed as `m / 0 / 4294967338`.

## Specification

### Helper functions

`int_hash` is the core of this tree KDF specification. It takes in an integer (private key) and repeatedly hashes it, checking each time whether the result of the hash is less than the curve order, `52435875175126190479447740508185965837690552500527637822603658699938581184513` in the case of BLS12-381. If the result is less than the curve order, it is returned as an integer. This rejection sampling mechanism ensures a uniform distribution over the key-space under the random oracle assumption for SHA256.

```python
def int_hash(x: int) -> int:
    while True:
        hashed_int = sha256(x.to_bytes(32, byteorder='big'))
        x = int.from_bytes(hashed_int, byteorder='big')
        if x < curve_order and x != 0:
            return x

```

### Master Key Derivation

The master key is the root of the key-tree and is derived from a 256-bit seed. While this seed can be any arbitrary 256 bits, it is intended to be the output of the seed derivation process described in the [mnemonic generation specification](.mnemonic.md).

```python
def derive_master_privkey(seed: bytes) -> int:
    int_seed = int.from_bytes(seed, byteorder='big')
    return int_hash(int_seed)
```

### Child Key Derivation

The child key derivation function takes in the parent's private key and the index of the child and returns the child private key. The returned result is the modulo-sum of the hashed versions of the index and the parent key in the non-hardened case and the hashed version of that in the case of a hardened index.

```python
def derive_child_privkey(parent_privkey: int, i: int) -> int:
    i_hash = int_hash(i)
    sk_hash = int_hash(parent_privkey)
    mod_sum = (i_hash + sk_hash) % curve_order
    return mod_sum if i < 2**31 else int_hash(mod_sum)
```
