from dataclasses import dataclass

from eth_consensus_specs.test.context import (
    MINIMAL,
    spec_state_test,
    with_all_phases_from_to,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    ALTAIR,
    FULU,
)
from eth_consensus_specs.test.helpers.fast_confirmation import (
    AdvanceSlot,
    Attesting,
    debug_print,
    EmptySlotRun,
    FCRTest,
    graffiti_to_str,
    Proposal,
    Slashing,
    SlotRun,
    SlotSequence,
)


@dataclass
class PreviousEpochTestSpecification:
    prev_head_ancestor: bool  # is_ancestor(store, fcr_store.previous_slot_head, block_root)
    first_slot_call: bool  # is_start_slot_at_epoch(get_current_slot(store))
    is_one_confirmed: bool  # is_one_confirmed(store, get_current_balance_source(store), block_root)
    no_conflicting_chkp: bool  # will_no_conflicting_checkpoint_be_justified(store)
    prev_head_vs_fresh: (
        bool  # get_voting_source(store, fcr_store.previous_slot_head).epoch + 2 >= current_epoch
    )
    prev_head_uj_fresh: bool  # store.unrealized_justifications[fcr_store.previous_slot_head].epoch + 1 >= current_epoch
    block_vs_fresh: (
        bool  # get_voting_source(store, tentative_confirmed_root).epoch + 2 >= current_epoch
    )
    head_uj_fresh: bool  # store.unrealized_justifications[head].epoch + 1 >= current_epoch

    def get_prev_epoch_canonical_roots(self, spec, fcr_store):
        store = fcr_store.store
        head = spec.get_head(store)
        current_epoch = spec.get_current_store_epoch(store)
        canonical_roots = spec.get_ancestor_roots(store, head, fcr_store.confirmed_root)
        return [
            root
            for root in canonical_roots
            if spec.get_block_epoch(store, root) + 1 == current_epoch
        ]

    def verify_preconditions(self, spec, fcr_store):
        store = fcr_store.store
        head = spec.get_head(store)
        current_epoch = spec.get_current_store_epoch(store)
        current_slot = spec.get_current_slot(store)
        confirmed_epoch = spec.get_block_epoch(store, fcr_store.confirmed_root)
        prev_epoch_canonical_roots = self.get_prev_epoch_canonical_roots(spec, fcr_store)
        # fcr_store.prev_slot_head = fcr_store.current_slot_head will become True
        # after the update_fast_confirmation_variables call
        # use fcr_store.current_slot_head as the future value of 'previous_slot_head' to check preconditions
        will_be_prev_slot_head = fcr_store.current_slot_head

        assert confirmed_epoch + 1 == current_epoch
        assert len(prev_epoch_canonical_roots) > 0

        assert self.first_slot_call == (current_slot % spec.SLOTS_PER_EPOCH == 0)
        assert self.head_uj_fresh == (
            store.unrealized_justifications[head].epoch + 1 >= current_epoch
        )
        assert self.prev_head_uj_fresh == (
            store.unrealized_justifications[will_be_prev_slot_head].epoch + 1 >= current_epoch
        )
        assert self.prev_head_vs_fresh == (
            spec.get_voting_source(store, will_be_prev_slot_head).epoch + 2 >= current_epoch
        )
        assert self.prev_head_ancestor == (
            spec.is_ancestor(store, will_be_prev_slot_head, prev_epoch_canonical_roots[0])
        )
        assert self.block_vs_fresh == (
            spec.get_voting_source(store, prev_epoch_canonical_roots[0]).epoch + 2 >= current_epoch
        )
        assert self.no_conflicting_chkp == spec.will_no_conflicting_checkpoint_be_justified(store)

        if self.is_one_confirmed:
            assert spec.is_one_confirmed(
                store, spec.get_current_balance_source(fcr_store), prev_epoch_canonical_roots[0]
            )
        else:
            assert not spec.is_one_confirmed(
                store, spec.get_current_balance_source(fcr_store), prev_epoch_canonical_roots[0]
            )

    def get_last_one_confirmed_block(self, spec, fcr_store):
        store = fcr_store.store
        head = spec.get_head(store)
        canonical_roots = spec.get_ancestor_roots(store, head, fcr_store.confirmed_root)
        balance_source = spec.get_current_balance_source(fcr_store)
        confirmed_root = fcr_store.confirmed_root
        for root in canonical_roots:
            if spec.is_one_confirmed(store, balance_source, root):
                confirmed_root = root
            else:
                break

        return confirmed_root

    def get_expected_confirmed_root(self, spec, fcr_store):
        if not self.is_one_confirmed:
            return fcr_store.confirmed_root

        if not (self.no_conflicting_chkp or self.first_slot_call):
            return fcr_store.confirmed_root

        if (self.prev_head_vs_fresh and self.prev_head_ancestor) and (
            self.first_slot_call or self.prev_head_uj_fresh or self.head_uj_fresh
        ):
            return self.get_last_one_confirmed_block(spec, fcr_store)
        elif self.block_vs_fresh and (self.first_slot_call or self.head_uj_fresh):
            return self.get_last_one_confirmed_block(spec, fcr_store)
        else:
            return fcr_store.confirmed_root

    def is_vs_fresh(self):
        return self.block_vs_fresh and self.prev_head_vs_fresh

    def is_uj_fresh(self):
        return self.head_uj_fresh and self.prev_head_uj_fresh

    def vs_and_uj_are_fresh(self):
        return self.is_vs_fresh() and self.is_uj_fresh()


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
            SlotSequence(
                number_of_slots=target_slot - 1, attesting=Attesting(participation_rate=100)
            ),
            SlotRun(
                proposal=Proposal(graffiti="confirmed"), attesting=Attesting(participation_rate=100)
            ),
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
            prev_head_parent = "target"
        else:
            # prev_epoch   | curr_epoch
            #              |
            #      - p_H   |
            #    /         |
            # B_c - T -- H |
            #              |
            prev_head_parent = "confirmed"

        runs.extend(
            [
                # Build target block, do not attest
                SlotRun(
                    proposal=Proposal(graffiti="target", parent_id="confirmed"),
                    attesting=Attesting(participation_rate=0),
                ),
                # Build previous_slot_head, ensure it becomes a head by giving it a little support
                SlotRun(
                    proposal=Proposal(graffiti="prev_head", parent_id=prev_head_parent),
                    attesting=Attesting(participation_rate=13),
                ),
                # Build head, attest to head and target
                SlotRun(
                    proposal=Proposal(parent_id="target"),
                    attesting=[
                        Attesting(participation_rate=83),
                        Attesting(
                            committee_slot_or_offset=[target_slot, target_slot + 1],
                            block_id="target",
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
            SlotSequence(
                number_of_slots=target_slot - 1, attesting=Attesting(participation_rate=100)
            ),
            SlotRun(
                proposal=Proposal(graffiti="confirmed"), attesting=Attesting(participation_rate=100)
            ),
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
                SlotRun(
                    proposal=Proposal(graffiti="target"), attesting=Attesting(participation_rate=63)
                ),
                # Build a potentially previous_slot_head,
                # add a bunch of votes to make it a head for a short time
                SlotRun(
                    proposal=Proposal(parent_id=block_parents[0]),
                    attesting=Attesting(participation_rate=88),
                ),
                # Build one more block to gain additional weight in the case of empty slot
                SlotRun(
                    proposal=Proposal(parent_id=block_parents[1]),
                    # No attestations as we don't want the head to be changed yet
                    attesting=Attesting(participation_rate=0),
                ),
                # Build head
                SlotRun(
                    proposal=Proposal(parent_id=block_parents[2]),
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
                        block_id=-1,
                        participation_rate=target_block_rate,
                    ),
                    # attest to the target
                    Attesting(
                        committee_slot_or_offset=[target_slot, target_slot + 1],
                        block_id=target_slot,
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
                        block_id=target_slot,
                        committee_slot_or_offset=[0, -1, -2, -3, -4, -5, -6],
                        participation_rate=target_block_rate,
                    ),
                    AdvanceSlot(with_fast_confirmation=False),
                ]
            )

        return runs

    def create_stale_vs_and_uj_first_slot_runs(self):
        spec = self.spec
        test_spec = self.test_spec
        target_slot = 3 * spec.SLOTS_PER_EPOCH - 3
        target_epoch = spec.compute_epoch_at_slot(target_slot)

        if test_spec.prev_head_ancestor:
            #   prev_epoch     | curr_epoch
            #                  |
            #    f_H    p_H    |
            #    /     /       |
            # B_c --- T --- H  |
            #                  |
            prev_head_parent = "target"
        else:
            # prev_epoch       | curr_epoch
            #                  |
            #    f_H   - p_H   |
            #    /   /         |
            # B_c --- T --- H  |
            #                  |
            prev_head_parent = "confirmed"

        def include_att_fn(block, attestation) -> bool:
            epoch = spec.compute_epoch_at_slot(block.slot)
            graffiti = graffiti_to_str(block.body.graffiti)
            no_justification_boundary = epoch * spec.SLOTS_PER_EPOCH + spec.SLOTS_PER_EPOCH * 2 // 3

            if epoch == spec.GENESIS_EPOCH:
                return True

            if graffiti == "fake_head":
                # Fake head justifies prev checkpoint only
                return attestation.data.target.epoch < target_epoch

            if graffiti == "target":
                # If block_vs isn't fresh prevent justification of prev checkpoint
                return test_spec.block_vs_fresh

            if graffiti == "prev_head":
                # Prioritise curr epoch justification if prev_head_vs_fresh and prev_head_uj_fresh
                # as prev_head_uj_fresh implies prev_head_vs_fresh in this case
                if test_spec.prev_head_uj_fresh:
                    # If prev_head_uj isn't fresh prevent justification of curr checkpoint
                    return attestation.data.target.epoch == target_epoch
                elif test_spec.prev_head_vs_fresh:
                    # If prev_head_vs isn't fresh prevent justification of prev checkpoint
                    return attestation.data.target.epoch < target_epoch
                else:
                    return False

            if graffiti == "head":
                # If head_uj isn't fresh prevent justification of curr checkpoint
                return test_spec.head_uj_fresh or attestation.data.target.epoch < target_epoch

            if epoch == target_epoch - 1:
                return test_spec.is_vs_fresh() or block.slot <= no_justification_boundary

            if epoch == target_epoch:
                if attestation.data.target.epoch < target_epoch:
                    return test_spec.is_vs_fresh()
                else:
                    return (
                        test_spec.is_vs_fresh() and test_spec.head_uj_fresh
                    ) or block.slot <= no_justification_boundary

            return False

        # Run till the target slot with 100% participation, but prevent GU bump
        runs = [
            SlotSequence(
                end_slot=target_slot - 2,
                proposal=Proposal(include_att_fn=include_att_fn),
                attesting=Attesting(participation_rate=100),
            ),
            SlotRun(
                proposal=Proposal(graffiti="confirmed", include_att_fn=include_att_fn),
                attesting=Attesting(participation_rate=100),
            ),
        ]

        if test_spec.is_one_confirmed:
            head_block_rate = 100
        else:
            # Low participation rate but still enough to pass reconfirmation
            head_block_rate = 50

        # Do not vote on the target if it's not ancestor of prev head,
        # as then prev head wouldn't become a head
        if test_spec.prev_head_ancestor:
            prev_head_supporters_slashing_percentage = 0
            # Make "prev_head" weaker than "head"
            prev_head_participation = 25
        else:
            # Make "prev_head" stronger to be captured as prev_slot_head
            prev_head_participation = 50
            # In this case we need to slash a small fraction of "prev_head" supporters
            # to aid confirmation of the "target"
            if test_spec.is_one_confirmed:
                prev_head_supporters_slashing_percentage = 25
            else:
                prev_head_supporters_slashing_percentage = 0

        runs.extend(
            [
                # Build fake head block
                SlotRun(
                    proposal=Proposal(
                        graffiti="fake_head",
                        parent_id="confirmed",
                        include_att_fn=include_att_fn,
                        release_att_pool=False,
                    ),
                    attesting=Attesting(block_id="confirmed", participation_rate=100),
                ),
                # Build target block but do not attest yet
                SlotRun(
                    proposal=Proposal(
                        graffiti="target",
                        parent_id="confirmed",
                        include_att_fn=include_att_fn,
                        release_att_pool=False,
                    ),
                    # Attest to target before "prev_head" to have enough participation for justifying current epoch by "prev_head"
                    attesting=Attesting(participation_rate=38),
                ),
                # Build previous_slot_head, ensure it becomes a head by giving it a little support
                SlotRun(
                    proposal=Proposal(
                        graffiti="prev_head",
                        parent_id=prev_head_parent,
                        include_att_fn=include_att_fn,
                        release_att_pool=False,
                    ),
                    attesting=Attesting(participation_rate=prev_head_participation),
                ),
                # Attest to "target" before "head" is proposed to have enough participation for justifying current epoch by "head"
                Attesting(
                    committee_slot_or_offset=[target_slot, target_slot + 1],
                    block_id="target",
                    participation_rate=100,
                ),
                # Build head
                SlotRun(
                    proposal=Proposal(
                        graffiti="head", parent_id="target", include_att_fn=include_att_fn
                    ),
                    attesting=Attesting(participation_rate=head_block_rate),
                    advance_slot=AdvanceSlot(with_fast_confirmation=False),
                    slashing=Slashing(
                        supporters_of_block="prev_head",
                        percentage=prev_head_supporters_slashing_percentage,
                    ),
                ),
            ]
        )

        return runs

    def create_stale_vs_and_uj_mid_epoch_runs(self):
        spec = self.spec
        test_spec = self.test_spec
        if test_spec.prev_head_ancestor:
            target_slot = 3 * spec.SLOTS_PER_EPOCH - 3
        else:
            target_slot = 3 * spec.SLOTS_PER_EPOCH - 2
        target_epoch = spec.compute_epoch_at_slot(target_slot)

        def include_att_fn(block, attestation) -> bool:
            epoch = spec.compute_epoch_at_slot(block.slot)
            graffiti = graffiti_to_str(block.body.graffiti)
            no_justification_boundary = epoch * spec.SLOTS_PER_EPOCH + spec.SLOTS_PER_EPOCH * 2 // 3

            if epoch == spec.GENESIS_EPOCH:
                return True

            if graffiti == "fake_head":
                # Fake head justifies prev checkpoint only
                return attestation.data.target.epoch < target_epoch

            if graffiti == "target":
                # If block_vs isn't fresh prevent justification of prev checkpoint
                return test_spec.block_vs_fresh and attestation.data.target.epoch < target_epoch

            if graffiti == "middle":
                # Enforce fresh VS for "middle" and "head" inherently
                return attestation.data.target.epoch < target_epoch

            if graffiti == "prev_head":
                # Enforce prev_head_vs_fresh
                return test_spec.prev_head_uj_fresh or attestation.data.target.epoch < target_epoch

            if graffiti == "head":
                # If head_uj isn't fresh prevent justification of target checkpoint
                return test_spec.head_uj_fresh or attestation.data.target.epoch < target_epoch

            if epoch == target_epoch - 1:
                return test_spec.is_vs_fresh() or block.slot <= no_justification_boundary

            if epoch == target_epoch:
                if attestation.data.target.epoch < target_epoch:
                    return test_spec.is_vs_fresh()
                else:
                    return (
                        test_spec.is_vs_fresh() and test_spec.head_uj_fresh
                    ) or block.slot <= no_justification_boundary

            # The rest of Epoch 3
            return False

        # Run till the target slot with 100% participation
        runs = [
            SlotSequence(
                number_of_slots=target_slot - 2,
                proposal=Proposal(include_att_fn=include_att_fn),
                attesting=Attesting(participation_rate=100),
            ),
            SlotRun(
                proposal=Proposal(graffiti="confirmed", include_att_fn=include_att_fn),
                attesting=Attesting(participation_rate=100),
            ),
        ]

        if test_spec.is_one_confirmed:
            target_block_rate = 100
        else:
            # Reduce head rate to make is_one_confirmed fail
            target_block_rate = 0

        if test_spec.prev_head_ancestor:
            #   prev_epoch     | curr_epoch
            #                  |
            #    f_H    p_H    |
            #    /     /       |
            # B_c --- T --- M -|- H
            #                  |
            proposals = {
                "fake_head": Proposal(parent_id="confirmed"),
                "target": Proposal(parent_id="confirmed"),
                "prev_head": Proposal(parent_id="target"),
                "middle": Proposal(parent_id="target"),
                "head": Proposal(parent_id="middle"),
            }

            for k, p in proposals.items():
                p.graffiti = k
                p.include_att_fn = include_att_fn
                p.release_att_pool = False

            runs.extend(
                [
                    # Attest to "confirmed"
                    SlotRun(
                        proposal=proposals["fake_head"],
                        attesting=Attesting(block_id="confirmed", participation_rate=100),
                    ),
                    # Attest but prevent early confirmation of "target"
                    SlotRun(
                        proposal=proposals["target"], attesting=Attesting(participation_rate=63)
                    ),
                    # Attest just enough to outweigh "middle" and be captured as "prev_head"
                    SlotRun(
                        proposal=proposals["prev_head"],
                        attesting=Attesting(participation_rate=75),
                    ),
                    # Attest enough to make reconfirmation pass
                    SlotRun(
                        proposal=proposals["middle"],
                        attesting=Attesting(participation_rate=63),
                    ),
                    # No attestation yet in order to prevent early confirmation of "target"
                    SlotRun(
                        proposal=proposals["head"],
                        attesting=Attesting(participation_rate=0),
                        advance_slot=AdvanceSlot(next_slot=False),
                    ),
                ]
            )

            if test_spec.no_conflicting_chkp:
                # Attest enough to confirm if one_confirmed is required and next slot
                runs.extend(
                    [
                        # Attest to "head"
                        Attesting(block_id="head", participation_rate=100),
                        # Attest to "middle"
                        Attesting(
                            committee_slot_or_offset=target_slot + 2,
                            block_id="middle",
                            participation_rate=target_block_rate,
                        ),
                        # Attest to "target" by the rest of "target" and "prev_head" committees
                        Attesting(
                            committee_slot_or_offset=[target_slot, target_slot + 1],
                            block_id="target",
                            participation_rate=target_block_rate,
                        ),
                        # Next slot
                        AdvanceSlot(with_fast_confirmation=False),
                    ]
                )
            else:
                runs.extend(
                    [
                        # Next slot
                        AdvanceSlot(),
                        # Sequence of empty slots to prevent early confirmation of "target"
                        SlotSequence(
                            number_of_slots=3,
                            proposal=Proposal(enabled=False),
                            attesting=Attesting(participation_rate=0),
                        ),
                        # Attest to "target" by the committees of
                        # "head", "middle", "prev_head", "target" and all previous empty slots
                        Attesting(
                            block_id="target",
                            committee_slot_or_offset=[-1, -2, -3, -4, -5, -6],
                            participation_rate=target_block_rate,
                        ),
                        # Attest to head to make "prev_head" != "head"
                        Attesting(block_id="head", participation_rate=50),
                        # Next slot
                        AdvanceSlot(with_fast_confirmation=False),
                    ]
                )
        else:
            # prev_epoch     | curr_epoch
            #                |
            #    f_H --------|- p_H
            #    /           |
            # B_c --- T - M -|----- H
            #                |
            proposals = {
                "fake_head": Proposal(parent_id="confirmed"),
                "target": Proposal(parent_id="confirmed"),
                "middle": Proposal(parent_id="target"),
                "prev_head": Proposal(parent_id="fake_head"),
                "head": Proposal(parent_id="middle"),
            }

            for k, p in proposals.items():
                p.graffiti = k
                p.include_att_fn = include_att_fn
                p.release_att_pool = False

            if test_spec.no_conflicting_chkp:
                curr_epoch_attest_to = "middle"
            else:
                curr_epoch_attest_to = "target"

            runs.extend(
                [
                    SlotRun(
                        proposal=proposals["fake_head"], attesting=Attesting(participation_rate=75)
                    ),
                    Attesting(
                        committee_slot_or_offset=-1, block_id="confirmed", participation_rate=100
                    ),
                    SlotRun(
                        proposal=proposals["target"], attesting=Attesting(participation_rate=100)
                    ),
                    # "prev_head" must outweigh "target" and reconfirmation must pass, thus attest to "confirmed"
                    SlotRun(
                        proposal=proposals["middle"],
                        attesting=Attesting(block_id="confirmed", participation_rate=25),
                    ),
                    # "prev_head" must outweigh "target"
                    # 100% is needed as "prev_head" committee may overlap with "fake_head" committee
                    SlotRun(
                        proposal=proposals["prev_head"], attesting=Attesting(participation_rate=100)
                    ),
                    SlotRun(proposal=proposals["head"], attesting=Attesting(participation_rate=0)),
                    # Sequence of empty slots to aid confirming "target"
                    EmptySlotRun(attesting=Attesting(participation_rate=0)),
                    EmptySlotRun(attesting=Attesting(participation_rate=0)),
                    EmptySlotRun(attesting=Attesting(participation_rate=0)),
                    EmptySlotRun(attesting=Attesting(participation_rate=0)),
                    EmptySlotRun(
                        attesting=Attesting(participation_rate=0),
                        advance_slot=AdvanceSlot(next_slot=False),
                    ),
                    # Attest to "curr_epoch_attest_to" by past slots committees and constant participation
                    Attesting(
                        block_id=curr_epoch_attest_to,
                        participation_rate=100,
                        committee_slot_or_offset=[0, -1, -2, -3],
                    ),
                    # Attest to "target" by a couple of committees
                    # we need to one confirm "target" sharply, one confirming "middle" will imply block_vs_fresh
                    Attesting(
                        committee_slot_or_offset=[-4, -5],
                        block_id="target",
                        participation_rate=target_block_rate,
                    ),
                    # Attest to "target" by the rest of "target" and "middle" committees
                    Attesting(
                        committee_slot_or_offset=[target_slot, target_slot + 1],
                        block_id="target",
                        participation_rate=target_block_rate,
                    ),
                    # Next slot
                    AdvanceSlot(with_fast_confirmation=False),
                ]
            )

        return runs

    def create_system_runs(self):
        test_spec = self.test_spec

        if test_spec.first_slot_call:
            assert test_spec.no_conflicting_chkp, "Impossible in the first slot of an epoch"
        if test_spec.prev_head_uj_fresh:
            assert test_spec.prev_head_vs_fresh, (
                "Impossible as prev_head_uj_fresh implies prev_head_vs_fresh"
            )
        if test_spec.prev_head_ancestor and test_spec.block_vs_fresh:
            assert test_spec.prev_head_vs_fresh, (
                "Impossible as block_vs_fresh implies prev_head_vs_fresh if block is ancestor of prev_head"
            )
        if not test_spec.first_slot_call:
            assert test_spec.prev_head_vs_fresh, (
                "VS(prev_head) must always be fresh in the middle of an epoch, otherwise, prev_head would be filtered out in the previous slot"
            )

        if test_spec.vs_and_uj_are_fresh():
            if test_spec.first_slot_call:
                return self.create_first_slot_call_runs()
            else:
                return self.create_mid_epoch_call_runs()
        elif test_spec.first_slot_call:
            return self.create_stale_vs_and_uj_first_slot_runs()
        else:
            return self.create_stale_vs_and_uj_mid_epoch_runs()

    def build(self):
        fcr_test = FCRTest(self.spec, self.seed)
        fcr_test.initialize(self.state)

        debug_print("\n")

        for run in self.create_system_runs():
            run.execute(fcr_test)

            debug_print(f"slot {fcr_test.current_slot()}: {run}")
            fcr_test.print_fast_confirmation_state()
            debug_print("\n")

        # Check preconditions are correct
        self.test_spec.verify_preconditions(fcr_test.spec, fcr_test.fcr_store)

        return fcr_test


def run_previous_epoch_test(fcr_test: FCRTest, test_spec: PreviousEpochTestSpecification):
    # Keep expected confirmed_root after execution of the test
    expected_confirmed_root = test_spec.get_expected_confirmed_root(
        fcr_test.spec, fcr_test.fcr_store
    )
    # Execute FCR and check that confirmed_root is as expected
    fcr_test.run_fast_confirmation()
    assert fcr_test.fcr_store.confirmed_root == expected_confirmed_root

    yield from fcr_test.get_test_artefacts()


def build_and_run_previous_epoch_test(spec, state, seed, test_spec: PreviousEpochTestSpecification):
    test_builder = PreviousEpochTestBuilder(spec, state, seed, test_spec)
    fcr_test = test_builder.build()
    yield from run_previous_epoch_test(fcr_test, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_000(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 0, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_001(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 1, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_002(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 2, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_003(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 3, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_004(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 4, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_005(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 5, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_006(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 6, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_007(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 7, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_008(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 8, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_009(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 9, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_010(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 10, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_011(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 11, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_012(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 12, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_013(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 13, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_014(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 14, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_015(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 15, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_016(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 16, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_017(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 17, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_018(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 18, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_019(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 19, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_020(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 20, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_021(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 21, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_022(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 22, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_023(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 23, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_024(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 24, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_025(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 25, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_026(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 26, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_027(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 27, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_028(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 28, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_029(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 29, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_030(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 30, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_031(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 31, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_032(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 32, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_033(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 33, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_034(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 34, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_035(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 35, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_036(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 36, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_037(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 37, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_038(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 38, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_039(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 39, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_040(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 40, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_041(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 41, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_042(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 42, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_043(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 43, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_044(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=False,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 44, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_045(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 45, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_046(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 46, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_047(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 47, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_048(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 48, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_049(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 49, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_050(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 50, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_051(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=True,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 51, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_052(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 52, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_053(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 53, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_054(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 54, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_055(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 55, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_056(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 56, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_057(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 57, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_058(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 58, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_059(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 59, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_060(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 60, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_061(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 61, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_062(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 62, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_063(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 63, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_064(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 64, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_065(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 65, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_066(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 66, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_067(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 67, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_068(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 68, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_069(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 69, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_070(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 70, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_071(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 71, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_072(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 72, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_073(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 73, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_074(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 74, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_075(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 75, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_076(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 76, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_077(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 77, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_078(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 78, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_079(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=True,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 79, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_080(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 80, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_081(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 81, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_082(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 82, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_083(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 83, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_084(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 84, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_085(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 85, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_086(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 86, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_087(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 87, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_088(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 88, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_089(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 89, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_090(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 90, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_091(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 91, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_092(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 92, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_093(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=True,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 93, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_094(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 94, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_095(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 95, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_096(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 96, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_097(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 97, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_098(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 98, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_099(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 99, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_100(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=True,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 100, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_101(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 101, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_102(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 102, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_103(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 103, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_104(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=False,
        block_vs_fresh=True,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 104, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_105(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 105, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_106(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=False,
        head_uj_fresh=True,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 106, test_spec)


@with_all_phases_from_to(ALTAIR, FULU)
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_fcr_previous_epoch_107(spec, state):
    test_spec = PreviousEpochTestSpecification(
        prev_head_ancestor=False,
        first_slot_call=False,
        is_one_confirmed=False,
        no_conflicting_chkp=False,
        prev_head_vs_fresh=True,
        prev_head_uj_fresh=True,
        block_vs_fresh=True,
        head_uj_fresh=False,
    )
    yield from build_and_run_previous_epoch_test(spec, state, 107, test_spec)
