from eth_consensus_specs.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import (
    EIP8148,
    HEZE,
)


@with_phases(phases=[HEZE], other_phases=[EIP8148])
@spec_test
@with_state
def test_fork_base_state(spec, phases, state):
    post_spec = phases[EIP8148]

    yield "pre", state
    post = post_spec.upgrade_to_eip8148(state)

    assert len(post.validator_sweep_thresholds) == len(post.validators)
    for validator, threshold in zip(post.validators, post.validator_sweep_thresholds, strict=True):
        if post_spec.has_compounding_withdrawal_credential(validator):
            assert threshold == post_spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        else:
            assert threshold == post_spec.Gwei(0)

    yield "post", post
