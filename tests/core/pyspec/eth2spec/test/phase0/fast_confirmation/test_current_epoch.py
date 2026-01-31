from eth2spec.test.context import (
    MINIMAL,
    spec_state_test,
    with_altair_and_later,
    with_presets,
)
from eth2spec.test.helpers.fast_confirmation import (
    CurrentEpochTestBuilder,
    CurrentEpochTestSpecification,
    FCRTest,
)


def run_current_epoch_test(fcr_test: FCRTest, test_spec: CurrentEpochTestSpecification):
    # Keep expected confirmed_root after execution of the test
    exptected_confirmed_root = test_spec.get_expected_confirmed_root(fcr_test.spec, fcr_test.store)
    # Execute FCR and check that confirmed_root is as expected
    fcr_test.run_fast_confirmation()
    assert fcr_test.store.confirmed_root == exptected_confirmed_root

    yield from fcr_test.get_test_artefacts()


def build_and_run_current_epoch_test(spec, state, seed, test_spec: CurrentEpochTestSpecification):
    test_builder = CurrentEpochTestBuilder(spec, state, seed, test_spec)
    fcr_test = test_builder.build()
    yield from run_current_epoch_test(fcr_test, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_00(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=True,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 0, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_01(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=True,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 1, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_02(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=True,
        first_block_in_epoch=True,
        target_will_be_justified=False,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 2, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_03(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=True,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 3, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_04(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=True,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 4, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_05(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=False,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 5, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_06(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 6, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_07(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 7, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_08(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=False,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 8, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_09(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=True,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 9, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_10(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=True,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 10, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_11(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=True,
        first_block_in_epoch=True,
        target_will_be_justified=False,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 11, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_12(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=True,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 12, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_13(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=True,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 13, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_14(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=False,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 14, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_15(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 15, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_16(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=True,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 16, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_17(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=False,
        is_one_confirmed=False,
    )
    yield from build_and_run_current_epoch_test(spec, state, 17, test_spec)
