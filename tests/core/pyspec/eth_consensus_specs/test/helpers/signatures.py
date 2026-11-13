from eth_consensus_specs.test.helpers.forks import is_post_pq
from eth_consensus_specs.utils import bls, xmss


def sign(spec, privkey, signing_root, slot, leaf_name):
    """
    Sign ``signing_root`` with BLS, or from PQ onwards with XMSS at the leaf named
    by ``leaf_name``: the first reserved leaf, the attestation leaf of the epoch
    of ``slot``, or the leaf offset of ``slot``.
    """
    if is_post_pq(spec):
        # The first reserved leaf, which stubbed verification also accepts for
        # any other message
        leaf_index = 0
        if xmss.xmss_active and leaf_name != "RESERVED":
            if leaf_name == "ATTESTATION":
                epoch = spec.compute_epoch_at_slot(slot)
                leaf_index = spec.compute_xmss_attestation_leaf_index(epoch)
            else:
                leaf_index = spec.compute_xmss_leaf_index(slot, getattr(spec, leaf_name))
        return spec.XMSSSignature(xmss.Sign(privkey, leaf_index, signing_root))
    return bls.Sign(privkey, signing_root)


def get_execution_payload_bid_signature(spec, state, bid, privkey):
    """
    Sign ``bid`` with the key of its builder.
    """
    if is_post_pq(spec):
        # Any leaf reserved for bids passes stubbed verification
        leaf_index = spec.XMSS_RESERVED_LEAVES + spec.XMSS_ATTESTATION_LEAVES
        return spec.get_execution_payload_bid_signature(state, bid, privkey, leaf_index)
    return spec.get_execution_payload_bid_signature(state, bid, privkey)


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
