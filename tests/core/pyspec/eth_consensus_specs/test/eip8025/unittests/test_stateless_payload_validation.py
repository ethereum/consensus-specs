from types import SimpleNamespace

from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_eip8025_and_later,
)


def make_root(spec, value):
    return spec.Root(bytes([value]) * 32)


def make_block(spec, parent_root, slot):
    return SimpleNamespace(parent_root=parent_root, slot=spec.Slot(slot))


def make_proof(spec, proof_type, origin_root, origin_slot, head_root, head_slot):
    return spec.ExecutionProof(
        proof_data=spec.ProgressiveByteList(b"\x01"),
        proof_type=spec.ProofType(proof_type),
        claim=spec.ExecutionProofClaim(
            origin=spec.ExecutionCheckpoint(
                slot=spec.Slot(origin_slot),
                beacon_block_root=origin_root,
            ),
            head=spec.ExecutionCheckpoint(
                slot=spec.Slot(head_slot),
                beacon_block_root=head_root,
            ),
        ),
    )


def make_store(blocks, proofs):
    return SimpleNamespace(blocks=blocks, execution_proofs=proofs)


@with_eip8025_and_later(features=["stateless"])
@spec_test
@single_phase
def test_eip8025_feature_metadata(spec, eip8025_features):
    assert eip8025_features == frozenset({"stateless"})
    assert spec.EIP8025_FEATURES == {
        "prover": {
            "tag": "eip8025-prover",
            "status": "optional",
        },
        "stateless": {
            "tag": "eip8025-experimental",
            "status": "experimental",
        },
    }


@with_eip8025_and_later(features=["stateless"])
@spec_test
@single_phase
def test_stateless_bootstrap_requires_two_distinct_proof_types(spec, eip8025_features):
    assert "stateless" in eip8025_features
    head_root = make_root(spec, 1)
    head = make_block(spec, spec.Root(), 10)
    first_proof = make_proof(spec, 1, head_root, 10, head_root, 10)
    second_proof = make_proof(spec, 2, head_root, 10, head_root, 10)

    store = make_store({head_root: head}, {})
    opt_store = SimpleNamespace(
        optimistic_roots={head_root},
        head_block_root=head_root,
    )
    statuses = {head_root: spec.PAYLOAD_STATUS_NOT_VALIDATED}

    store.execution_proofs[head_root] = {first_proof.proof_type: first_proof}
    assert not spec.promote_payload_validation_status(store, opt_store, statuses, head_root)
    assert statuses[head_root] == spec.PAYLOAD_STATUS_NOT_VALIDATED

    store.execution_proofs[head_root][second_proof.proof_type] = second_proof
    assert spec.promote_payload_validation_status(store, opt_store, statuses, head_root)
    assert statuses[head_root] == spec.PAYLOAD_STATUS_VALID
    assert head_root not in opt_store.optimistic_roots
    assert opt_store.head_block_root == head_root


@with_eip8025_and_later(features=["stateless"])
@spec_test
@single_phase
def test_stateless_recursive_promotion_uses_root_ancestry(spec, eip8025_features):
    assert "stateless" in eip8025_features
    valid_root = make_root(spec, 1)
    intermediate_root = make_root(spec, 2)
    head_root = make_root(spec, 3)
    unrelated_head = make_root(spec, 4)
    blocks = {
        valid_root: make_block(spec, spec.Root(), 10),
        intermediate_root: make_block(spec, valid_root, 11),
        head_root: make_block(spec, intermediate_root, 13),
    }
    proofs = {
        spec.ProofType(proof_type): make_proof(spec, proof_type, valid_root, 10, head_root, 13)
        for proof_type in (1, 2)
    }
    store = make_store(blocks, {head_root: proofs})
    opt_store = SimpleNamespace(
        optimistic_roots={intermediate_root, head_root},
        head_block_root=unrelated_head,
    )
    statuses = {
        valid_root: spec.PAYLOAD_STATUS_VALID,
        intermediate_root: spec.PAYLOAD_STATUS_NOT_VALIDATED,
        head_root: spec.PAYLOAD_STATUS_NOT_VALIDATED,
    }

    assert spec.promote_payload_validation_status(store, opt_store, statuses, head_root)
    assert statuses[intermediate_root] == spec.PAYLOAD_STATUS_VALID
    assert statuses[head_root] == spec.PAYLOAD_STATUS_VALID
    assert opt_store.optimistic_roots == set()
    assert opt_store.head_block_root == unrelated_head


@with_eip8025_and_later(features=["stateless"])
@spec_test
@single_phase
def test_stateless_recursive_promotion_defers_for_incompatible_origin(spec, eip8025_features):
    assert "stateless" in eip8025_features
    valid_root = make_root(spec, 1)
    head_root = make_root(spec, 2)
    competing_root = make_root(spec, 3)
    blocks = {
        valid_root: make_block(spec, spec.Root(), 10),
        head_root: make_block(spec, valid_root, 11),
        competing_root: make_block(spec, valid_root, 10),
    }
    compatible = make_proof(spec, 1, valid_root, 10, head_root, 11)
    incompatible = make_proof(spec, 2, competing_root, 10, head_root, 11)
    store = make_store(
        blocks,
        {
            head_root: {
                compatible.proof_type: compatible,
                incompatible.proof_type: incompatible,
            }
        },
    )
    opt_store = SimpleNamespace(optimistic_roots={head_root})
    statuses = {
        valid_root: spec.PAYLOAD_STATUS_VALID,
        head_root: spec.PAYLOAD_STATUS_NOT_VALIDATED,
    }

    assert not spec.promote_payload_validation_status(store, opt_store, statuses, head_root)
    assert statuses[head_root] == spec.PAYLOAD_STATUS_NOT_VALIDATED
    assert head_root in opt_store.optimistic_roots


@with_eip8025_and_later(features=["stateless"])
@spec_test
@single_phase
def test_stateless_promotion_never_revives_invalidated_block(spec, eip8025_features):
    assert "stateless" in eip8025_features
    head_root = make_root(spec, 1)
    proofs = {
        spec.ProofType(proof_type): make_proof(spec, proof_type, head_root, 10, head_root, 10)
        for proof_type in (1, 2)
    }
    store = make_store(
        {head_root: make_block(spec, spec.Root(), 10)},
        {head_root: proofs},
    )
    opt_store = SimpleNamespace(optimistic_roots=set())
    statuses = {head_root: spec.PAYLOAD_STATUS_INVALIDATED}

    assert not spec.promote_payload_validation_status(store, opt_store, statuses, head_root)
    assert statuses[head_root] == spec.PAYLOAD_STATUS_INVALIDATED
