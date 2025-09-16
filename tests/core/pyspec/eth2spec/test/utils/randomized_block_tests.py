"""
Utility code to generate randomized block tests
"""

import sys
import warnings
from collections.abc import Callable
from random import Random

from eth2spec.test.helpers.blob import get_sample_blob_tx
from eth2spec.test.helpers.execution_payload import (
    build_randomized_execution_payload,
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_bellatrix,
    is_post_capella,
    is_post_deneb,
)
from eth2spec.test.helpers.inactivity_scores import randomize_inactivity_scores
from eth2spec.test.helpers.multi_operations import (
    build_random_block_from_state_for_next_slot,
    get_random_bls_to_execution_changes,
    get_random_execution_requests,
    get_random_sync_aggregate,
    prepare_state_and_get_random_deposits,
)
from eth2spec.test.helpers.random import (
    patch_state_to_non_leaking,
    randomize_state as randomize_state_helper,
)
from eth2spec.test.helpers.state import (
    ensure_state_has_validators_across_lifecycle,
    next_epoch,
    next_slot,
    state_transition_and_sign_block,
)
from eth2spec.utils import bls

# primitives:
# state


def _randomize_deposit_state(spec, state, stats):
    """
    To introduce valid, randomized deposits, the ``state`` deposit sub-state
    must be coordinated with the data that will ultimately go into blocks.

    This function randomizes the ``state`` in a way that can signal downstream to
    the block constructors how they should (or should not) make some randomized deposits.
    """
    rng = Random(999)
    block_count = stats.get("block_count", 0)
    deposits = []
    if block_count > 0:
        num_deposits = rng.randrange(1, block_count * spec.MAX_DEPOSITS)
        deposits = prepare_state_and_get_random_deposits(
            spec, state, rng, num_deposits=num_deposits
        )
    return {
        "deposits": deposits,
    }


def _randomize_phase0_fields(spec, state):
    """Set Phase0-specific fields to realistic non-default values."""

    rng = Random(8020)  # same seed as other randomization functions
    current_epoch = spec.get_current_epoch(state)

    # Randomize ETH1 data votes (simulate realistic ETH1 voting)
    if len(state.eth1_data_votes) == 0:
        num_votes = rng.randint(1, min(10, spec.EPOCHS_PER_ETH1_VOTING_PERIOD))
        for i in range(num_votes):
            eth1_data = spec.Eth1Data(
                deposit_root=rng.randbytes(32),
                deposit_count=rng.randint(1, 1000),
                block_hash=rng.randbytes(32),
            )
            state.eth1_data_votes.append(eth1_data)

    # Randomize historical roots
    if current_epoch > 0 and len(state.historical_roots) == 0:
        num_historical = rng.randint(0, min(3, current_epoch))
        for i in range(num_historical):
            state.historical_roots.append(rng.randbytes(32))

    # Randomize RANDAO mixes
    for i in range(min(len(state.randao_mixes), spec.EPOCHS_PER_HISTORICAL_VECTOR)):
        if state.randao_mixes[i] == b"\x00" * 32:  # Only modify empty ones
            state.randao_mixes[i] = rng.randbytes(32)

    # Add some slashing penalties
    current_epoch_index = current_epoch % spec.EPOCHS_PER_SLASHINGS_VECTOR
    if state.slashings[current_epoch_index] == 0:
        penalty = spec.EFFECTIVE_BALANCE_INCREMENT * rng.randint(0, 10)
        state.slashings[current_epoch_index] = penalty


def _randomize_altair_fields(spec, state):
    """Set Altair-specific fields to realistic non-default values."""
    if not is_post_altair(spec):
        return

    rng = Random(4242)  # consistent seed with inactivity scores

    # Simulate sync committee rotation to catch transition bugs
    if hasattr(state, "current_sync_committee") and hasattr(state, "next_sync_committee"):
        current_epoch = spec.get_current_epoch(state)
        active_validators = spec.get_active_validator_indices(state, current_epoch)

        if len(active_validators) >= spec.SYNC_COMMITTEE_SIZE:
            shuffled_validators = list(active_validators)
            rng.shuffle(shuffled_validators)
            next_committee_indices = shuffled_validators[: spec.SYNC_COMMITTEE_SIZE]
            next_pubkeys = [state.validators[i].pubkey for i in next_committee_indices]
            state.next_sync_committee.pubkeys = next_pubkeys

            if next_pubkeys:
                state.next_sync_committee.aggregate_pubkey = bls.AggregatePKs(next_pubkeys)


def _randomize_bellatrix_fields(spec, state):
    """Set Bellatrix-specific fields to realistic non-default values."""
    if not is_post_bellatrix(spec):
        return

    rng = Random(3456)  # consistent seed with block randomization

    if hasattr(state, "latest_execution_payload_header"):
        empty_header = spec.ExecutionPayloadHeader()
        if state.latest_execution_payload_header == empty_header:
            state.latest_execution_payload_header = spec.ExecutionPayloadHeader(
                parent_hash=rng.randbytes(32),
                fee_recipient=rng.randbytes(20),
                state_root=rng.randbytes(32),
                receipts_root=rng.randbytes(32),
                logs_bloom=rng.randbytes(spec.BYTES_PER_LOGS_BLOOM),
                prev_randao=rng.randbytes(32),
                block_number=rng.randint(1, 1000000),
                gas_limit=rng.randint(8000000, 30000000),
                gas_used=rng.randint(100000, 15000000),
                timestamp=rng.randint(1609459200, 2000000000),
                extra_data=rng.randbytes(rng.randint(0, 32)),
                base_fee_per_gas=rng.randint(1, 100000000000),
                block_hash=rng.randbytes(32),
                transactions_root=rng.randbytes(32),
            )


def _randomize_capella_fields(spec, state):
    """Set Capella-specific fields to realistic non-default values."""
    if not is_post_capella(spec):
        return

    rng = Random(7890)

    # Randomize withdrawal credentials to simulate realistic validator states
    if hasattr(state, "validators"):
        num_validators = len(state.validators)

        # Set some validators to have ETH1 withdrawal credentials (0x01 prefix)
        # to simulate realistic pre-Capella state where some validators haven't
        # updated their credentials yet
        for i in range(min(num_validators, 20)):
            validator = state.validators[i]

            # ~30% chance to set ETH1 withdrawal credentials
            if rng.random() < 0.3:
                eth1_address = rng.randbytes(20)
                validator.withdrawal_credentials = b"\x01" + b"\x00" * 11 + eth1_address


def _randomize_deneb_fields(spec, state):
    """Set Deneb-specific fields to realistic non-default values."""
    if not is_post_deneb(spec):
        return

    rng = Random(9999)

    if hasattr(state, "historical_summaries") and len(state.historical_summaries) == 0:
        current_epoch = spec.get_current_epoch(state)
        num_summaries = rng.randint(0, min(3, current_epoch // 100))

        for i in range(num_summaries):
            historical_summary = spec.HistoricalSummary(
                block_summary_root=rng.randbytes(32),
                state_summary_root=rng.randbytes(32),
            )
            state.historical_summaries.append(historical_summary)


def randomize_state_phase0(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )

    _randomize_phase0_fields(spec, state)
    return scenario_state


def randomize_state(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    randomize_state_helper(spec, state, exit_fraction=exit_fraction, slash_fraction=slash_fraction)
    scenario_state = _randomize_deposit_state(spec, state, stats)
    return scenario_state


def randomize_state_altair(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_phase0(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    randomize_inactivity_scores(spec, state)
    _randomize_altair_fields(spec, state)
    return scenario_state


def randomize_state_bellatrix(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_altair(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    _randomize_bellatrix_fields(spec, state)
    return scenario_state


def randomize_state_capella(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_bellatrix(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    _randomize_capella_fields(spec, state)
    return scenario_state


def randomize_state_deneb(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_capella(
        spec, state, stats, exit_fraction=exit_fraction, slash_fraction=slash_fraction
    )
    _randomize_deneb_fields(spec, state)
    return scenario_state


def randomize_state_electra(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_deneb(
        spec,
        state,
        stats,
        exit_fraction=exit_fraction,
        slash_fraction=slash_fraction,
    )
    return scenario_state


def randomize_state_fulu(spec, state, stats, exit_fraction=0.1, slash_fraction=0.1):
    scenario_state = randomize_state_electra(
        spec,
        state,
        stats,
        exit_fraction=exit_fraction,
        slash_fraction=slash_fraction,
    )
    return scenario_state


# epochs


def epochs_until_leak(spec):
    """
    State is "leaking" if the current epoch is at least
    this value after the last finalized epoch.
    """
    return spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY + 1


def epochs_for_shard_committee_period(spec):
    return spec.config.SHARD_COMMITTEE_PERIOD


# slots


def last_slot_in_epoch(spec):
    return spec.SLOTS_PER_EPOCH - 1


def random_slot_in_epoch(spec, rng=None):
    if rng is None:
        rng = Random(1336)
    return rng.randrange(1, spec.SLOTS_PER_EPOCH - 2)


def penultimate_slot_in_epoch(spec):
    return spec.SLOTS_PER_EPOCH - 2


# blocks


def no_block(_spec, _pre_state, _signed_blocks, _scenario_state):
    return None


# May need to make several attempts to find a block that does not correspond to a slashed
# proposer with the randomization helpers...
BLOCK_ATTEMPTS = 32


def _warn_if_empty_operations(block):
    """
    NOTE: a block may be missing deposits depending on how many were created
    and already inserted into existing blocks in a given scenario.
    """
    if len(block.body.proposer_slashings) == 0:
        warnings.warn(f"proposer slashings missing in block at slot {block.slot}")

    if len(block.body.attester_slashings) == 0:
        warnings.warn(f"attester slashings missing in block at slot {block.slot}")

    if len(block.body.attestations) == 0:
        warnings.warn(f"attestations missing in block at slot {block.slot}")

    if len(block.body.voluntary_exits) == 0:
        warnings.warn(f"voluntary exits missing in block at slot {block.slot}")


def _pull_deposits_from_scenario_state(spec, scenario_state, existing_block_count):
    all_deposits = scenario_state.get("deposits", [])
    start = existing_block_count * spec.MAX_DEPOSITS
    return all_deposits[start : start + spec.MAX_DEPOSITS]


def random_block(spec, state, signed_blocks, scenario_state):
    """
    Produce a random block.
    NOTE: this helper may mutate state, as it will attempt
    to produce a block over ``BLOCK_ATTEMPTS`` slots in order
    to find a valid block in the event that the proposer has already been slashed.
    """
    # NOTE: ``state`` has been "randomized" at this point and so will likely
    # contain a large number of slashed validators. This function needs to return
    # a valid block so it needs to check that the proposer of the next slot is not
    # slashed.
    # To do this, generate a ``temp_state`` to use for checking the propser in the next slot.
    # This ensures no accidental mutations happen to the ``state`` the caller expects to get back
    # after this function returns.
    # Using a copy of the state for proposer sampling is also sound as any inputs used for the
    # shuffling are fixed a few epochs prior to ``spec.get_current_epoch(state)``.
    temp_state = state.copy()
    next_slot(spec, temp_state)
    for _ in range(BLOCK_ATTEMPTS):
        proposer_index = spec.get_beacon_proposer_index(temp_state)
        proposer = state.validators[proposer_index]
        if proposer.slashed:
            next_slot(spec, state)
            next_slot(spec, temp_state)
        else:
            deposits_for_block = _pull_deposits_from_scenario_state(
                spec, scenario_state, len(signed_blocks)
            )
            block = build_random_block_from_state_for_next_slot(
                spec, state, deposits=deposits_for_block
            )
            _warn_if_empty_operations(block)
            return block
    raise AssertionError("could not find a block with an unslashed proposer, check ``state`` input")


SYNC_AGGREGATE_PARTICIPATION_BUCKETS = 4


def random_block_altair_with_cycling_sync_committee_participation(
    spec, state, signed_blocks, scenario_state
):
    block = random_block(spec, state, signed_blocks, scenario_state)
    block_index = len(signed_blocks) % SYNC_AGGREGATE_PARTICIPATION_BUCKETS
    fraction_missed = block_index * (1 / SYNC_AGGREGATE_PARTICIPATION_BUCKETS)
    fraction_participated = 1.0 - fraction_missed
    previous_root = block.parent_root
    block.body.sync_aggregate = get_random_sync_aggregate(
        spec,
        state,
        block.slot - 1,
        block_root=previous_root,
        fraction_participated=fraction_participated,
    )
    return block


def random_block_bellatrix(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_altair_with_cycling_sync_committee_participation(
        spec, state, signed_blocks, scenario_state
    )
    # build execution_payload at the next slot
    state = state.copy()
    next_slot(spec, state)
    block.body.execution_payload = build_randomized_execution_payload(spec, state, rng=rng)
    return block


def random_block_capella(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_bellatrix(spec, state, signed_blocks, scenario_state, rng=rng)
    block.body.bls_to_execution_changes = get_random_bls_to_execution_changes(
        spec, state, num_address_changes=rng.randint(1, spec.MAX_BLS_TO_EXECUTION_CHANGES)
    )
    return block


def random_block_deneb(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_capella(spec, state, signed_blocks, scenario_state, rng=rng)
    # TODO: more commitments. blob_kzg_commitments: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]
    # TODO: add MAX_BLOBS_PER_BLOCK_FULU at fulu
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(
        spec, blob_count=rng.randint(0, spec.config.MAX_BLOBS_PER_BLOCK), rng=rng
    )
    block.body.execution_payload.transactions.append(opaque_tx)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    block.body.blob_kzg_commitments = blob_kzg_commitments

    return block


def random_block_electra(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_deneb(spec, state, signed_blocks, scenario_state, rng=rng)
    block.body.execution_requests = get_random_execution_requests(spec, state, rng=rng)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)

    return block


def random_block_fulu(spec, state, signed_blocks, scenario_state, rng=None):
    if rng is None:
        rng = Random(3456)
    block = random_block_electra(spec, state, signed_blocks, scenario_state, rng=rng)

    return block


# validations


def no_op_validation(_spec, _state):
    return True


def validate_is_leaking(spec, state):
    return spec.is_in_inactivity_leak(state)


def validate_is_not_leaking(spec, state):
    return not validate_is_leaking(spec, state)


# transitions


def with_validation(transition, validation):
    if isinstance(transition, Callable):
        transition = transition()
    transition["validation"] = validation
    return transition


def no_op_transition():
    return {}


def epoch_transition(n=0):
    return {
        "epochs_to_skip": n,
    }


def slot_transition(n=0):
    return {
        "slots_to_skip": n,
    }


def transition_to_leaking():
    return {
        "epochs_to_skip": epochs_until_leak,
        "validation": validate_is_leaking,
    }


transition_without_leak = with_validation(no_op_transition, validate_is_not_leaking)

# block transitions


def transition_with_random_block(block_randomizer):
    """
    Build a block transition with randomized data.
    Provide optional sub-transitions to advance some
    number of epochs or slots before applying the random block.
    """
    return {
        "block_producer": block_randomizer,
    }


# setup and test gen


def _randomized_scenario_setup(state_randomizer):
    """
    Return a sequence of pairs of ("mutation", "validation").
    A "mutation" is a function that accepts (``spec``, ``state``, ``stats``) arguments and
    allegedly performs some change to the state.
    A "validation" is a function that accepts (spec, state) arguments and validates some change was made.

    The "mutation" may return some state that should be available to any down-stream transitions
    across the **entire** scenario.

    The ``stats`` parameter reflects a summary of actions in a given scenario like
    how many blocks will be produced. This data can be useful to construct a valid
    pre-state and so is provided at the setup stage.
    """

    def _skip_epochs(epoch_producer):
        def f(spec, state, _stats):
            """
            The unoptimized spec implementation is too slow to advance via ``next_epoch``.
            Instead, just overwrite the ``state.slot`` and continue...
            """
            epochs_to_skip = epoch_producer(spec)
            slots_to_skip = epochs_to_skip * spec.SLOTS_PER_EPOCH
            state.slot += slots_to_skip

        return f

    def _simulate_honest_execution(spec, state, _stats):
        """
        Want to start tests not in a leak state; the finality data
        may not reflect this condition with prior (arbitrary) mutations,
        so this mutator addresses that fact.
        """
        patch_state_to_non_leaking(spec, state)

    return (
        # NOTE: the block randomization function assumes at least 1 shard committee period
        # so advance the state before doing anything else.
        (_skip_epochs(epochs_for_shard_committee_period), no_op_validation),
        (_simulate_honest_execution, no_op_validation),
        (state_randomizer, ensure_state_has_validators_across_lifecycle),
    )


# Run the generated tests:


# while the test implementation works via code-gen,
# references to helper code in this module are serialized as str names.
# to resolve this references at runtime, we need a reference to this module:
_this_module = sys.modules[__name__]


def _resolve_ref(ref):
    if isinstance(ref, str):
        return getattr(_this_module, ref)
    return ref


def _iter_temporal(spec, description):
    """
    Intended to advance some number of {epochs, slots}.
    Caller can provide a constant integer or a callable deriving a number from
    the ``spec`` under consideration.
    """
    numeric = _resolve_ref(description)
    if isinstance(numeric, Callable):
        numeric = numeric(spec)
    yield from range(numeric)


def _compute_statistics(scenario):
    block_count = 0
    for transition in scenario["transitions"]:
        block_producer = _resolve_ref(transition.get("block_producer", None))
        if block_producer and block_producer != no_block:
            block_count += 1
    return {
        "block_count": block_count,
    }


def run_generated_randomized_test(spec, state, scenario):
    stats = _compute_statistics(scenario)
    if "setup" not in scenario:
        state_randomizer = _resolve_ref(scenario.get("state_randomizer", randomize_state))
        scenario["setup"] = _randomized_scenario_setup(state_randomizer)

    scenario_state = {}
    for mutation, validation in scenario["setup"]:
        additional_state = mutation(spec, state, stats)
        validation(spec, state)
        if additional_state:
            scenario_state.update(additional_state)

    yield "pre", state

    blocks = []
    for transition in scenario["transitions"]:
        epochs_to_skip = _iter_temporal(spec, transition["epochs_to_skip"])
        for _ in epochs_to_skip:
            next_epoch(spec, state)
        slots_to_skip = _iter_temporal(spec, transition["slots_to_skip"])
        for _ in slots_to_skip:
            next_slot(spec, state)

        block_producer = _resolve_ref(transition["block_producer"])
        block = block_producer(spec, state, blocks, scenario_state)
        if block:
            signed_block = state_transition_and_sign_block(spec, state, block)
            blocks.append(signed_block)

        validation = _resolve_ref(transition["validation"])
        assert validation(spec, state)

    yield "blocks", blocks
    yield "post", state
