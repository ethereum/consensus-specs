from functools import cache

from eth_hash.auto import keccak

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
# A full VRF tree takes billions of hashes, so the placeholder VRF trees only
# commit to secrets for the first 2**VRF_SUBTREE_DEPTH slots
VRF_SUBTREE_DEPTH = 12


def get_vrf_secret(slot):
    """
    The secret for ``slot`` of every placeholder VRF tree.
    """
    return keccak(b"vrf secret" + slot.to_bytes(8, "little"))


@cache
def get_vrf_subtree_levels():
    """
    The levels of the subtree that every placeholder VRF tree has on its left,
    from its leaves up to its root. Each leaf commits to the secret for its slot.
    """
    leaves = [
        keccak(b"VRF_LEAF" + get_vrf_secret(slot) + slot.to_bytes(8, "little"))
        for slot in range(2**VRF_SUBTREE_DEPTH)
    ]
    levels = [leaves]
    while len(levels[-1]) > 1:
        level = levels[-1]
        levels.append([keccak(level[i] + level[i + 1]) for i in range(0, len(level), 2)])
    return levels


@cache
def get_vrf_upper_branch(index):
    """
    The siblings above the shared subtree in the placeholder VRF tree of the
    validator at ``index``. They differ between validators, so each validator
    has its own VRF root.
    """
    return tuple(
        keccak(b"vrf node" + index.to_bytes(8, "little") + height.to_bytes(8, "little"))
        for height in range(VRF_SUBTREE_DEPTH, VRF_TREE_DEPTH)
    )


def get_vrf_root(index):
    """
    The VRF root of the validator at ``index``.
    """
    node = get_vrf_subtree_levels()[-1][0]
    for sibling in get_vrf_upper_branch(index):
        node = keccak(node + sibling)
    return node


def get_vrf_proof(index, slot):
    """
    The VRF proof of the validator at ``index`` for ``slot``, the secret for the
    slot followed by the Merkle branch of the slot's leaf.
    """
    assert slot < 2**VRF_SUBTREE_DEPTH
    levels = get_vrf_subtree_levels()
    branch = [levels[height][(slot >> height) ^ 1] for height in range(VRF_SUBTREE_DEPTH)]
    return (get_vrf_secret(slot), *branch, *get_vrf_upper_branch(index))


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
