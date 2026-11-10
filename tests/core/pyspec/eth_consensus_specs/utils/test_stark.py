from dataclasses import dataclass

import pytest

from . import stark, xmss
from .test_xmss import LEAF_INDEX, MESSAGE, OTHER_PUBKEY, PUBKEY, SIGNATURE


@dataclass
class Statement:
    pubkeys: list
    leaf_index: int
    message: bytes


@pytest.fixture(autouse=True)
def active_xmss():
    old_state = xmss.xmss_active
    xmss.xmss_active = True
    yield
    xmss.xmss_active = old_state


def test_verify_aggregates():
    statements = [
        Statement([PUBKEY], LEAF_INDEX, MESSAGE),
        Statement([PUBKEY, PUBKEY], LEAF_INDEX, MESSAGE),
    ]
    proof = stark.ProveAggregates(statements, [[SIGNATURE], [SIGNATURE, SIGNATURE]])
    assert stark.VerifyAggregates(statements, proof)


def test_verify_merged_proofs():
    statement_1 = Statement([PUBKEY], LEAF_INDEX, MESSAGE)
    statement_2 = Statement([PUBKEY, PUBKEY], LEAF_INDEX, MESSAGE)
    proof_1 = stark.ProveAggregates([statement_1], [[SIGNATURE]])
    proof_2 = stark.ProveAggregates([statement_2], [[SIGNATURE, SIGNATURE]])
    proof = stark.MergeProofs([proof_1, proof_2])
    assert stark.VerifyAggregates([statement_1, statement_2], proof)
    assert not stark.VerifyAggregates([statement_2, statement_1], stark.MergeProofs([proof_1]))


def test_verify_aggregates_empty():
    assert stark.VerifyAggregates([], stark.ProveAggregates([], []))


def test_verify_aggregates_wrong_pubkey():
    statements = [Statement([OTHER_PUBKEY], LEAF_INDEX, MESSAGE)]
    proof = stark.ProveAggregates(statements, [[SIGNATURE]])
    assert not stark.VerifyAggregates(statements, proof)


def test_verify_aggregates_missing_signature():
    statements = [
        Statement([PUBKEY], LEAF_INDEX, MESSAGE),
        Statement([PUBKEY], LEAF_INDEX, MESSAGE),
    ]
    proof = stark.ProveAggregates(statements[:1], [[SIGNATURE]])
    assert not stark.VerifyAggregates(statements, proof)


def test_verify_aggregates_trailing_bytes():
    statements = [Statement([PUBKEY], LEAF_INDEX, MESSAGE)]
    proof = stark.ProveAggregates(statements, [[SIGNATURE]]) + b"\x00"
    assert not stark.VerifyAggregates(statements, proof)


def test_inactive_stubs():
    xmss.xmss_active = False
    assert stark.ProveAggregates([], []) == stark.STUB_PROOF
    assert stark.MergeProofs([]) == stark.STUB_PROOF
    statements = [Statement([OTHER_PUBKEY], LEAF_INDEX, MESSAGE)]
    assert stark.VerifyAggregates(statements, b"")
