from eth_consensus_specs.test.context import expect_assertion_error, spec_state_test, with_phases
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.keys import get_vrf_proof


def run_randao_processing(spec, state, body, valid=True):
    yield "pre", state
    yield "body", body

    if not valid:
        expect_assertion_error(lambda: spec.process_randao(state, body))
        yield "post", None
        return

    spec.process_randao(state, body)
    yield "post", state


@with_phases([PQ])
@spec_state_test
def test_randao_reveal_hashes_vrf_leaf_into_mix(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    spec.process_slots(state, block.slot)
    epoch = spec.get_current_epoch(state)
    pre_mix = spec.get_randao_mix(state, epoch)

    yield from run_randao_processing(spec, state, block.body)

    leaf = block.body.randao_reveal[0]
    assert spec.get_randao_mix(state, epoch) == spec.sha256(pre_mix + leaf + spec.DOMAIN_RANDAO)


@with_phases([PQ])
@spec_state_test
def test_invalid_randao_reveal_of_other_validator(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    spec.process_slots(state, block.slot)
    proposer_index = spec.get_beacon_proposer_index(state)
    other_index = (proposer_index + 1) % len(state.validators)
    block.body.randao_reveal = spec.VRFProof(data=get_vrf_proof(other_index))

    yield from run_randao_processing(spec, state, block.body, valid=False)
