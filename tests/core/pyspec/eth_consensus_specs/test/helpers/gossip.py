from eth_utils import encode_hex

from eth_consensus_specs.test.helpers.forks import is_post_altair, is_post_capella, is_post_deneb

PAYLOAD_STATUS_VALID = "VALID"
PAYLOAD_STATUS_INVALIDATED = "INVALIDATED"
PAYLOAD_STATUS_NOT_VALIDATED = "NOT_VALIDATED"


def wrap_genesis_block(spec, block):
    """Wrap an unsigned genesis block in a SignedBeaconBlock with empty signature."""
    return spec.SignedBeaconBlock(message=block)


def get_spec_block_payload_statuses(spec, block_payload_statuses):
    spec_block_payload_statuses = {}
    if block_payload_statuses is None:
        return spec_block_payload_statuses

    for block_root, payload_status in block_payload_statuses.items():
        if payload_status == PAYLOAD_STATUS_VALID:
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_VALID
        elif payload_status == PAYLOAD_STATUS_INVALIDATED:
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_INVALIDATED
        else:
            assert payload_status == PAYLOAD_STATUS_NOT_VALIDATED
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_NOT_VALIDATED

    return spec_block_payload_statuses


def run_validate_beacon_block_gossip(
    spec, seen, store, state, signed_block, current_time_ms, block_payload_statuses=None
):
    """
    Run validate_beacon_block_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    kwargs = {}
    if block_payload_statuses is not None:
        kwargs["block_payload_statuses"] = get_spec_block_payload_statuses(
            spec, block_payload_statuses
        )
    try:
        spec.validate_beacon_block_gossip(
            seen, store, state, signed_block, current_time_ms, **kwargs
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def get_seen(spec):
    """Create an empty Seen object for gossip validation."""
    kwargs = dict(
        proposer_slots=set(),
        aggregator_epochs=set(),
        aggregate_data_roots={},
        voluntary_exit_indices=set(),
        proposer_slashing_indices=set(),
        attester_slashing_indices=set(),
        attestation_validator_epochs=set(),
    )
    if is_post_altair(spec):
        kwargs.update(
            dict(
                sync_contribution_aggregator_slots=set(),
                sync_contribution_data={},
                sync_message_validator_slots=set(),
            )
        )
    if is_post_capella(spec):
        kwargs.update(
            dict(
                bls_to_execution_change_indices=set(),
            )
        )
    if is_post_deneb(spec):
        kwargs.update(
            dict(
                blob_sidecar_tuples=set(),
            )
        )
    return spec.Seen(**kwargs)


def get_filename(obj):
    """Get a filename for an SSZ object based on its type."""
    class_name = obj.__class__.__name__

    # phase0
    if "BeaconBlock" in class_name:
        prefix = "block"
    elif class_name == "Attestation":
        prefix = "attestation"
    elif class_name == "SingleAttestation":
        prefix = "single_attestation"
    elif "AggregateAndProof" in class_name:
        prefix = "aggregate"
    elif class_name == "ProposerSlashing":
        prefix = "proposer_slashing"
    elif class_name == "AttesterSlashing":
        prefix = "attester_slashing"
    elif "VoluntaryExit" in class_name:
        prefix = "voluntary_exit"
    # altair
    elif "ContributionAndProof" in class_name:
        prefix = "contribution"
    elif class_name == "SyncCommitteeMessage":
        prefix = "sync_committee_message"
    # capella
    elif "BLSToExecutionChange" in class_name:
        prefix = "bls_to_execution_change"
    # deneb
    elif class_name == "BlobSidecar":
        prefix = "blob_sidecar"
    else:
        raise Exception(f"unsupported type: {class_name}")

    return f"{prefix}_{encode_hex(obj.hash_tree_root())}"
