from eth2spec.test.context import (
    spec_state_test,
    with_capella_and_later,
)

@with_capella_and_later
@spec_state_test
def test_validator_appears_only_once_in_attestation(spec, state):
    """
    A test to confirm that the validator_index of the validators in an attestation committee are unique and there
    are no duplicate validators
    """
    slot = state.slot
    epoch = slot // spec.SLOTS_PER_EPOCH

    # Get the number of committees assigned per slot in the current epoch
    slot_committee_count = spec.get_committee_count_per_slot(state, epoch)

    # Get the list of validators for each committee in the slot
    validators = []
    for committee in range(slot_committee_count):
        validator_index = spec.get_committee_assignment(state, epoch, committee)

        # There are tuples and individual validators in the list, so they need to be extracted
        if isinstance(validator_index, tuple):
            validators.extend(validator_index[0])
        elif isinstance(validator_index, list):
            validators.extend(validator_index)
        else:
            validators.append(validator_index)

    # Check that the assigned_validators list is not empty
    assert len(validators) > 0

    # Confirm that the same validator does not appear more than once in the list of validators
    validator_ids = set()
    for validator_id in validators:
        assert validator_id not in validator_ids
        validator_ids.add(validator_id)

    yield "committee_assignments", validator_ids