from types import SimpleNamespace

from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_eip8025_and_later,
)
from eth_consensus_specs.test.helpers.block import build_block_and_payload
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.merkle import build_proof
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


class DummyGuest:
    def __init__(
        self,
        spec,
        *,
        previous_proof_is_valid=True,
        successful_validation=True,
        result_chain_config=None,
    ):
        self.spec = spec
        self.previous_proof_is_valid = previous_proof_is_valid
        self.successful_validation = successful_validation
        self.result_chain_config = result_chain_config
        self.previous_proofs = []
        self.new_payload_calls = []

    def verify_execution_proof(self, previous_proof, chain_config_root):
        self.previous_proofs.append((previous_proof, chain_config_root))
        return self.previous_proof_is_valid

    def verify_stateless_new_payload(
        self,
        new_payload_request,
        execution_witness,
        chain_config,
        public_keys,
    ):
        self.new_payload_calls.append(
            (
                new_payload_request,
                execution_witness,
                chain_config,
                public_keys,
            )
        )
        if self.result_chain_config is None:
            self.result_chain_config = chain_config
        return SimpleNamespace(
            successful_validation=self.successful_validation,
            chain_config=self.result_chain_config,
        )


def get_chain_config(spec):
    return spec.Root(b"\xcc" * 32)


def get_chain_config_root(spec):
    return spec.hash_tree_root(get_chain_config(spec))


def get_block_header(spec, block):
    return spec.BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=block.state_root,
        body_root=block.body.hash_tree_root(),
    )


def get_checkpoint(spec, block):
    header = get_block_header(spec, block)
    return spec.ExecutionCheckpoint(
        slot=header.slot,
        beacon_block_root=header.hash_tree_root(),
    )


def get_branch(value, generalized_index):
    return build_proof(value.get_backing(), int(generalized_index))


def get_bid_witness(spec, block):
    bid_gindex = spec.get_generalized_index(
        spec.BeaconBlockBody,
        "signed_execution_payload_bid",
    )
    return spec.BeaconBlockBidWitness(
        signed_bid=block.body.signed_execution_payload_bid,
        signed_bid_merkle_witness=get_branch(block.body, bid_gindex),
    )


def build_target_state_witness(spec, state, block):
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
    latest_block_hash_gindex = spec.get_generalized_index(
        spec.BeaconState,
        "latest_block_hash",
    )
    signer_gindex = spec.get_progressive_list_element_field_gindex(
        spec.BeaconState,
        "validators",
        spec.Validators,
        block.proposer_index,
        spec.Validator,
        "pubkey",
    )
    return spec.BeaconStateWitness(
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
        latest_block_hash=state.latest_block_hash,
        latest_block_hash_merkle_witness=get_branch(state, latest_block_hash_gindex),
        envelope_signer_pubkey=state.validators[block.proposer_index].pubkey,
        envelope_signer_pubkey_merkle_witness=get_branch(state, signer_gindex),
    )


def build_target_block(spec, state, *, slot=None, parent_payload=None):
    if slot is None:
        slot = state.slot + 1
    block, _payload = build_block_and_payload(
        spec,
        state,
        slot=slot,
        parent_payload=parent_payload,
    )
    signed_block = state_transition_and_sign_block(spec, state, block)
    block = signed_block.message
    signed_envelope = build_signed_execution_payload_envelope(
        spec,
        state,
        block.hash_tree_root(),
        signed_block,
    )
    return signed_block, signed_envelope


def make_private_input(
    spec,
    state,
    signed_block,
    signed_envelope,
    *,
    origin,
    previous_proof,
    previous_bid,
    beacon_lineage,
):
    block = signed_block.message
    return spec.PrivateInput(
        beacon_chain_witness=spec.BeaconChainWitness(
            origin=origin,
            previous_proof=previous_proof,
            previous_bid=previous_bid,
            beacon_lineage=beacon_lineage,
            target_bid=get_bid_witness(spec, block),
            signed_envelope=signed_envelope,
            target_state=build_target_state_witness(spec, state, block),
        ),
        execution_witness=object(),
        chain_config=get_chain_config(spec),
        public_keys=[],
    )


def build_base_private_input(spec, state):
    signed_block, signed_envelope = build_target_block(spec, state)
    block = signed_block.message
    target = get_checkpoint(spec, block)
    private_input = make_private_input(
        spec,
        state,
        signed_block,
        signed_envelope,
        origin=target,
        previous_proof=None,
        previous_bid=None,
        beacon_lineage=[get_block_header(spec, block)],
    )
    return private_input, signed_block, signed_envelope


def build_recursive_private_input(
    spec,
    state,
    *,
    missed_slot=False,
    with_intermediate=False,
    intermediate_is_full=False,
):
    base_input, base_signed_block, base_envelope = build_base_private_input(spec, state)
    base_block = base_signed_block.message
    origin = base_input.beacon_chain_witness.origin
    previous_proof = spec.ExecutionProof(
        proof_data=spec.ProgressiveByteList(b"\x01"),
        proof_type=spec.ProofType(1),
        claim=spec.ExecutionProofClaim(origin=origin, head=origin),
    )
    lineage = [get_block_header(spec, base_block)]

    parent_payload = base_envelope.message.payload
    if with_intermediate:
        intermediate_signed_block, intermediate_envelope = build_target_block(
            spec,
            state,
            parent_payload=parent_payload,
        )
        lineage.append(get_block_header(spec, intermediate_signed_block.message))
        if intermediate_is_full:
            parent_payload = intermediate_envelope.message.payload
        else:
            parent_payload = None

    target_slot = state.slot + (2 if missed_slot else 1)
    target_signed_block, target_envelope = build_target_block(
        spec,
        state,
        slot=target_slot,
        parent_payload=parent_payload,
    )
    lineage.append(get_block_header(spec, target_signed_block.message))
    private_input = make_private_input(
        spec,
        state,
        target_signed_block,
        target_envelope,
        origin=None,
        previous_proof=previous_proof,
        previous_bid=get_bid_witness(spec, base_block),
        beacon_lineage=lineage,
    )
    return private_input, previous_proof


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_valid_base_proof(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)
    guest = DummyGuest(spec)
    chain_config_root = get_chain_config_root(spec)

    public_input = spec.process_private_input(guest, private_input, chain_config_root)

    witness = private_input.beacon_chain_witness
    target_header = witness.beacon_lineage[-1]
    assert public_input.origin == witness.origin
    assert public_input.head.slot == target_header.slot
    assert public_input.head.beacon_block_root == target_header.hash_tree_root()
    assert public_input.chain_config_root == chain_config_root
    assert len(guest.new_payload_calls) == 1
    assert guest.new_payload_calls[0][2] == private_input.chain_config


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_base_origin_must_equal_target(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)
    private_input.beacon_chain_witness.origin.beacon_block_root = spec.Root(b"\xaa" * 32)

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_base_rejects_previous_bid(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)
    witness = private_input.beacon_chain_witness
    witness.previous_bid = witness.target_bid

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_valid_recursive_proof(spec, state):
    private_input, previous_proof = build_recursive_private_input(spec, state)
    guest = DummyGuest(spec)
    chain_config_root = get_chain_config_root(spec)

    public_input = spec.process_private_input(guest, private_input, chain_config_root)

    assert public_input.origin == previous_proof.claim.origin
    assert public_input.head.slot == private_input.beacon_chain_witness.beacon_lineage[-1].slot
    assert guest.previous_proofs == [(previous_proof, chain_config_root)]


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_recursive_proof_accepts_missed_slot(spec, state):
    private_input, _previous_proof = build_recursive_private_input(
        spec,
        state,
        missed_slot=True,
    )

    spec.process_private_input(
        DummyGuest(spec),
        private_input,
        get_chain_config_root(spec),
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_recursive_proof_accepts_empty_intermediate(spec, state):
    private_input, _previous_proof = build_recursive_private_input(
        spec,
        state,
        with_intermediate=True,
    )

    spec.process_private_input(
        DummyGuest(spec),
        private_input,
        get_chain_config_root(spec),
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_recursive_proof_rejects_changed_execution_head(spec, state):
    private_input, _previous_proof = build_recursive_private_input(
        spec,
        state,
        with_intermediate=True,
        intermediate_is_full=True,
    )

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_rejects_invalid_previous_proof(spec, state):
    private_input, _previous_proof = build_recursive_private_input(spec, state)

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec, previous_proof_is_valid=False),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_rejects_previous_head_mismatch(spec, state):
    private_input, previous_proof = build_recursive_private_input(spec, state)
    previous_proof.claim.head.beacon_block_root = spec.Root(b"\xbb" * 32)

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_rejects_broken_beacon_ancestry(spec, state):
    private_input, _previous_proof = build_recursive_private_input(spec, state)
    private_input.beacon_chain_witness.beacon_lineage[-1].parent_root = spec.Root(b"\xdd" * 32)

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_rejects_invalid_envelope_signature(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)
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
def test_process_private_input_rejects_unauthenticated_latest_block_hash(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)
    private_input.beacon_chain_witness.target_state.latest_block_hash = spec.Hash32(b"\xee" * 32)

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
def test_process_private_input_rejects_invalid_latest_block_hash_branch(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)
    target_state = private_input.beacon_chain_witness.target_state
    branch = list(target_state.latest_block_hash_merkle_witness)
    branch[0] = spec.Bytes32(b"\xef" * 32)
    target_state.latest_block_hash_merkle_witness = branch

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec),
            private_input,
            get_chain_config_root(spec),
        )
    )


def mutate_envelope_binding(spec, private_input, case):
    witness = private_input.beacon_chain_witness
    envelope = witness.signed_envelope.message
    payload = envelope.payload

    if case == "beacon_block_root":
        envelope.beacon_block_root = spec.Root(b"\x01" * 32)
    elif case == "parent_beacon_block_root":
        envelope.parent_beacon_block_root = spec.Root(b"\x02" * 32)
    elif case == "builder_index":
        envelope.builder_index = spec.BuilderIndex(0)
    elif case == "block_hash":
        payload.block_hash = spec.Hash32(b"\x03" * 32)
    elif case == "prev_randao":
        payload.prev_randao = spec.Bytes32(b"\x04" * 32)
    elif case == "gas_limit":
        payload.gas_limit += 1
    elif case == "execution_requests_root":
        envelope.execution_requests.withdrawals.append(spec.WithdrawalRequest())
    elif case == "slot_number":
        payload.slot_number += 1
    elif case == "parent_hash":
        payload.parent_hash = spec.Hash32(b"\x05" * 32)
    elif case == "timestamp":
        payload.timestamp += 1
    elif case == "withdrawals_root":
        payload.withdrawals.append(spec.Withdrawal())
    else:
        raise ValueError(f"unknown case: {case}")


@with_eip8025_and_later
@spec_state_test
@always_bls
def test_process_private_input_rejects_envelope_binding_mismatch(spec, state):
    pre_state = state.copy()
    cases = (
        "beacon_block_root",
        "parent_beacon_block_root",
        "builder_index",
        "block_hash",
        "prev_randao",
        "gas_limit",
        "execution_requests_root",
        "slot_number",
        "parent_hash",
        "timestamp",
        "withdrawals_root",
    )
    for case in cases:
        private_input, _signed_block, _signed_envelope = build_base_private_input(
            spec,
            pre_state.copy(),
        )
        mutate_envelope_binding(spec, private_input, case)
        expect_assertion_error(
            lambda private_input=private_input: spec.process_private_input(
                DummyGuest(spec),
                private_input,
                get_chain_config_root(spec),
            )
        )


@with_eip8025_and_later
@spec_state_test
def test_process_private_input_rejects_failed_stateless_validation(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)

    expect_assertion_error(
        lambda: spec.process_private_input(
            DummyGuest(spec, successful_validation=False),
            private_input,
            get_chain_config_root(spec),
        )
    )


@with_eip8025_and_later
@spec_state_test
def test_process_private_input_rejects_wrong_stateless_chain_config(spec, state):
    private_input, _signed_block, _signed_envelope = build_base_private_input(spec, state)
    guest = DummyGuest(
        spec,
        result_chain_config=spec.Root(b"\xdd" * 32),
    )

    expect_assertion_error(
        lambda: spec.process_private_input(
            guest,
            private_input,
            get_chain_config_root(spec),
        )
    )
