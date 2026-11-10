from eth_consensus_specs.test.helpers.forks import is_post_pq
from eth_consensus_specs.utils import bls, xmss


def sign(spec, privkey, signing_root, slot, leaf_name):
    """
    Sign ``signing_root`` with BLS, or from PQ onwards with XMSS at the leaf named
    by ``leaf_name``: a reserved leaf, the attestation leaf of the epoch of
    ``slot``, or the leaf offset of ``slot``.
    """
    if is_post_pq(spec):
        # The stub ignores the leaf
        leaf_index = 0
        if xmss.xmss_active:
            if leaf_name.startswith("RESERVED_LEAF_"):
                leaf_index = getattr(spec, leaf_name)
            elif leaf_name == "ATTESTATION":
                epoch = spec.compute_epoch_at_slot(slot)
                leaf_index = spec.compute_xmss_attestation_leaf_index(epoch)
            else:
                leaf_index = spec.compute_xmss_leaf_index(slot, getattr(spec, leaf_name))
        return spec.XMSSSignature(xmss.Sign(privkey, leaf_index, signing_root))
    return bls.Sign(privkey, signing_root)


def aggregate(spec, signatures):
    return bls.Aggregate(signatures)


def get_empty_aggregate(spec):
    """
    The aggregate of no signatures.
    """
    return spec.G2_POINT_AT_INFINITY


def get_placeholder_signature(spec):
    """
    The signature placed where there is nothing to sign, such as a self-build
    bid.
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
