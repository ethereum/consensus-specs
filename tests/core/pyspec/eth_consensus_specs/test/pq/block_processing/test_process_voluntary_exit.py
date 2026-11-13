from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.keys import pubkey_to_privkey
from eth_consensus_specs.test.helpers.voluntary_exits import run_voluntary_exit_processing
from eth_consensus_specs.utils import xmss


def prepare_signed_exit_at_leaf(spec, state, leaf_index):
    """
    Sign a voluntary exit of the first active validator at ``leaf_index``, after
    moving ``state`` forward far enough for the validator to exit.
    """
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    voluntary_exit = spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index)
    domain = spec.compute_domain(
        spec.DOMAIN_VOLUNTARY_EXIT,
        spec.config.CAPELLA_FORK_VERSION,
        state.genesis_validators_root,
    )
    signing_root = spec.compute_signing_root(voluntary_exit, domain)
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    return spec.SignedVoluntaryExit(
        message=voluntary_exit,
        signature=xmss.Sign(privkey, leaf_index, signing_root),
    )


@with_phases([PQ])
@spec_state_test
def test_voluntary_exit_signed_at_last_reserved_leaf(spec, state):
    signed_exit = prepare_signed_exit_at_leaf(spec, state, spec.XMSS_RESERVED_LEAVES - 1)

    yield from run_voluntary_exit_processing(spec, state, signed_exit)


@with_phases([PQ])
@spec_state_test
def test_invalid_voluntary_exit_signed_past_reserved_leaves(spec, state):
    signed_exit = prepare_signed_exit_at_leaf(spec, state, spec.XMSS_RESERVED_LEAVES)

    yield from run_voluntary_exit_processing(spec, state, signed_exit, valid=False)
