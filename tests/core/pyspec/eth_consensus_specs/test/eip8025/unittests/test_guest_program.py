from types import SimpleNamespace

from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8025_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
    sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.merkle import build_proof
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


class DummyGuest:
    def __init__(self, spec, *, result_chain_config_root=None):
        self.spec = spec
        self.result_chain_config_root = result_chain_config_root
        self.previous_proofs = []
        self.new_payload_requests = []

    def verify_execution_proof(self, previous_proof, chain_config_root):
        self.previous_proofs.append((previous_proof, chain_config_root))
        return True

    def verify_stateless_new_payload(
        self,
        new_payload_request,
        execution_witness,
        chain_config,
        chain_config_root,
        public_keys,
    ):
        self.new_payload_requests.append(new_payload_request)
        if self.result_chain_config_root is None:
            self.result_chain_config_root = chain_config_root
        return SimpleNamespace(
            successful_validation=True,
            chain_config_root=self.result_chain_config_root,
        )


def get_chain_config_root(spec):
    return spec.Root(b"\xcc" * 32)


def get_block_header(spec, block):
    return spec.BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=block.state_root,
        body_root=block.body.hash_tree_root(),
    )


def get_branch(value, generalized_index):
    return build_proof(value.get_backing(), int(generalized_index))


def get_bid_witness(spec, block):
    bid_gindex = spec.get_generalized_index(
        spec.BeaconBlockBody,
        "signed_execution_payload_bid",
    )
    return spec.BeaconBlockBidWitness(
        header=get_block_header(spec, block),
        signed_bid=block.body.signed_execution_payload_bid,
        signed_bid_merkle_witness=get_branch(block.body, bid_gindex),
    )


def build_private_input(spec, state):
    _store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block = signed_block.message
    # Model the anchor as a full checkpoint by linking the target bid and
    # payload to the execution block hash authenticated by the anchor bid.
    anchor_execution_block_hash = anchor_block.body.signed_execution_payload_bid.message.block_hash
    block.body.signed_execution_payload_bid.message.parent_block_hash = anchor_execution_block_hash
    block_root = block.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec,
        state,
        block_root,
        signed_block,
    )
    signed_envelope.message.payload.parent_hash = anchor_execution_block_hash
    signed_envelope = sign_execution_payload_envelope(
        spec,
        state,
        signed_block,
        signed_envelope.message,
    )

    state_root = state.hash_tree_root()
    assert block.state_root == state_root
    genesis_time_gindex = spec.get_generalized_index(spec.BeaconState, "genesis_time")
    fork_gindex = spec.get_generalized_index(spec.BeaconState, "fork")
    genesis_validators_root_gindex = spec.get_generalized_index(
        spec.BeaconState,
        "genesis_validators_root",
    )
    expected_withdrawals_gindex = spec.get_generalized_index(
        spec.BeaconState,
        "payload_expected_withdrawals",
    )
    proposer_index = block.proposer_index
    signer_gindex = spec.get_progressive_list_element_field_gindex(
        spec.BeaconState,
        "validators",
        spec.Validators,
        proposer_index,
        spec.Validator,
        "pubkey",
    )
    target_state = spec.BeaconStateWitness(
        genesis_time=state.genesis_time,
        genesis_time_merkle_witness=get_branch(state, genesis_time_gindex),
        fork=state.fork,
        fork_merkle_witness=get_branch(state, fork_gindex),
        genesis_validators_root=state.genesis_validators_root,
        genesis_validators_root_merkle_witness=get_branch(
            state,
            genesis_validators_root_gindex,
        ),
        payload_expected_withdrawals=state.payload_expected_withdrawals,
        payload_expected_withdrawals_merkle_witness=get_branch(
            state,
            expected_withdrawals_gindex,
        ),
        envelope_signer_pubkey=state.validators[proposer_index].pubkey,
        envelope_signer_pubkey_merkle_witness=get_branch(state, signer_gindex),
    )
    anchor_header = get_block_header(spec, anchor_block)
    origin = spec.ExecutionCheckpoint(
        slot=anchor_header.slot,
        beacon_block_root=anchor_header.hash_tree_root(),
    )
    beacon_chain_witness = spec.BeaconChainWitness(
        origin=origin,
        previous_proof=None,
        beacon_lineage=[
            get_bid_witness(spec, anchor_block),
            get_bid_witness(spec, block),
        ],
        signed_envelope=signed_envelope,
        target_state=target_state,
    )
    return spec.PrivateInput(
        beacon_chain_witness=beacon_chain_witness,
        execution_witness=object(),
        chain_config=b"test-chain-config",
        public_keys=[],
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_valid(spec, state):
    private_input = build_private_input(spec, state)
    guest = DummyGuest(spec)
    chain_config_root = get_chain_config_root(spec)

    public_input = spec.process_private_input(guest, private_input, chain_config_root)

    witness = private_input.beacon_chain_witness
    assert public_input.origin == witness.origin
    assert public_input.head.slot == witness.beacon_lineage[-1].header.slot
    assert public_input.head.beacon_block_root == witness.signed_envelope.message.beacon_block_root
    assert public_input.chain_config_root == chain_config_root
    assert len(guest.new_payload_requests) == 1


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_rejects_invalid_envelope_signature(spec, state):
    private_input = build_private_input(spec, state)
    private_input.beacon_chain_witness.signed_envelope.signature = spec.BLSSignature()

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
def test_process_private_input_rejects_unauthenticated_state_field(spec, state):
    private_input = build_private_input(spec, state)
    private_input.beacon_chain_witness.target_state.genesis_time += 1

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
def test_process_private_input_rejects_wrong_stateless_chain_config_root(spec, state):
    private_input = build_private_input(spec, state)
    chain_config_root = get_chain_config_root(spec)
    guest = DummyGuest(
        spec,
        result_chain_config_root=spec.Root(b"\xdd" * 32),
    )

    expect_assertion_error(
        lambda: spec.process_private_input(guest, private_input, chain_config_root)
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_recursion_uses_chain_config_root(spec, state):
    private_input = build_private_input(spec, state)
    witness = private_input.beacon_chain_witness
    previous_proof = spec.ExecutionProof(
        proof_data=spec.ProgressiveByteList(b"\x01"),
        proof_type=spec.ProofType(1),
        claim=spec.ExecutionProofClaim(origin=witness.origin, head=witness.origin),
    )
    witness.previous_proof = previous_proof
    witness.origin = None
    guest = DummyGuest(spec)
    chain_config_root = get_chain_config_root(spec)

    spec.process_private_input(guest, private_input, chain_config_root)

    assert guest.previous_proofs == [(previous_proof, chain_config_root)]
