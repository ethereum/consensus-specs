from frozendict import frozendict

BASIS_POINTS = 10000

# The inherited basis-point fractions, used to place each deadline at its
# pre-schedule relative position by default
DEADLINE_BPS = {
    "PROPOSER_REORG_CUTOFF_MS": 1667,
    "ATTESTATION_DUE_MS": 2500,
    "AGGREGATE_DUE_MS": 5000,
    "SYNC_MESSAGE_DUE_MS": 2500,
    "CONTRIBUTION_DUE_MS": 5000,
    "PAYLOAD_DUE_MS": 5000,
    "PAYLOAD_ATTESTATION_DUE_MS": 7500,
    "INCLUSION_LIST_DUE_MS": 6667,
}


def slot_duration_schedule_entry(epoch, slot_duration_ms, **deadline_overrides):
    """
    Build a ``SLOT_DURATION_SCHEDULE`` entry, with deadlines at the inherited
    fractions of the slot duration unless overridden.
    """
    entry = {"EPOCH": epoch, "SLOT_DURATION_MS": slot_duration_ms}
    for name, basis_points in DEADLINE_BPS.items():
        entry[name] = basis_points * slot_duration_ms // BASIS_POINTS
    entry.update(deadline_overrides)
    return frozendict(entry)
