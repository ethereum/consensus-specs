from dataclasses import dataclass

from eth_consensus_specs.test.context import (
    MINIMAL,
    spec_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    ALTAIR,
    BELLATRIX,
    CAPELLA,
    DENEB,
    ELECTRA,
    FULU,
)
from eth_consensus_specs.test.helpers.fast_confirmation import (
    AdvanceSlot,
    Attesting,
    EmptySlotRun,
    FCRTest,
    Proposal,
    SlotRun,
    SlotSequence,
    SystemRun,
)


@dataclass
class CurrentEpochTestSpecification:
    head_uj_fresh: bool = (
        False  # <-> store.unrealized_justifications[head].epoch + 1 >= current_epoch
    )
    second_slot_call: bool = False  # <-> algorithm is called in the second slot of an epoch, this is the first slot when a block from the current epoch can possibly be confirmed
    first_block_in_epoch: bool = False  # <-> confirm the first block in the current epoch
    target_will_be_justified: bool = False  # <-> will_current_target_be_justified(store)
    is_one_confirmed: (
        bool  # <-> is_one_confirmed(store, get_current_balance_source(store), block_root)
    ) = False

    def verify_preconditions(self, spec, fcr_store):
        store = fcr_store.store
        head = spec.get_head(store)
        current_epoch = spec.get_current_store_epoch(store)
        current_slot = spec.get_current_slot(store)
        confirmed_epoch = spec.get_block_epoch(store, fcr_store.confirmed_root)
        canonical_roots = spec.get_ancestor_roots(store, head, fcr_store.confirmed_root)

        assert confirmed_epoch + 1 >= current_epoch
        assert current_slot % spec.SLOTS_PER_EPOCH > 0
        assert len(canonical_roots) > 0

        assert self.second_slot_call == (current_slot % spec.SLOTS_PER_EPOCH == 1)
        assert self.first_block_in_epoch == (confirmed_epoch + 1 == current_epoch)
        assert self.head_uj_fresh == (
            store.unrealized_justifications[head].epoch + 1 >= current_epoch
        )
        assert self.target_will_be_justified == spec.will_current_target_be_justified(store)
        if self.is_one_confirmed:
            is_one_confirmed_list = [
                spec.is_one_confirmed(store, spec.get_current_balance_source(fcr_store), root)
                for root in canonical_roots
            ]
            assert all(is_one_confirmed_list)
        else:
            assert not spec.is_one_confirmed(
                store, spec.get_current_balance_source(fcr_store), spec.get_head(store)
            )

    def get_expected_confirmed_root(self, spec, fcr_store):
        store = fcr_store.store
        confirmed_epoch = spec.get_block_epoch(store, fcr_store.confirmed_root)
        current_epoch = spec.get_current_store_epoch(store)

        if confirmed_epoch < current_epoch and not self.target_will_be_justified:
            return fcr_store.confirmed_root

        if self.head_uj_fresh and self.is_one_confirmed:
            # If any block is supposed to be confirmed
            # the head is always expected to be the most recent confirmed one
            return spec.get_head(store)
        else:
            return fcr_store.confirmed_root

    def first_block_at_mid_epoch(self):
        return self.first_block_in_epoch and not self.second_slot_call

    def one_confirmed_but_no_justification(self):
        return self.is_one_confirmed and not self.target_will_be_justified

    def first_block_in_second_slot(self):
        return self.first_block_in_epoch and self.second_slot_call


class CurrentEpochTestBuilder:
    def __init__(self, spec, state, seed, test_spec: CurrentEpochTestSpecification):
        self.spec = spec
        self.state = state
        self.seed = seed
        self.test_spec = test_spec

    def get_target_participation(self) -> int:
        if self.test_spec.is_one_confirmed:
            # Full participation
            return 100
        elif self.test_spec.target_will_be_justified:
            # Participation enough to justify a target
            # but not enough to fast confirm
            return 75
        else:
            # Participation enough neither to fast confirm
            # nor to justify a target
            return 0

    def initial_run_and_end_epoch(self) -> (list[SystemRun], int):
        if self.test_spec.head_uj_fresh:
            # Run to the second epoch
            run = [SlotSequence(number_of_slots=self.spec.SLOTS_PER_EPOCH)]
            return run, 2
        else:
            # Run to the second epoch and then
            # run for an epoch with low onchain attestation inclusion
            # to prevent UJ update while keep fast confirming blocks
            run = [
                # Run to the second epoch
                SlotSequence(number_of_slots=self.spec.SLOTS_PER_EPOCH),
                # Slots with full inclusion at the beginning
                SlotSequence(
                    number_of_slots=self.spec.SLOTS_PER_EPOCH * 2 // 3,
                    proposal=Proposal(atts_in_block=True),
                ),
                # Up to the next epoch start with zero enclusion
                SlotSequence(
                    end_slot=2 * self.spec.SLOTS_PER_EPOCH, proposal=Proposal(atts_in_block=False)
                ),
            ]
            return run, 3

    def first_block_in_second_slot_run(self) -> list[SystemRun]:
        return [
            SlotRun(
                # Prevent UJ update unless UJ must be fresh
                proposal=Proposal(atts_in_block=self.test_spec.head_uj_fresh),
                attesting=Attesting(participation_rate=self.get_target_participation()),
                advance_slot=AdvanceSlot(with_fast_confirmation=False),
            )
        ]

    def no_justification_final_run(self, end_epoch) -> list[SystemRun]:
        # Sequence of empty slots with participation enough to one confirm
        # but not enough to justify
        return [
            SlotSequence(
                end_slot=end_epoch * self.spec.SLOTS_PER_EPOCH - 2,
                proposal=Proposal(enabled=False),
                attesting=Attesting(participation_rate=75),
            ),
            # Attest and advance slot with no fast confirmation
            # fast confirmation will be triggered by the test runner
            # later into the process
            EmptySlotRun(
                attesting=Attesting(participation_rate=self.get_target_participation()),
                advance_slot=AdvanceSlot(with_fast_confirmation=False),
            ),
        ]

    def regular_final_run(self) -> list[SystemRun]:
        # Attest and advance slot with no fast confirmation
        # fast confirmation will be triggered by the test runner
        # later into the process
        return [
            Attesting(participation_rate=self.get_target_participation()),
            AdvanceSlot(with_fast_confirmation=False),
        ]

    def confirm_at_mid_epoch_final_run(self, end_epoch) -> list[SystemRun]:
        if self.test_spec.one_confirmed_but_no_justification():
            return self.no_justification_final_run(end_epoch)
        else:
            return self.regular_final_run()

    def first_block_at_mid_epoch_run(self, end_epoch) -> list[SystemRun]:
        # Move on to the second slot in an epoch
        # with proposal and participation low enough to prevent confirming a proposed block
        # but still enough to confirm it a slot after if needed
        run = [
            SlotRun(
                proposal=Proposal(atts_in_block=self.test_spec.head_uj_fresh),
                attesting=Attesting(participation_rate=85),
            ),
        ]

        # Finalize
        run.extend(self.confirm_at_mid_epoch_final_run(end_epoch))

        return run

    def second_block_at_mid_epoch_run(self, end_epoch) -> list[SystemRun]:
        if self.test_spec.head_uj_fresh:
            # Move on to the seconds slot in an epoch with confirmation and child block proposal,
            # then attempt to confirm a child block
            run = [SlotRun(), Proposal()]
        else:
            # Create the following block tree:
            #   B
            #  /
            # A -- H, where:
            #
            # UJ[B].epoch == current_epoch - 1
            # UJ[H].epoch == current_epoch - 2
            run = [
                # Create A and attest to A
                SlotRun(proposal=Proposal(atts_in_block=False)),
                # Create B but attest to A
                # B includes attestations from previous epoch enough to update UJ
                SlotRun(
                    proposal=Proposal(atts_in_block=True),
                    attesting=Attesting(block_id=-1),
                ),
                # Create H and attest to it, so H becomes the head, confirm A
                SlotRun(proposal=Proposal(parent_id=-2)),
                # Prevent UJ update unless UJ must be fresh
                Proposal(atts_in_block=False),
            ]

        # Finalize
        run.extend(self.confirm_at_mid_epoch_final_run(end_epoch))

        return run

    def create_system_runs(self) -> list[SystemRun]:
        test_spec = self.test_spec
        if test_spec.second_slot_call:
            assert test_spec.first_block_in_epoch, "Impossible in the second slot of an epoch"
        if test_spec.one_confirmed_but_no_justification():
            assert not test_spec.first_block_in_second_slot(), "Impossible with beta = 25%"

        # Initial run
        init, end_epoch = self.initial_run_and_end_epoch()

        if test_spec.first_block_in_second_slot():
            return init + self.first_block_in_second_slot_run()
        elif self.test_spec.first_block_at_mid_epoch():
            return init + self.first_block_at_mid_epoch_run(end_epoch)
        else:
            return init + self.second_block_at_mid_epoch_run(end_epoch)

    def build(self):
        fcr_test = FCRTest(self.spec, self.seed)
        fcr_test.initialize(self.state)
        for run in self.create_system_runs():
            run.execute(fcr_test)
            fcr_test.print_fast_confirmation_state()

        # Check preconditions are correct
        self.test_spec.verify_preconditions(fcr_test.spec, fcr_test.fcr_store)

        return fcr_test


def run_current_epoch_test(fcr_test: FCRTest, test_spec: CurrentEpochTestSpecification):
    # Keep expected confirmed_root after execution of the test
    exptected_confirmed_root = test_spec.get_expected_confirmed_root(
        fcr_test.spec, fcr_test.fcr_store
    )
    # Execute FCR and check that confirmed_root is as expected
    fcr_test.run_fast_confirmation()
    assert fcr_test.fcr_store.confirmed_root == exptected_confirmed_root

    yield from fcr_test.get_test_artefacts()


def build_and_run_current_epoch_test(spec, state, seed, test_spec: CurrentEpochTestSpecification):
    test_builder = CurrentEpochTestBuilder(spec, state, seed, test_spec)
    fcr_test = test_builder.build()
    yield from run_current_epoch_test(fcr_test, test_spec)


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
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


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_18(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=False,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 18, test_spec)


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_19(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=False,
        target_will_be_justified=False,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 19, test_spec)


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_20(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=True,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=False,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 20, test_spec)


@with_phases([ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_current_epoch_21(spec, state):
    test_spec = CurrentEpochTestSpecification(
        head_uj_fresh=False,
        second_slot_call=False,
        first_block_in_epoch=True,
        target_will_be_justified=False,
        is_one_confirmed=True,
    )
    yield from build_and_run_current_epoch_test(spec, state, 21, test_spec)
