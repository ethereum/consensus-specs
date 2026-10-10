import pytest

from eth_consensus_specs.test.context import (
    expect_assertion_error,
    single_phase,
    spec_state_test,
    spec_test,
    with_heze_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
    sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth_consensus_specs.test.helpers.gossip import get_seen
from eth_consensus_specs.test.helpers.inclusion_list import run_with_inclusion_list_store
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def setup_claimed_envelope(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    # Duplicate hashes and a maximum index are EL inputs, not CL validity errors.
    claims = spec.InclusionListClaims(
        data=[
            spec.InclusionListClaim(transaction_hash=spec.Bytes32(b"\x11" * 32)),
            spec.InclusionListClaim(
                transaction_hash=spec.Bytes32(b"\x11" * 32), transaction_index=2**64 - 1
            ),
        ]
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.signed_execution_payload_bid.message.inclusion_claims_root = spec.hash_tree_root(
        claims
    )
    signed_block = state_transition_and_sign_block(spec, state, block)
    root = signed_block.message.hash_tree_root()
    store.blocks[root] = signed_block.message
    store.block_states[root] = state.copy()
    envelope = build_signed_execution_payload_envelope(spec, state, root, signed_block).message
    envelope.inclusion_claims = claims
    signed_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
    return store, signed_block, signed_envelope


@with_heze_and_later
@spec_state_test
def test_nonempty_inclusion_claims_commitment(spec, state):
    store, signed_block, signed_envelope = setup_claimed_envelope(spec, state)
    spec.validate_execution_payload_envelope_gossip(get_seen(spec), store, signed_envelope)
    spec.verify_execution_payload_envelope(state, signed_envelope, spec.NoopExecutionEngine())

    committed = signed_envelope.message.inclusion_claims
    altered_lists = [
        spec.InclusionListClaims(),
        spec.InclusionListClaims(data=list(reversed(committed))),
        spec.InclusionListClaims(data=[committed[0]]),
    ]
    for altered in altered_lists:
        envelope = signed_envelope.message.copy()
        envelope.inclusion_claims = altered
        altered_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
        with pytest.raises(spec.GossipReject, match="inclusion claims root"):
            spec.validate_execution_payload_envelope_gossip(get_seen(spec), store, altered_envelope)
        expect_assertion_error(
            lambda altered_envelope=altered_envelope: spec.verify_execution_payload_envelope(
                state, altered_envelope, spec.NoopExecutionEngine()
            )
        )


@with_heze_and_later
@spec_state_test
def test_unsatisfied_inclusion_claims_preserve_payload_validity(spec, state):
    store, _, signed_envelope = setup_claimed_envelope(spec, state)
    envelope = signed_envelope.message
    root = envelope.beacon_block_root

    def run():
        slot = state.slot - 1
        dependent_root = spec.get_shuffling_dependent_root(
            store, root, spec.compute_epoch_at_slot(slot)
        )
        committee = spec.get_inclusion_list_committee(state, slot)
        transaction = spec.Transaction(data=[1])
        spec.process_inclusion_list(
            spec.get_inclusion_list_store(),
            spec.SignedInclusionList(
                message=spec.InclusionList(
                    slot=slot,
                    validator_index=committee[0],
                    dependent_root=dependent_root,
                    transactions=spec.Transactions(data=[transaction]),
                )
            ),
            timely=True,
        )

        class RecordingEngine(spec.NoopExecutionEngine):
            called = False

            def is_inclusion_list_satisfied(self, payload, transactions, membership, claims):
                self.called = True
                assert payload == envelope.payload
                assert transactions == [transaction]
                assert membership == [
                    spec.InclusionListBits(data=[member == committee[0] for member in committee])
                ]
                assert claims == envelope.inclusion_claims
                return False

        engine = RecordingEngine()
        previous_engine = spec.EXECUTION_ENGINE
        spec.EXECUTION_ENGINE = engine
        try:
            spec.on_execution_payload_envelope(store, signed_envelope)
        finally:
            spec.EXECUTION_ENGINE = previous_engine
        assert engine.called
        assert store.payloads[root] == envelope
        assert not store.payload_inclusion_list_satisfaction[root]
        assert not spec.is_payload_inclusion_list_satisfied(store, root)
        store.time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, state.slot + 1)
        assert not spec.should_extend_payload(store, root)

    run_with_inclusion_list_store(spec, run)


@with_heze_and_later
@spec_test
@single_phase
def test_inclusion_claims_ssz_limit(spec):
    claims = spec.InclusionListClaims(
        data=[spec.InclusionListClaim()] * spec.MAX_INCLUSION_LIST_CLAIMS
    )
    assert len(claims.encode_bytes()) == 40 * spec.MAX_INCLUSION_LIST_CLAIMS
    assert spec.InclusionListClaims.decode_bytes(claims.encode_bytes()) == claims
    with pytest.raises(ValueError, match="holds at most"):
        spec.InclusionListClaims(
            data=[spec.InclusionListClaim()] * (spec.MAX_INCLUSION_LIST_CLAIMS + 1)
        )
