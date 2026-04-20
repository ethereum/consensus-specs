def compute_proposer_lookahead(spec, state):
    current_epoch = spec.get_current_epoch(state)
    lookahead = []
    for i in range(spec.MIN_SEED_LOOKAHEAD + 1):
        lookahead.extend(spec.get_beacon_proposer_indices(state, spec.Epoch(current_epoch + i)))
    return lookahead
