from dataclasses import dataclass

from eth2spec.test.context import (
    MINIMAL,
    spec_state_test,
    with_altair_and_later,
    with_presets,
)
from eth2spec.test.helpers.fast_confirmation import (
    AdvanceSlot,
    Attesting,
    debug_print,
    FCRTest,
    Proposal,
    SlotRun,
    SlotSequence,
)


@dataclass
class PreviousEpochTestSpecification:
    prev_head_ancestor: bool  # is_ancestor(store, store.previous_slot_head, block_root)
    first_slot_call: bool  # is_start_slot_at_epoch(get_current_slot(store))
    is_one_confirmed: bool  # is_one_confirmed(store, get_current_balance_source(store), block_root)
    no_conflicting_chkp: bool  # will_no_conflicting_checkpoint_be_justified(store)
    vs_prev_head_fresh: (
        bool  # get_voting_source(store, store.previous_slot_head).epoch + 2 >= current_epoch
    )
    prev_head_uj_fresh: (
        bool  # store.unrealized_justifications[store.previous_slot_head].epoch + 1 >= current_epoch
    )
    vs_block_fresh: (
        bool  # get_voting_source(store, tentative_confirmed_root).epoch + 2 >= current_epoch
    )
    head_uj_fresh: bool  # store.unrealized_justifications[head].epoch + 1 >= current_epoch

    def get_prev_epoch_canonical_roots(self, spec, store):
        head = spec.get_head(store)
        current_epoch = spec.get_current_store_epoch(store)
        canonical_roots = spec.get_ancestor_roots(store, head, store.confirmed_root)
        return [
            root
            for root in canonical_roots
            if spec.get_block_epoch(store, root) + 1 == current_epoch
        ]

    def verify_preconditions(self, spec, store):
        head = spec.get_head(store)
        current_epoch = spec.get_current_store_epoch(store)
        current_slot = spec.get_current_slot(store)
        confirmed_epoch = spec.get_block_epoch(store, store.confirmed_root)
        prev_epoch_canonical_roots = self.get_prev_epoch_canonical_roots(spec, store)
        # store.prev_slot_head = store.current_slot_head will become True
        # after the update_fast_confirmation_variables call
        # use store.current_slot_head as the future value of 'previous_slot_head' to check preconditions
        will_be_prev_slot_head = store.current_slot_head

        assert confirmed_epoch + 1 == current_epoch
        assert len(prev_epoch_canonical_roots) > 0

        assert self.first_slot_call == (current_slot % spec.SLOTS_PER_EPOCH == 0)
        assert self.head_uj_fresh == (
            store.unrealized_justifications[head].epoch + 1 >= current_epoch
        )
        assert self.prev_head_uj_fresh == (
            store.unrealized_justifications[will_be_prev_slot_head].epoch + 1 >= current_epoch
        )
        assert self.vs_prev_head_fresh == (
            spec.get_voting_source(store, will_be_prev_slot_head).epoch + 2 >= current_epoch
        )
        assert self.prev_head_ancestor == (
            spec.is_ancestor(store, will_be_prev_slot_head, prev_epoch_canonical_roots[0])
        )
        assert self.vs_block_fresh == (
            spec.get_voting_source(store, prev_epoch_canonical_roots[-1]).epoch + 2 >= current_epoch
        )
        assert self.no_conflicting_chkp == spec.will_no_conflicting_checkpoint_be_justified(store)

        if self.is_one_confirmed:
            assert spec.is_one_confirmed(
                store, spec.get_current_balance_source(store), prev_epoch_canonical_roots[0]
            )
        else:
            assert not spec.is_one_confirmed(
                store, spec.get_current_balance_source(store), prev_epoch_canonical_roots[0]
            )

    def get_last_one_confirmed_block(self, spec, store):
        head = spec.get_head(store)
        canonical_roots = spec.get_ancestor_roots(store, head, store.confirmed_root)
        balance_source = spec.get_current_balance_source(store)
        confirmed_root = store.confirmed_root
        for root in canonical_roots:
            if spec.is_one_confirmed(store, balance_source, root):
                confirmed_root = root
            else:
                break

        return confirmed_root

    def get_expected_confirmed_root(self, spec, store):
        if not self.is_one_confirmed:
            return store.confirmed_root

        if not (self.no_conflicting_chkp or self.first_slot_call):
            return store.confirmed_root

        if (self.vs_prev_head_fresh and self.prev_head_ancestor) and (
            self.first_slot_call or self.prev_head_uj_fresh or self.head_uj_fresh
        ):
            return self.get_last_one_confirmed_block(spec, store)
        elif self.vs_block_fresh and (self.first_slot_call or self.head_uj_fresh):
            return self.get_last_one_confirmed_block(spec, store)
        else:
            return store.confirmed_root

    def vs_and_uj_are_fresh(self):
        return (
            self.vs_block_fresh
            and self.vs_prev_head_fresh
            and self.head_uj_fresh
            and self.prev_head_uj_fresh
        )


class PreviousEpochTestBuilder:
    def __init__(self, spec, state, seed, test_spec: PreviousEpochTestSpecification):
        self.spec = spec
        self.state = state
        self.seed = seed
        self.test_spec = test_spec

    def create_first_slot_call_runs(self):
        target_slot = self.spec.SLOTS_PER_EPOCH - 3
        # Run till the target slot with 100% participation
        runs = [
            SlotSequence(number_of_slots=target_slot, attesting=Attesting(participation_rate=100))
        ]

        if self.test_spec.is_one_confirmed:
            target_block_rate = 100
        else:
            # Low participation rate but still enough to pass reconfirmation
            target_block_rate = 75

        if self.test_spec.prev_head_ancestor:
            #   prev_epoch      | curr_epoch
            #                   |
            # B_c - T - p_H - H |
            #                   |
            prev_head_parent_slot = target_slot
            head_parent_slot = target_slot + 1
        else:
            # prev_epoch   | curr_epoch
            #              |
            #      - p_H   |
            #    /         |
            # B_c - T -- H |
            #              |
            prev_head_parent_slot = target_slot - 1
            head_parent_slot = target_slot

        runs.extend(
            [
                # Build target block, do not attest
                SlotRun(attesting=Attesting(participation_rate=0)),
                # Build previous_slot_head, ensure it becomes a head by giving it a little support
                SlotRun(
                    proposal=Proposal(parent_root_slot_or_offset=prev_head_parent_slot),
                    attesting=Attesting(participation_rate=13),
                ),
                # Build head, attest to head and target
                SlotRun(
                    proposal=Proposal(parent_root_slot_or_offset=head_parent_slot),
                    attesting=[
                        Attesting(participation_rate=83),
                        Attesting(
                            committee_slot_or_offset=[target_slot, target_slot + 1],
                            block_slot_or_offset=target_slot,
                            participation_rate=target_block_rate,
                        ),
                    ],
                    advance_slot=AdvanceSlot(with_fast_confirmation=False),
                ),
            ]
        )

        return runs

    def create_mid_epoch_call_runs(self):
        target_slot = self.spec.SLOTS_PER_EPOCH - 2
        # Run till the target slot with 100% participation
        runs = [
            SlotSequence(number_of_slots=target_slot, attesting=Attesting(participation_rate=100))
        ]

        if self.test_spec.is_one_confirmed:
            target_block_rate = 100
        else:
            # Reduce head rate to make is_one_confirmed fail
            target_block_rate = 50

        if self.test_spec.prev_head_ancestor:
            #   prev_epoch | curr_epoch
            #              |
            # B_c - T - B -|- p_H - H
            #              |
            block_parents = [target_slot, target_slot + 1, target_slot + 2]
        else:
            # prev_epoch | curr_epoch
            #            |
            #      - p_H |
            #    /       |
            # B_c - T ---|- B - H
            #            |
            block_parents = [target_slot - 1, target_slot, target_slot + 2]

        runs.extend(
            [
                # Build target block
                SlotRun(attesting=Attesting(participation_rate=60)),
                # Build a potentially previous_slot_head,
                # add a bunch of votes to make it a head for a short time
                SlotRun(
                    proposal=Proposal(parent_root_slot_or_offset=block_parents[0]),
                    attesting=Attesting(participation_rate=85),
                ),
                # Build one more block to gain additional weight in the case of empty slot
                SlotRun(
                    proposal=Proposal(parent_root_slot_or_offset=block_parents[1]),
                    # No attestations as we don't want the head to be changed yet
                    attesting=Attesting(participation_rate=0),
                ),
                # Build head
                SlotRun(
                    proposal=Proposal(parent_root_slot_or_offset=block_parents[2]),
                    attesting=Attesting(participation_rate=0),
                    advance_slot=AdvanceSlot(next_slot=False),
                ),
            ]
        )

        if self.test_spec.no_conflicting_chkp:
            # Attest and next slot
            runs.extend(
                [
                    # attest to head
                    Attesting(participation_rate=target_block_rate),
                    # attest to an interim block
                    Attesting(
                        committee_slot_or_offset=-1,
                        block_slot_or_offset=-1,
                        participation_rate=target_block_rate,
                    ),
                    # attest to the target
                    Attesting(
                        committee_slot_or_offset=[target_slot, target_slot + 1],
                        block_slot_or_offset=target_slot,
                        participation_rate=target_block_rate,
                    ),
                    # next slot
                    AdvanceSlot(with_fast_confirmation=False),
                ]
            )
        else:
            runs.extend(
                [
                    # next slot
                    AdvanceSlot(),
                    # sequence of empty slots with no attestations
                    SlotSequence(
                        number_of_slots=4,
                        proposal=Proposal(enabled=False),
                        attesting=Attesting(participation_rate=0),
                    ),
                    # attest to target by several committees
                    Attesting(
                        block_slot_or_offset=target_slot,
                        committee_slot_or_offset=[0, -1, -2, -3, -4, -5, -6],
                        participation_rate=target_block_rate,
                    ),
                    AdvanceSlot(with_fast_confirmation=False),
                ]
            )

        return runs

    def create_vs_and_uj_are_fresh_runs(self):
        assert self.test_spec.vs_and_uj_are_fresh()

        if self.test_spec.first_slot_call:
            return self.create_first_slot_call_runs()
        else:
            return self.create_mid_epoch_call_runs()

    def create_system_runs(self):
        if self.test_spec.first_slot_call:
            assert self.test_spec.no_conflicting_chkp, "Impossible in the first slot of an epoch"

        if self.test_spec.vs_and_uj_are_fresh():
            return self.create_vs_and_uj_are_fresh_runs()
        else:
            assert False, "Unsupported"

    def build(self):
        fcr_test = FCRTest(self.spec, self.seed)
        fcr_test.initialize(self.state)

        debug_print("\n")

        for run in self.create_system_runs():
            run.execute(fcr_test)
            fcr_test.print_fast_confirmation_state()

        # Check preconditions are correct
        self.test_spec.verify_preconditions(fcr_test.spec, fcr_test.store)

        return fcr_test


def run_previous_epoch_test(fcr_test: FCRTest, test_spec: PreviousEpochTestSpecification):
    # Keep expected confirmed_root after execution of the test
    exptected_confirmed_root = test_spec.get_expected_confirmed_root(fcr_test.spec, fcr_test.store)
    # Execute FCR and check that confirmed_root is as expected
    fcr_test.run_fast_confirmation()
    assert fcr_test.store.confirmed_root == exptected_confirmed_root

    yield from fcr_test.get_test_artefacts()


def build_and_run_previous_epoch_test(spec, state, seed, test_spec: PreviousEpochTestSpecification):
    test_builder = PreviousEpochTestBuilder(spec, state, seed, test_spec)
    fcr_test = test_builder.build()
    yield from run_previous_epoch_test(fcr_test, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_00(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 0, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_01(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 1, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_02(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 2, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_03(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 3, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_04(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 4, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_05(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 5, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_06(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 6, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_07(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 7, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_08(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 8, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_09(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 9, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_10(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 10, test_spec)


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_11(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        vs_prev_head_fresh=True,
        prev_head_uj_fresh=True,
        vs_block_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 11, test_spec)
