from eth_consensus_specs.test.context import (
    ForkMeta,
    with_fork_metas,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import (
    AFTER_DENEB_PRE_POST_FORKS,
    MINIMAL,
)
from eth_consensus_specs.test.helpers.fork_transition import (
    do_fork,
    transition_to_next_epoch_and_append_blocks,
    transition_until_fork,
)
from eth_consensus_specs.test.helpers.keys import pubkeys


def mock_activated_validators(spec, state, mock_activations):
    validator_count = len(state.validators)
    for i in range(mock_activations):
        index = validator_count + i
        validator = spec.Validator(
            pubkey=pubkeys[index],
            withdrawal_credentials=spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
            + b"\x00" * 11
            + b"\x56" * 20,
            activation_eligibility_epoch=0,
            activation_epoch=spec.FAR_FUTURE_EPOCH,
            exit_epoch=spec.FAR_FUTURE_EPOCH,
            withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
            effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.validators.append(validator)
        state.balances.append(spec.MAX_EFFECTIVE_BALANCE)
        state.previous_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
        state.current_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
        state.inactivity_scores.append(0)
        state.validators[index].activation_epoch = spec.get_current_epoch(state)


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in AFTER_DENEB_PRE_POST_FORKS
    ]
)
@with_presets([MINIMAL], reason="churn limit update needs enough validators")
def test_higher_churn_limit_to_lower(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Test if churn limit goes from high to low due to EIP-7514.
    """
    # Create high churn limit
    mock_activations = (
        post_spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT * spec.config.CHURN_LIMIT_QUOTIENT
    )
    mock_activated_validators(spec, state, mock_activations)

    transition_until_fork(spec, state, fork_epoch)

    churn_limit_0 = spec.get_validator_churn_limit(state)
    assert churn_limit_0 > post_spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT

    # check pre state
    assert spec.get_current_epoch(state) < fork_epoch

    yield "pre", state

    # irregular state transition to handle fork
    blocks = []
    state, block = do_fork(state, spec, post_spec, fork_epoch)
    blocks.append(post_tag(block))

    # check post state
    assert spec.get_current_epoch(state) == fork_epoch

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    yield "blocks", blocks
    yield "post", state

    churn_limit_1 = post_spec.get_validator_activation_churn_limit(state)
    assert churn_limit_1 == post_spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT
    assert churn_limit_1 < churn_limit_0
