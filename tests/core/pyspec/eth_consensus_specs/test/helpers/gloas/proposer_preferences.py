from eth_consensus_specs.test.helpers.keys import privkeys


def find_upcoming_proposal_slot(spec, state):
    """
    Return the next future slot in the proposer lookahead, with the validator
    that is proposing it.
    """
    current_epoch_start = spec.compute_start_slot_at_epoch(spec.get_current_epoch(state))
    for offset, validator_index in enumerate(state.proposer_lookahead):
        slot = spec.Slot(current_epoch_start + offset)
        if slot <= state.slot:
            continue
        return slot, validator_index
    raise AssertionError("no upcoming proposal slot found in lookahead")


def build_signed_proposer_preferences(
    spec,
    state,
    proposal_slot=None,
    validator_index=None,
    dependent_root=None,
    fee_recipient=None,
    target_gas_limit=None,
    valid_signature=True,
):
    """Construct a SignedProposerPreferences with sensible defaults."""
    if proposal_slot is None or validator_index is None:
        proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)

    if dependent_root is None:
        dependent_root = spec.get_proposer_dependent_root(
            state, spec.compute_epoch_at_slot(proposal_slot)
        )

    if fee_recipient is None:
        fee_recipient = spec.ExecutionAddress(b"\x11" * 20)

    if target_gas_limit is None:
        target_gas_limit = spec.uint64(30_000_000)

    preferences = spec.ProposerPreferences(
        dependent_root=dependent_root,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=fee_recipient,
        target_gas_limit=target_gas_limit,
    )

    if valid_signature:
        domain = spec.get_domain(
            state,
            spec.DOMAIN_PROPOSER_PREFERENCES,
            spec.compute_epoch_at_slot(proposal_slot),
        )
        signing_root = spec.compute_signing_root(preferences, domain)
        signature = spec.bls.Sign(privkeys[validator_index], signing_root)
    else:
        signature = spec.BLSSignature()

    return spec.SignedProposerPreferences(message=preferences, signature=signature)
