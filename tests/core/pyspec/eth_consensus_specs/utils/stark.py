"""
A reference stand-in for STARK proofs of XMSS aggregates.
"""

from eth_consensus_specs.utils import xmss

STUB_PROOF = b""


def ProveAggregates(statements, aggregates):
    """
    Prove ``aggregates``, one for each of ``statements``, by concatenation, a
    stand-in for a STARK. When XMSS is inactive, a stub proof is returned.
    """
    if not xmss.xmss_active:
        return STUB_PROOF
    assert len(statements) == len(aggregates)
    return b"".join(bytes(aggregate) for aggregate in aggregates)


def VerifyAggregates(statements, proof):
    """
    Check that ``proof`` holds, for each of ``statements`` in turn, an aggregate
    that ``xmss.AggregateVerify`` accepts. When XMSS is inactive, every proof is
    accepted.
    """
    if not xmss.xmss_active:
        return True
    proof = bytes(proof)
    offset = 0
    for statement in statements:
        size = len(statement.pubkeys) * xmss.SIGNATURE_SIZE
        aggregate = proof[offset : offset + size]
        if len(aggregate) != size:
            return False
        if not xmss.AggregateVerify(
            statement.pubkeys, statement.leaf_index, statement.message, aggregate
        ):
            return False
        offset += size
    return offset == len(proof)
