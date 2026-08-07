def initialize_ptc_window(spec, state):
    empty_previous_epoch = [
        spec.PTC(data=[spec.ValidatorIndex(0) for _ in range(spec.PTC_SIZE)])
        for _ in range(spec.SLOTS_PER_EPOCH)
    ]
    ptcs = []
    current_epoch = spec.get_current_epoch(state)
    for e in range(1 + spec.MIN_SEED_LOOKAHEAD):
        epoch = spec.Epoch(current_epoch + e)
        start_slot = spec.compute_start_slot_at_epoch(epoch)
        ptcs += [
            spec.compute_ptc(state, spec.Slot(start_slot + i)) for i in range(spec.SLOTS_PER_EPOCH)
        ]
    return spec.PTCWindow(data=empty_previous_epoch + ptcs)
