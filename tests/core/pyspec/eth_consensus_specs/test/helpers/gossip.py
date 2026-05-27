import inspect

from eth_utils import encode_hex

from eth_consensus_specs.test.helpers.forks import (
    is_post_altair,
    is_post_capella,
    is_post_deneb,
    is_post_fulu,
    is_post_gloas,
)

PAYLOAD_STATUS_VALID = "VALID"
PAYLOAD_STATUS_INVALIDATED = "INVALIDATED"
PAYLOAD_STATUS_NOT_VALIDATED = "NOT_VALIDATED"


def wrap_genesis_block(spec, block):
    """Wrap an unsigned genesis block in a SignedBeaconBlock with empty signature."""
    return spec.SignedBeaconBlock(message=block)


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


def _call_validation_fn(spec_func, *args, **kwargs):
    """Call spec_func with args/kwargs; assert no unexpected kwargs are supplied."""
    accepted = set(inspect.signature(spec_func).parameters)
    extras = set(kwargs) - accepted
    assert not extras, f"unexpected kwargs for {spec_func.__name__}: {sorted(extras)}"
    return spec_func(*args, **kwargs)


def _dispatch_gossip_validation(spec, seen, store, state, message, kwargs):
    """Dispatch to the appropriate gossip validation function based on message's type."""
    type_name = type(message).__name__
    info = _MESSAGE_INFO.get(type_name)
    func_name = info["validation_fn"] if info else None
    if func_name is None:
        raise Exception(f"unsupported gossip message type: {type_name}")
    spec_func = getattr(spec, func_name)
    # Some validators (e.g. voluntary_exit, slashings) don't take store
    takes_store = "store" in inspect.signature(spec_func).parameters
    assert takes_store or store is None
    args = [seen, store, state, message] if takes_store else [seen, state, message]
    return _call_validation_fn(spec_func, *args, **kwargs)


def run_validate_gossip(spec, seen, store=None, state=None, message=None, **kwargs):
    """Dispatch to the appropriate gossip validation function based on message's type."""
    try:
        _dispatch_gossip_validation(spec, seen, store, state, message, kwargs)
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def get_seen(spec):
    """Create an empty Seen object for gossip validation."""
    kwargs = {
        "proposer_slots": set(),
        "aggregator_epochs": set(),
        "aggregate_data_roots": {},
        "voluntary_exit_indices": set(),
        "proposer_slashing_indices": set(),
        "attester_slashing_indices": set(),
        "attestation_validator_epochs": set(),
    }
    if is_post_altair(spec):
        kwargs.update(
            {
                "sync_contribution_aggregator_slots": set(),
                "sync_contribution_data": {},
                "sync_message_validator_slots": set(),
            }
        )
    if is_post_capella(spec):
        kwargs.update(
            {
                "bls_to_execution_change_indices": set(),
            }
        )
    if is_post_deneb(spec) and not is_post_fulu(spec):
        kwargs.update(
            {
                "blob_sidecar_tuples": set(),
            }
        )
    if is_post_fulu(spec):
        kwargs.update(
            {
                "data_column_sidecar_tuples": set(),
            }
        )
        if not is_post_gloas(spec):
            kwargs.update(
                {
                    "partial_data_column_headers": {},
                }
            )
    if is_post_gloas(spec):
        kwargs.update(
            {
                "execution_payloads": {},
                "execution_payload_envelopes": set(),
                "payload_attestation_validators": set(),
                "execution_payload_bids": set(),
                "best_execution_payload_bid": {},
                "proposer_preferences": {},
            }
        )
    return spec.Seen(**kwargs)
