import random

from eth_consensus_specs.test.context import (
    always_bls,
    default_activation_threshold,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_heze_and_later,
)
from eth_consensus_specs.test.helpers.inclusion_list import get_empty_inclusion_list
from eth_consensus_specs.test.helpers.keys import privkeys, pubkeys
from eth_consensus_specs.test.phase0.unittests.validator.test_validator_unittest import (
    run_get_signature_test,
)


def inclusion_committee_balances(spec):
    return [spec.MAX_EFFECTIVE_BALANCE] * spec.SLOTS_PER_EPOCH * spec.INCLUSION_LIST_COMMITTEE_SIZE


def run_get_inclusion_list_committee_assignments(spec, state, epoch, valid=True):
    rng = random.Random(7805)

    start_slot = spec.compute_start_slot_at_epoch(epoch)
    end_slot = start_slot + spec.SLOTS_PER_EPOCH
    some_slots = rng.sample(range(start_slot, end_slot), 3)

    inclusion_assignments = [(None, None, len(state.validators))]
    for slot in some_slots:
        committee = spec.get_inclusion_list_committee(state, slot)
        for validator_index in rng.sample(committee, 3):
            inclusion_assignments.append((slot, committee, validator_index))

    for slot, committee, validator_index in inclusion_assignments:
        try:
            assigned_slot = spec.get_inclusion_list_committee_assignment(
                state, epoch, validator_index
            )
            assert assigned_slot == slot
            if assigned_slot is not None:
                assert spec.compute_epoch_at_slot(assigned_slot) == epoch
                assert validator_index in committee
        except AssertionError:
            assert not valid
        else:
            assert valid


@with_heze_and_later
@spec_test
@with_custom_state(
    balances_fn=inclusion_committee_balances, threshold_fn=default_activation_threshold
)
@single_phase
def test_get_inclusion_committee_assignment_current_epoch(spec, state):
    epoch = spec.get_current_epoch(state)
    run_get_inclusion_list_committee_assignments(spec, state, epoch, valid=True)


@with_heze_and_later
@spec_test
@with_custom_state(
    balances_fn=inclusion_committee_balances, threshold_fn=default_activation_threshold
)
@single_phase
def test_get_inclusion_committee_assignment_next_epoch(spec, state):
    epoch = spec.get_current_epoch(state) + 1
    run_get_inclusion_list_committee_assignments(spec, state, epoch, valid=True)


@with_heze_and_later
@spec_test
@with_custom_state(
    balances_fn=inclusion_committee_balances, threshold_fn=default_activation_threshold
)
@single_phase
def test_get_inclusion_committee_assignment_out_bound_epoch(spec, state):
    epoch = spec.get_current_epoch(state) + 2
    run_get_inclusion_list_committee_assignments(spec, state, epoch, valid=False)


@with_heze_and_later
@spec_state_test
@always_bls
def test_get_inclusion_list_signature(spec, state):
    inclusion_list = get_empty_inclusion_list(spec, state)
    domain = spec.get_domain(
        state, spec.DOMAIN_INCLUSION_LIST_COMMITTEE, spec.compute_epoch_at_slot(inclusion_list.slot)
    )
    privkey = privkeys[0]
    pubkey = pubkeys[0]
    run_get_signature_test(
        spec=spec,
        state=state,
        obj=inclusion_list,
        domain=domain,
        get_signature_fn=spec.get_inclusion_list_signature,
        privkey=privkey,
        pubkey=pubkey,
    )
