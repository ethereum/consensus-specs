from eth2spec.test.context import with_all_phases, spec_state_test


def run_on_tick(spec, store, time, new_justified_checkpoint=None):
    previous_justified_checkpoint = store.justified_checkpoint

    spec.on_tick(store, time)

    assert store.time == time

    if new_justified_checkpoint:
        assert store.justified_checkpoint == new_justified_checkpoint
        assert store.justified_checkpoint.epoch > previous_justified_checkpoint.epoch
    else:
        assert store.justified_checkpoint == previous_justified_checkpoint


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    store = spec.get_genesis_store(state)
    run_on_tick(spec, store, store.time + 1)


@with_all_phases
@spec_state_test
def test_update_justified_single(spec, state):
    store = spec.get_genesis_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    new_justified = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )
    store.queued_justified_checkpoints.append(new_justified)

    run_on_tick(spec, store, store.time + seconds_per_epoch, new_justified)


@with_all_phases
@spec_state_test
def test_update_justified_multiple(spec, state):
    store = spec.get_genesis_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    new_justified = None  # remember checkpoint with latest epoch
    for i in range(3):
        new_justified = spec.Checkpoint(
            epoch=store.justified_checkpoint.epoch + i + 1,
            root=i.to_bytes(1, byteorder='big') * 32,
        )
        store.queued_justified_checkpoints.append(new_justified)

    run_on_tick(spec, store, store.time + seconds_per_epoch, new_justified)


@with_all_phases
@spec_state_test
def test_no_update_same_slot_at_epoch_boundary(spec, state):
    store = spec.get_genesis_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    new_justified = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )
    store.queued_justified_checkpoints.append(new_justified)

    # set store time to already be at epoch boundary
    store.time = seconds_per_epoch

    run_on_tick(spec, store, store.time + 1)


@with_all_phases
@spec_state_test
def test_no_update_not_epoch_boundary(spec, state):
    store = spec.get_genesis_store(state)

    new_justified = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )
    store.queued_justified_checkpoints.append(new_justified)

    run_on_tick(spec, store, store.time + spec.SECONDS_PER_SLOT)


@with_all_phases
@spec_state_test
def test_no_update_new_justified_equal_epoch(spec, state):
    store = spec.get_genesis_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    new_justified = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )
    store.queued_justified_checkpoints.append(new_justified)

    store.justified_checkpoint = spec.Checkpoint(
        epoch=new_justified.epoch,
        root=b'\44' * 32,
    )

    run_on_tick(spec, store, store.time + seconds_per_epoch)


@with_all_phases
@spec_state_test
def test_no_update_new_justified_later_epoch(spec, state):
    store = spec.get_genesis_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    new_justified = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )
    store.queued_justified_checkpoints.append(new_justified)

    store.justified_checkpoint = spec.Checkpoint(
        epoch=new_justified.epoch + 1,
        root=b'\44' * 32,
    )

    run_on_tick(spec, store, store.time + seconds_per_epoch)
