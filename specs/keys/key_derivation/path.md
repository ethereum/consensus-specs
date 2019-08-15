# Path / Tree Traversal

The *path* specifies which key from the key-tree to utilise for what purpose. It is to be interpreted in tandem with the [Tree KDF specification](./tree_kdf.md) as that specification describes how to build out a tree of keys and this one how to traverse that tree and which keys to use for what.

## Specification

### Path

```text
m / purpose' / coin_type' /  account' / other'
```

#### Notation

The notation used within the path is specified within the [Tree KDF specification](./tree_kdf.md), but is summarized again below for convenience.

* `m` Denotes the master node (or root) of the tree
* `/` Separates the tree into depths, thus `i / j` signifies that `j` is a child of `i`
* `'` Indicates that hardened key derivation is used at this level

### Purpose

The purpose is set to 12381' which is the hardened form of the name of the new curve (BLS12-381). It is necessary to define a new purpose here (as opposed to 44 or 43) as the new tree derivation strategy is not compatible with existing standards.

### Coin Type

The `coin_type` here reflects the (hardened) coin number for an individual coin. Ethereum, in this case, is number 60.

### Account

Account is a (hardened) field that provides the ability for a user to have distinct sets of keys for different purposes, if they so choose. This is the level at which different accounts for a single user are to be implemented, unless a better reason is found.

### Other

This level is designed to provide a set of related (and co-derivable given the chain-code) keys that can be used for any purpose. It is required to support this level in the tree, although, for many purposes it will remain `0 '`. Additionally, although not recommended, implementors MAY choose to make use of non-hardened keys at this level if their is a specific need for doing so.
