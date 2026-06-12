import inspect
from typing import get_origin, get_type_hints

from eth_utils import encode_hex

from eth_consensus_specs.test.context import expect_assertion_error
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

PAYLOAD_STATUS_VALID = "VALID"
PAYLOAD_STATUS_INVALIDATED = "INVALIDATED"
PAYLOAD_STATUS_NOT_VALIDATED = "NOT_VALIDATED"


def wrap_genesis_block(spec, block):
    """Wrap an unsigned genesis block in a SignedBeaconBlock with empty signature."""
    return spec.SignedBeaconBlock(message=block)


def add_pending_block_to_store(store, signed_block):
    """
    Record a block that has been seen but not yet imported: present in
    ``store.blocks`` with no post-state. The corresponding blocks meta entry
    must set ``pending: true``.
    """
    store.blocks[signed_block.message.hash_tree_root()] = signed_block.message


def setup_store_with_failed_block(spec, state):
    """
    Build the genesis store plus a correctly signed block for the next slot
    whose state root is wrong, so it passes gossip checks but fails state
    transition on import. The failed block is recorded as seen, with no
    post-state. The corresponding blocks meta entry must set ``failed: true``.

    Advances ``state`` past the valid version of the block so callers can
    build descendants and messages on top of it.
    Returns (store, signed_anchor, signed_failed_block).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    pre_state = state.copy()
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    failed_block = signed_block.message.copy()
    failed_block.state_root = spec.Root(b"\xab" * 32)
    signed_failed_block = sign_block(
        spec, state, failed_block, proposer_index=failed_block.proposer_index
    )
    # Prove the block genuinely fails import before recording it as failed.
    expect_assertion_error(
        lambda: spec.state_transition(pre_state, signed_failed_block, validate_result=True)
    )
    store.blocks[signed_failed_block.message.hash_tree_root()] = signed_failed_block.message
    return store, signed_anchor, signed_failed_block


def get_spec_block_payload_statuses(spec, block_payload_statuses):
    spec_block_payload_statuses = {}
    for block_root, payload_status in block_payload_statuses.items():
        if payload_status == PAYLOAD_STATUS_VALID:
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_VALID
        elif payload_status == PAYLOAD_STATUS_INVALIDATED:
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_INVALIDATED
        else:
            assert payload_status == PAYLOAD_STATUS_NOT_VALIDATED
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_NOT_VALIDATED

    return spec_block_payload_statuses


_MESSAGE_INFO = {
    ###########################################################################
    # phase0
    ###########################################################################
    "Attestation": {
        "file_prefix": "attestation",
        "validation_fn": "validate_beacon_attestation_gossip",
    },
    "AttesterSlashing": {
        "file_prefix": "attester_slashing",
        "validation_fn": "validate_attester_slashing_gossip",
    },
    "ProposerSlashing": {
        "file_prefix": "proposer_slashing",
        "validation_fn": "validate_proposer_slashing_gossip",
    },
    "SignedAggregateAndProof": {
        "file_prefix": "aggregate",
        "validation_fn": "validate_beacon_aggregate_and_proof_gossip",
    },
    "SignedBeaconBlock": {
        "file_prefix": "block",
        "validation_fn": "validate_beacon_block_gossip",
    },
    "SignedVoluntaryExit": {
        "file_prefix": "voluntary_exit",
        "validation_fn": "validate_voluntary_exit_gossip",
    },
    "SingleAttestation": {
        "file_prefix": "single_attestation",
        "validation_fn": "validate_beacon_attestation_gossip",
    },
    ###########################################################################
    # altair
    ###########################################################################
    "SignedContributionAndProof": {
        "file_prefix": "contribution",
        "validation_fn": "validate_sync_committee_contribution_and_proof_gossip",
    },
    "SyncCommitteeMessage": {
        "file_prefix": "sync_committee_message",
        "validation_fn": "validate_sync_committee_message_gossip",
    },
    ###########################################################################
    # capella
    ###########################################################################
    "SignedBLSToExecutionChange": {
        "file_prefix": "bls_to_execution_change",
        "validation_fn": "validate_bls_to_execution_change_gossip",
    },
    ###########################################################################
    # deneb
    ###########################################################################
    "BlobSidecar": {
        "file_prefix": "blob_sidecar",
        "validation_fn": "validate_blob_sidecar_gossip",
    },
    ###########################################################################
    # fulu
    ###########################################################################
    "DataColumnSidecar": {
        "file_prefix": "data_column_sidecar",
        "validation_fn": "validate_data_column_sidecar_gossip",
    },
    "PartialDataColumnHeader": {
        "file_prefix": "partial_data_column_header",
        "validation_fn": None,
    },
    "PartialDataColumnSidecar": {
        "file_prefix": "partial_data_column_sidecar",
        "validation_fn": "validate_partial_data_column_sidecar_gossip",
    },
    ###########################################################################
    # gloas
    ###########################################################################
    "PayloadAttestationMessage": {
        "file_prefix": "payload_attestation_message",
        "validation_fn": "validate_payload_attestation_message_gossip",
    },
    "SignedExecutionPayloadBid": {
        "file_prefix": "execution_payload_bid",
        "validation_fn": "validate_execution_payload_bid_gossip",
    },
    "SignedExecutionPayloadEnvelope": {
        "file_prefix": "execution_payload_envelope",
        "validation_fn": "validate_execution_payload_envelope_gossip",
    },
    "SignedProposerPreferences": {
        "file_prefix": "proposer_preferences",
        "validation_fn": "validate_proposer_preferences_gossip",
    },
}


def get_filename(obj):
    """Get a filename for an SSZ object based on its type."""
    class_name = obj.__class__.__name__
    info = _MESSAGE_INFO.get(class_name)
    if info is None:
        raise Exception(f"unsupported type: {class_name}")
    return f"{info['file_prefix']}_{encode_hex(obj.hash_tree_root())}"


def run_validate_gossip(spec, **kwargs):
    """Dispatch to the appropriate gossip validation function based on the message's type."""
    matches = [v for v in kwargs.values() if type(v).__name__ in _MESSAGE_INFO]
    assert len(matches) == 1, f"expected exactly one gossip message kwarg, got {len(matches)}"
    func_name = _MESSAGE_INFO[type(matches[0]).__name__]["validation_fn"]
    if func_name is None:
        raise Exception(f"unsupported gossip message type: {type(matches[0]).__name__}")
    spec_func = getattr(spec, func_name)
    extras = set(kwargs) - set(inspect.signature(spec_func).parameters)
    assert not extras, f"unexpected kwargs for {func_name}: {sorted(extras)}"

    try:
        spec_func(**kwargs)
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def get_seen(spec):
    """Create an empty Seen object by instantiating each annotated field's container type."""
    return spec.Seen(**{name: get_origin(t)() for name, t in get_type_hints(spec.Seen).items()})
