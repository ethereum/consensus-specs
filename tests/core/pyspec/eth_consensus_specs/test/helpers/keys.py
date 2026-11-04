from functools import cache
from hashlib import sha256

from eth_consensus_specs.utils import bls, xmss

# Enough keys for 256 builders
builder_privkeys = [2**15 + i + 1 for i in range(256)]
builder_pubkeys = [bls.SkToPk(privkey) for privkey in builder_privkeys]
builder_pubkey_to_privkey = {
    pubkey: privkey for privkey, pubkey in zip(builder_privkeys, builder_pubkeys, strict=False)
}

# Enough keys for 256 validators per slot in worst-case epoch length
privkeys = [i + 1 for i in range(32 * 256 + 1)]
pubkeys = [bls.SkToPk(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys, strict=False)}

# XMSS key generation takes minutes, so the XMSS keys are placeholders
xmss_builder_pubkeys = [xmss.StubPk(privkey) for privkey in builder_privkeys]
xmss_pubkeys = [xmss.StubPk(privkey) for privkey in privkeys]

# Depth of the VRF trees whose roots validators register as VRF data
VRF_TREE_DEPTH = 31


@cache
def get_vrf_tree_nodes(index):
    """
    The nodes of the placeholder VRF tree of the validator at ``index``, from its
    leaf up to its root. Every leaf of the tree is the same, so the node at each
    level is also the sibling of every node at that level.
    """
    nodes = [sha256(b"vrf leaf" + index.to_bytes(8, "little")).digest()]
    for _ in range(VRF_TREE_DEPTH):
        nodes.append(sha256(nodes[-1] + nodes[-1]).digest())
    return tuple(nodes)


def get_vrf_data(index):
    """
    The VRF data of the validator at ``index``, the root of its VRF tree.
    """
    return get_vrf_tree_nodes(index)[-1]


def get_vrf_proof(index):
    """
    The VRF proof of the validator at ``index`` for any slot, the leaf of its VRF
    tree followed by the leaf's Merkle branch.
    """
    nodes = get_vrf_tree_nodes(index)
    return (nodes[0], *nodes[:VRF_TREE_DEPTH])
