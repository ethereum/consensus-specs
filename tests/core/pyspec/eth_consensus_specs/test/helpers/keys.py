from functools import cache
from hashlib import sha256

from eth_consensus_specs.test.helpers.forks import is_post_pq
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
builder_pubkey_to_privkey.update(zip(xmss_builder_pubkeys, builder_privkeys, strict=True))
pubkey_to_privkey.update(zip(xmss_pubkeys, privkeys, strict=True))

# Depth of the VRF trees whose roots validators register
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


def get_vrf_root(index):
    """
    The VRF root of the validator at ``index``.
    """
    return get_vrf_tree_nodes(index)[-1]


def get_vrf_proof(index):
    """
    The VRF proof of the validator at ``index`` for any slot, the leaf of its VRF
    tree followed by the leaf's Merkle branch.
    """
    nodes = get_vrf_tree_nodes(index)
    return (nodes[0], *nodes[:VRF_TREE_DEPTH])


def get_request_pubkey(spec, pubkey):
    """
    The 48-byte public key that an execution layer request names for
    ``pubkey``. From PQ onwards it is the XMSS public key after
    ``XMSS_DEPOSIT_PREFIX``, and a BLS test key stands for the XMSS key that
    shares its private key.
    """
    if not is_post_pq(spec):
        return pubkey
    if len(pubkey) == 48:
        privkey = pubkey_to_privkey.get(pubkey, builder_pubkey_to_privkey.get(pubkey))
        if privkey is None:
            return pubkey
        pubkey = xmss.StubPk(privkey)
    return spec.Bytes48(spec.XMSS_DEPOSIT_PREFIX + pubkey)


def get_pubkey_from_request(spec, request_pubkey):
    """
    The public key of the validator or builder that ``request_pubkey`` names.
    """
    if is_post_pq(spec):
        return spec.XMSSPubkey(request_pubkey[16:])
    return request_pubkey


def get_deposit_pubkey(spec, request_pubkey):
    """
    The public key of the validator or builder that a deposit naming
    ``request_pubkey`` is for.
    """
    if is_post_pq(spec):
        return spec.compute_deposit_pubkey(request_pubkey)
    return request_pubkey
