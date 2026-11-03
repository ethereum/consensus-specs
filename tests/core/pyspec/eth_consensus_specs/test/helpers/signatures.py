from eth_consensus_specs.test.helpers.forks import is_post_pq
from eth_consensus_specs.utils import bls, xmss


def sign(spec, privkey, signing_root, slot, leaf_offset):
    """
    Sign ``signing_root`` with BLS, or from PQ onwards with XMSS at the leaf of
    ``slot`` for the ``leaf_offset`` constant named by its string.
    """
    if is_post_pq(spec):
        leaf_index = spec.compute_xmss_leaf_index(slot, getattr(spec, leaf_offset))
        return spec.XMSSSignature(xmss.Sign(privkey, leaf_index, signing_root))
    return bls.Sign(privkey, signing_root)


def aggregate(spec, signatures):
    if is_post_pq(spec):
        return spec.XMSSAggregateSignature(data=xmss.Aggregate(signatures))
    return bls.Aggregate(signatures)


def get_empty_aggregate(spec):
    """
    The aggregate of no signatures.
    """
    if is_post_pq(spec):
        return spec.XMSSAggregateSignature()
    return spec.G2_POINT_AT_INFINITY


def get_placeholder_signature(spec):
    """
    The signature placed where there is nothing to sign, such as a self-build
    bid or a pending deposit created by the protocol.
    """
    if is_post_pq(spec):
        return spec.XMSSSignature()
    return spec.bls.G2_POINT_AT_INFINITY


def get_unsigned_signature(spec):
    """
    The zero signature of an unsigned message.
    """
    if is_post_pq(spec):
        return spec.XMSSSignature()
    return spec.BLSSignature()
