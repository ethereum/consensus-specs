"""
A reference stand-in for STARK proofs of XMSS signatures.
"""

from eth_consensus_specs.utils import xmss

STUB_PROOF = b""


def ProveAggregates(statements, signatures):
    """
    Prove ``signatures``, for each of ``statements`` the signatures of its
    public keys in order, by concatenation, a stand-in for a STARK. When XMSS is
    inactive, a stub proof is returned.
    """
    if not xmss.xmss_active:
        return STUB_PROOF
    assert len(statements) == len(signatures)
    for statement, statement_signatures in zip(statements, signatures, strict=True):
        assert len(statement.pubkeys) == len(statement_signatures)
    return b"".join(
        bytes(signature)
        for statement_signatures in signatures
        for signature in statement_signatures
    )


def MergeProofs(proofs):
    """
    Merge ``proofs`` of lists of statements into one proof of their
    concatenation, by concatenation. When XMSS is inactive, a stub proof is
    returned.
    """
    if not xmss.xmss_active:
        return STUB_PROOF
    return b"".join(bytes(proof) for proof in proofs)


def VerifyAggregates(statements, proof):
    """
    Check that ``proof`` holds, for each of ``statements`` in turn and each of
    its public keys in order, a signature that ``xmss.Verify`` accepts. When
    XMSS is inactive, every proof is accepted.
    """
    if not xmss.xmss_active:
        return True
    proof = bytes(proof)
    offset = 0
    for statement in statements:
        for pubkey in statement.pubkeys:
            signature = proof[offset : offset + xmss.SIGNATURE_SIZE]
            if len(signature) != xmss.SIGNATURE_SIZE:
                return False
            if not xmss.Verify(pubkey, statement.leaf_index, statement.message, signature):
                return False
            offset += xmss.SIGNATURE_SIZE
    return offset == len(proof)
