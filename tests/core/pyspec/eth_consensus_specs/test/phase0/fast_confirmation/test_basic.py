from eth_consensus_specs.test.context import (
    MINIMAL,
    never_bls,
    only_generator,
    spec_state_test,
    with_altair_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.fast_confirmation import (
    FCRTest,
)


@only_generator("too slow")
@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
@never_bls
def test_fast_confirm_an_epoch(spec, state):
    fcr_test = FCRTest(spec, seed=1)
    _, fcr_store = fcr_test.initialize(state)
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr_test.next_slot_with_block_and_fast_confirmation(participation_rate=100)
        # Ensure head is confirmed
        assert fcr_store.confirmed_root == fcr_test.head_root()

    yield from fcr_test.get_test_artefacts()


@only_generator("too slow")
@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
@never_bls
def test_fast_confirm_with_low_participation(spec, state):
    fcr_test = FCRTest(spec, seed=1)
    store, fcr_store = fcr_test.initialize(state)
    for _ in range(3 * spec.SLOTS_PER_EPOCH):
        fcr_test.next_slot_with_block_and_fast_confirmation(participation_rate=90)
        # Ensure confirmed block is being advanced
        assert spec.get_block_epoch(store, fcr_store.confirmed_root) + 1 >= fcr_test.current_epoch()

    yield from fcr_test.get_test_artefacts()


@only_generator("too slow")
@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
@never_bls
def test_fast_confirm_with_asynchrony_at_epoch_boundary(spec, state):
    fcr_test = FCRTest(spec, seed=1)
    store, fcr_store = fcr_test.initialize(state)

    # Move closer to epoch boundary
    while fcr_test.current_slot() < spec.SLOTS_PER_EPOCH - 2:
        fcr_test.next_slot_with_block_and_fast_confirmation(participation_rate=100)
        # Ensure confirmed block is being advanced
        assert fcr_store.confirmed_root == fcr_test.head_root()

    # Run for a few slots with asynchrony
    while fcr_test.current_slot() < spec.SLOTS_PER_EPOCH + 2:
        fcr_test.next_slot_with_block_and_fast_confirmation(participation_rate=75)
        # Confirmed block is behind the head
        assert fcr_store.confirmed_root != fcr_test.head_root()

    # Restore participation and run for an epoch
    for _ in range(spec.SLOTS_PER_EPOCH):
        fcr_test.next_slot_with_block_and_fast_confirmation(participation_rate=100)
        # Ensure confirmed block is being advanced
        assert spec.get_block_epoch(store, fcr_store.confirmed_root) + 1 >= fcr_test.current_epoch()

    # After asynchrony followed by a period of good participation FCR provides 1-slot delay
    fcr_test.next_slot_with_block_and_fast_confirmation(participation_rate=100)
    assert fcr_store.confirmed_root == fcr_test.head_root()

    yield from fcr_test.get_test_artefacts()
