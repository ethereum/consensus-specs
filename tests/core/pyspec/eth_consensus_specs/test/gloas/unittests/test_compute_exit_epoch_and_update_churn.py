from eth_consensus_specs.test.context import spec_state_test, with_gloas_and_later


def _set_queue_epochs(spec, state, exit_offset, consolidation_offset):
    """Helper: set both queue epochs relative to the activation-exit epoch."""
    activation_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    state.earliest_exit_epoch = spec.Epoch(activation_exit_epoch + exit_offset)
    state.earliest_consolidation_epoch = spec.Epoch(activation_exit_epoch + consolidation_offset)
    return activation_exit_epoch


@with_gloas_and_later
@spec_state_test
def test_exit_uses_exit_queue_when_queues_equal(spec, state):
    """
    [EIP-8080] When exit and consolidation queues are the same length, exits
    continue to use the exit queue.
    """
    activation_exit_epoch = _set_queue_epochs(spec, state, exit_offset=3, consolidation_offset=3)
    pre_consolidation_balance = state.consolidation_balance_to_consume
    pre_consolidation_epoch = state.earliest_consolidation_epoch

    exit_balance = spec.Gwei(1 * 10**9)
    returned_epoch = spec.compute_exit_epoch_and_update_churn(state, exit_balance)

    assert returned_epoch == state.earliest_exit_epoch
    assert state.earliest_consolidation_epoch == pre_consolidation_epoch
    assert state.consolidation_balance_to_consume == pre_consolidation_balance
    assert state.earliest_exit_epoch >= spec.Epoch(activation_exit_epoch + 3)
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_exit_uses_exit_queue_when_consolidation_queue_longer(spec, state):
    """
    [EIP-8080] When the consolidation queue is longer than the exit queue,
    exits stay on the exit queue (no routing).
    """
    _set_queue_epochs(spec, state, exit_offset=0, consolidation_offset=10)
    pre_consolidation_balance = state.consolidation_balance_to_consume
    pre_consolidation_epoch = state.earliest_consolidation_epoch

    exit_balance = spec.Gwei(1 * 10**9)
    returned_epoch = spec.compute_exit_epoch_and_update_churn(state, exit_balance)

    assert returned_epoch == state.earliest_exit_epoch
    assert state.earliest_consolidation_epoch == pre_consolidation_epoch
    assert state.consolidation_balance_to_consume == pre_consolidation_balance
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_exit_routes_through_consolidation_when_exit_queue_longer(spec, state):
    """
    [EIP-8080] When the exit queue is longer than the consolidation queue,
    exits are routed through `compute_consolidation_epoch_and_update_churn`.
    """
    _set_queue_epochs(spec, state, exit_offset=5, consolidation_offset=0)
    # Park a large consolidation-churn reservoir so the converted exit fits in-epoch.
    state.consolidation_balance_to_consume = spec.Gwei(10**18)
    pre_exit_epoch = state.earliest_exit_epoch
    pre_exit_balance_to_consume = state.exit_balance_to_consume

    exit_balance = spec.Gwei(300 * 10**9)
    returned_epoch = spec.compute_exit_epoch_and_update_churn(state, exit_balance)

    assert returned_epoch == state.earliest_consolidation_epoch
    # Exit queue untouched.
    assert state.earliest_exit_epoch == pre_exit_epoch
    assert state.exit_balance_to_consume == pre_exit_balance_to_consume
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_exit_routed_through_consolidation_applies_two_thirds_factor(spec, state):
    """
    [EIP-8080] The `2/3` conversion factor is applied to `exit_balance` when
    routing through the consolidation queue.
    """
    _set_queue_epochs(spec, state, exit_offset=5, consolidation_offset=0)
    # Large reservoir so the converted amount fits in the current epoch.
    state.consolidation_balance_to_consume = spec.Gwei(10**18)
    pre_consolidation_balance = state.consolidation_balance_to_consume

    exit_balance = spec.Gwei(300 * 10**9)
    spec.compute_exit_epoch_and_update_churn(state, exit_balance)

    converted = spec.Gwei(2 * exit_balance // 3)
    assert pre_consolidation_balance - state.consolidation_balance_to_consume == converted
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_exit_routes_through_consolidation_when_longer_by_one_epoch(spec, state):
    """
    [EIP-8080] Edge case: a one-epoch difference between the exit and
    consolidation queues is still enough to trigger routing.
    """
    _set_queue_epochs(spec, state, exit_offset=1, consolidation_offset=0)
    state.consolidation_balance_to_consume = spec.Gwei(10**18)

    exit_balance = spec.Gwei(1 * 10**9)
    returned_epoch = spec.compute_exit_epoch_and_update_churn(state, exit_balance)

    assert returned_epoch == state.earliest_consolidation_epoch
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_exit_routing_preserves_exit_queue_state(spec, state):
    """
    [EIP-8080] When an exit is routed through the consolidation queue, the
    exit queue's state fields must not be mutated.
    """
    _set_queue_epochs(spec, state, exit_offset=5, consolidation_offset=0)
    state.consolidation_balance_to_consume = spec.Gwei(10**18)
    state.exit_balance_to_consume = spec.Gwei(123 * 10**9)

    pre_exit_epoch = state.earliest_exit_epoch
    pre_exit_balance_to_consume = state.exit_balance_to_consume

    spec.compute_exit_epoch_and_update_churn(state, spec.Gwei(50 * 10**9))

    assert state.earliest_exit_epoch == pre_exit_epoch
    assert state.exit_balance_to_consume == pre_exit_balance_to_consume
    yield "post", state
