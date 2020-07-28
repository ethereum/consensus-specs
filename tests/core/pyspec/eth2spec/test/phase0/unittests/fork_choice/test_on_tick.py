from eth2spec.test.context import with_all_phases, spec_state_test


def run_on_tick(spec, store, time, new_justified_checkpoint=False):
    previous_justified_checkpoint = store.justified_checkpoint

    spec.on_tick(store, time)

    assert store.time == time

    if new_justified_checkpoint:
        assert store.justified_checkpoint == store.best_justified_checkpoint
        assert store.justified_checkpoint.epoch > previous_justified_checkpoint.epoch
        assert store.justified_checkpoint.root != previous_justified_checkpoint.root
    else:
        assert store.justified_checkpoint == previous_justified_checkpoint


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    store = spec.get_forkchoice_store(state)
    run_on_tick(spec, store, store.time + 1)


@with_all_phases
@spec_state_test
def test_update_justified_single(spec, state):
    store = spec.get_forkchoice_store(state)
    next_epoch = spec.get_current_epoch(state) + 1
    next_epoch_start_slot = spec.compute_start_slot_at_epoch(next_epoch)
    seconds_until_next_epoch = next_epoch_start_slot * spec.SECONDS_PER_SLOT - store.time

    store.best_justified_checkpoint = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )

    run_on_tick(spec, store, store.time + seconds_until_next_epoch, True)


@with_all_phases
@spec_state_test
def test_no_update_same_slot_at_epoch_boundary(spec, state):
    store = spec.get_forkchoice_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    store.best_justified_checkpoint = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )

    # set store time to already be at epoch boundary
    store.time = seconds_per_epoch

    run_on_tick(spec, store, store.time + 1)


@with_all_phases
@spec_state_test
def test_no_update_not_epoch_boundary(spec, state):
    store = spec.get_forkchoice_store(state)

    store.best_justified_checkpoint = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )

    run_on_tick(spec, store, store.time + spec.SECONDS_PER_SLOT)


@with_all_phases
@spec_state_test
def test_no_update_new_justified_equal_epoch(spec, state):
    store = spec.get_forkchoice_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    store.best_justified_checkpoint = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )

    store.justified_checkpoint = spec.Checkpoint(
        epoch=store.best_justified_checkpoint.epoch,
        root=b'\44' * 32,
    )

    run_on_tick(spec, store, store.time + seconds_per_epoch)


@with_all_phases
@spec_state_test
def test_no_update_new_justified_later_epoch(spec, state):
    store = spec.get_forkchoice_store(state)
    seconds_per_epoch = spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    store.best_justified_checkpoint = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=b'\x55' * 32,
    )

    store.justified_checkpoint = spec.Checkpoint(
        epoch=store.best_justified_checkpoint.epoch + 1,
        root=b'\44' * 32,
    )

    run_on_tick(spec, store, store.time + seconds_per_epoch)
