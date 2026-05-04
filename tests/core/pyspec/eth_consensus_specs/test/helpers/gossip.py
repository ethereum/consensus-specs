from eth_utils import encode_hex


def get_seen(spec):
    """Create an empty Seen object for gossip validation."""
    return spec.Seen(
        proposer_slots=set(),
        aggregator_epochs=set(),
        aggregate_data_roots={},
        voluntary_exit_indices=set(),
        proposer_slashing_indices=set(),
        attester_slashing_indices=set(),
        attestation_validator_epochs=set(),
    )


def get_filename(obj):
    """Get a filename for an SSZ object based on its type."""
    class_name = obj.__class__.__name__

    # Map class names to filename prefixes
    if "BeaconBlock" in class_name:
        prefix = "block"
    elif class_name == "Attestation":
        prefix = "attestation"
    elif "AggregateAndProof" in class_name:
        prefix = "aggregate"
    elif class_name == "ProposerSlashing":
        prefix = "proposer_slashing"
    elif class_name == "AttesterSlashing":
        prefix = "attester_slashing"
    elif "VoluntaryExit" in class_name:
        prefix = "voluntary_exit"
    else:
        raise Exception(f"unsupported type: {class_name}")

    return f"{prefix}_{encode_hex(obj.hash_tree_root())}"
