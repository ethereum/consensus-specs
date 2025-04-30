from eth2spec.test._deprecated.helpers.custody import (
    get_valid_custody_slashing,
    get_custody_slashable_shard_transition,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.ssz.ssz_typing import ByteList
from eth2spec.test.helpers.state import get_balance, transition_to
from eth2spec.test.context import (
    with_phases,
    spec_state_test,
    expect_assertion_error,
    disable_process_reveal_deadlines,
    with_presets,
)
from eth2spec.test.phase0.block_processing.test_process_attestation import (
    run_attestation_processing,
)
from eth2spec.test.helpers.typing import SpecForkName

CUSTODY_GAME = SpecForkName("custody_game")


def run_custody_slashing_processing(spec, state, custody_slashing, valid=True, correct=True):
    """
    Run ``process_bit_challenge``, yielding:
      - pre-state ('pre')
      - CustodySlashing ('custody_slashing')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "custody_slashing", custody_slashing

    if not valid:
        expect_assertion_error(lambda: spec.process_custody_slashing(state, custody_slashing))
        yield "post", None
        return

    if correct:
        pre_slashed_balance = get_balance(state, custody_slashing.message.malefactor_index)
    else:
        pre_slashed_balance = get_balance(state, custody_slashing.message.whistleblower_index)

    spec.process_custody_slashing(state, custody_slashing)

    if correct:
        slashed_validator = state.validators[custody_slashing.message.malefactor_index]
        assert get_balance(state, custody_slashing.message.malefactor_index) < pre_slashed_balance
    else:
        slashed_validator = state.validators[custody_slashing.message.whistleblower_index]
        assert (
            get_balance(state, custody_slashing.message.whistleblower_index) < pre_slashed_balance
        )

    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    yield "post", state


def run_standard_custody_slashing_test(
    spec,
    state,
    shard_lateness=None,
    shard=None,
    validator_index=None,
    block_lengths=None,
    slashing_message_data=None,
    correct=True,
    valid=True,
):
    transition_to(spec, state, state.slot + 1)  # Make len(offset_slots) == 1
    if shard_lateness is None:
        shard_lateness = spec.SLOTS_PER_EPOCH
    transition_to(spec, state, state.slot + shard_lateness)

    if shard is None:
        shard = 0
    if validator_index is None:
        validator_index = spec.get_beacon_committee(state, state.slot, shard)[0]

    offset_slots = spec.get_offset_slots(state, shard)
    if block_lengths is None:
        block_lengths = [2**15 // 3] * len(offset_slots)

    custody_secret = spec.get_custody_secret(
        state,
        validator_index,
        privkeys[validator_index],
        spec.get_current_epoch(state),
    )
    shard_transition, slashable_test_vector = get_custody_slashable_shard_transition(
        spec,
        state.slot,
        block_lengths,
        custody_secret,
        slashable=correct,
    )

    attestation = get_valid_attestation(
        spec, state, index=shard, signed=True, shard_transition=shard_transition
    )

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    transition_to(
        spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1)
    )

    slashing = get_valid_custody_slashing(
        spec, state, attestation, shard_transition, custody_secret, slashable_test_vector
    )

    if slashing_message_data is not None:
        slashing.message.data = slashing_message_data

    yield from run_custody_slashing_processing(spec, state, slashing, valid=valid, correct=correct)


@with_phases([CUSTODY_GAME])
@spec_state_test
@disable_process_reveal_deadlines
@with_presets([MINIMAL], reason="too slow")
def test_custody_slashing(spec, state):
    yield from run_standard_custody_slashing_test(spec, state)


@with_phases([CUSTODY_GAME])
@spec_state_test
@disable_process_reveal_deadlines
@with_presets([MINIMAL], reason="too slow")
def test_incorrect_custody_slashing(spec, state):
    yield from run_standard_custody_slashing_test(spec, state, correct=False)


@with_phases([CUSTODY_GAME])
@spec_state_test
@disable_process_reveal_deadlines
@with_presets([MINIMAL], reason="too slow")
def test_multiple_epochs_custody(spec, state):
    yield from run_standard_custody_slashing_test(
        spec, state, shard_lateness=spec.SLOTS_PER_EPOCH * 3
    )


@with_phases([CUSTODY_GAME])
@spec_state_test
@disable_process_reveal_deadlines
@with_presets([MINIMAL], reason="too slow")
def test_many_epochs_custody(spec, state):
    yield from run_standard_custody_slashing_test(
        spec, state, shard_lateness=spec.SLOTS_PER_EPOCH * 5
    )


@with_phases([CUSTODY_GAME])
@spec_state_test
@disable_process_reveal_deadlines
@with_presets([MINIMAL], reason="too slow")
def test_invalid_custody_slashing(spec, state):
    yield from run_standard_custody_slashing_test(
        spec,
        state,
        slashing_message_data=ByteList[spec.MAX_SHARD_BLOCK_SIZE](),
        valid=False,
    )
