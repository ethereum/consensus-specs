"""Regression checks for the larger inactivity-update profile."""

from random import Random
from types import SimpleNamespace

from eth_consensus_specs.gloas import mainnet, minimal as spec
from eth_consensus_specs.test.helpers.block import sign_randao_reveal
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    BoundFormula,
    fix,
)
from tests.generators.compliance_runners.state_transition.evaluation.invariant_scan import (
    entry_condition_violations,
    state_invariant_violations,
)
from tests.generators.compliance_runners.state_transition.inactivity_updates_loop.materializer import (
    InactivityUpdatesLoopMaterializer,
)
from tests.generators.compliance_runners.state_transition.inactivity_updates_loop.target import (
    TARGET as LOOP_TARGET,
)
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .history import InactivityHistory
from .materializer import InactivityUpdatesMaterializer
from .target import TARGET


def _observed(materializer, target, **solution):
    materializer.rng = Random(0)
    bound = target.for_spec(spec)
    witnesses = BoundFormula(bound, fix(**solution)).generation_obligations()
    assert len(witnesses) == 1
    witness = dict(next(iter(witnesses)))
    _, parts = materializer.materialize_solution(SimpleNamespace(**witness))
    pre = spec.BeaconState.decode_bytes(parts[0][2])
    post = spec.BeaconState.decode_bytes(parts[1][2])
    assert not list(entry_condition_violations(spec, pre, "epoch_processing"))
    assert not list(state_invariant_violations(spec, pre))
    record = target.record(target.observation(Context(spec, pre, None, post, {})))
    if target is TARGET and record.get("has_slashed_validators") is True:
        index = spec.ValidatorIndex(0)
        validator = pre.validators[index]
        still_eligible = record["slashed_withdrawable_vs_previous"]
        assert validator.slashed
        assert validator.withdrawable_epoch == spec.get_current_epoch(pre) + int(still_eligible)
        assert not spec.is_active_validator(validator, spec.get_previous_epoch(pre))
        assert (index in spec.get_eligible_validator_indices(pre)) == still_eligible
        assert len(pre.historical_summaries) == pre.slot // spec.SLOTS_PER_HISTORICAL_ROOT
        assert not any(pre.slashings)
    return record


def test_generated_witnesses_keep_requested_eligibility_and_score_effect():
    materializer = InactivityUpdatesMaterializer(spec)
    eligible = _observed(
        materializer,
        TARGET,
        current_after_genesis=True,
        has_slashed_validators=True,
        slashed_withdrawable_vs_previous=False,
    )
    assert eligible["has_active_eligible"] is True
    assert eligible["has_ineligible_validators"] is True
    assert eligible["slashed_withdrawable_vs_previous"] is False

    waiting = _observed(
        materializer,
        TARGET,
        current_after_genesis=True,
        has_slashed_validators=True,
        slashed_withdrawable_vs_previous=True,
        has_ineligible_validators=False,
    )
    assert waiting["slashed_withdrawable_vs_previous"] is True
    assert waiting["has_ineligible_validators"] is False

    changed = _observed(
        materializer,
        TARGET,
        current_after_genesis=True,
        eligible_validators="MANY",
        has_zero_score_eligible=True,
        scores_changed=True,
    )
    assert changed["scores_changed"] is True
    assert changed["has_zero_score_eligible"] is True


def test_stable_participant_keeps_target_flag():
    observed = _observed(
        InactivityUpdatesLoopMaterializer(spec),
        LOOP_TARGET,
        score_delta="UNCHANGED",
        has_target_flag=True,
        is_slashed=False,
    )
    assert observed["score_delta"] == "UNCHANGED"
    assert observed["has_target_flag"] is True


def test_mainnet_aged_checkpoint_at_withdrawal_boundary():
    history = InactivityHistory(mainnet)
    genesis_execution_hash = history.genesis.latest_block_hash
    states = []
    for matured in (False, True):
        state = history.outer(
            after_genesis=True, leaking=True, slashed=True, matured=matured, ineligible=matured
        ).copy()
        run_epoch_processing_to(mainnet, state, "process_inactivity_updates")
        assert not list(entry_condition_violations(mainnet, state, "epoch_processing"))
        assert not list(state_invariant_violations(mainnet, state))
        assert len(state.historical_summaries) == state.slot // mainnet.SLOTS_PER_HISTORICAL_ROOT
        assert state.latest_block_hash == genesis_execution_hash
        assert not any(state.execution_payload_availability)
        assert state.validators[0].pubkey not in state.current_sync_committee.pubkeys
        assert state.validators[0].pubkey not in state.next_sync_committee.pubkeys
        states.append(state)

    before, at_cutoff = states
    head = before.latest_block_header
    head_epoch = mainnet.compute_epoch_at_slot(head.slot)
    assert head_epoch < mainnet.get_previous_epoch(before)
    expected_mix = mainnet.get_randao_mix(before, head_epoch)
    head_state = before.copy()
    head_state.slot = head.slot
    head_state.proposer_lookahead[head.slot % mainnet.SLOTS_PER_EPOCH] = head.proposer_index
    head_state.randao_mixes[head_epoch % mainnet.EPOCHS_PER_HISTORICAL_VECTOR] = (
        before.latest_execution_payload_bid.prev_randao
    )
    block = mainnet.BeaconBlock(slot=head.slot, proposer_index=head.proposer_index)
    with bls_enabled():
        sign_randao_reveal(mainnet, head_state, block, head.proposer_index)
        mainnet.process_randao(head_state, block.body)
    assert mainnet.get_randao_mix(head_state, head_epoch) == expected_mix

    cutoff = mainnet.get_current_epoch(at_cutoff)
    period = mainnet.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    assert mainnet.get_current_epoch(before) + 1 == cutoff
    assert cutoff % period == 0
    selection_state = before.copy()
    selection_state.slot = mainnet.compute_start_slot_at_epoch(cutoff - 2 * period) - 1
    assert before.current_sync_committee == mainnet.get_next_sync_committee(selection_state)
    selection_state.slot = mainnet.compute_start_slot_at_epoch(cutoff - period) - 1
    assert before.next_sync_committee == mainnet.get_next_sync_committee(selection_state)
    assert at_cutoff.current_sync_committee == before.next_sync_committee
    assert before.slashings[0] > 0
    assert not any(at_cutoff.slashings)
    assert list(at_cutoff.historical_summaries) == [
        *before.historical_summaries,
        mainnet.HistoricalSummary(
            block_summary_root=mainnet.hash_tree_root(before.block_roots),
            state_summary_root=mainnet.hash_tree_root(before.state_roots),
        ),
    ]


def test_coverage_loader_selects_each_provider_in_the_shared_suite(tmp_path):
    materialize_handler("inactivity_updates", "smoke", tmp_path, spec=spec, seed=124)
    for name in ("inactivity_updates", "inactivity_updates_loop"):
        provider = load_provider(name)
        bound = provider.TARGET.for_spec(spec)
        observations = load_observations([tmp_path], bound, "minimal")
        assert len(observations) == len(provider.build_profile("smoke", spec=spec))
        report = score(bound, [bound.record(obs) for obs in observations], bound.profiles["smoke"])
        assert report.covered == report.total
        assert not report.unexpected


def test_max_omits_unrealizable_score_and_branch_combinations():
    obligations = [dict(item) for item in TARGET.for_spec(spec).profiles["max"].run()]
    assert all(item.get("eligible_validators") not in {"ZERO", "ONE"} for item in obligations)
    assert all(
        not (
            item.get("scores_changed") is False
            and (item.get("has_zero_score_eligible") is False or item.get("leaking") is True)
        )
        for item in obligations
    )
    assert not LOOP_TARGET.for_spec(spec).feasible(
        {"is_active_in_previous": False, "has_target_flag": True}
    )
    assert all(
        not (
            item.get("has_ineligible_validators") is False
            and item.get("has_slashed_validators") is True
            and item.get("branch_mix") == "ALL_DECREMENT"
        )
        for item in obligations
    )
