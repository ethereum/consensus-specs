from eth_consensus_specs.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    get_store_from_state,
    run_validate_gossip,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.voluntary_exits import (
    sign_voluntary_exit,
)
from eth_consensus_specs.test.helpers.withdrawals import (
    prepare_pending_withdrawal,
)


def create_signed_voluntary_exit(spec, state, validator_index, epoch=None):
    if epoch is None:
        epoch = spec.get_current_epoch(state)
    voluntary_exit = spec.VoluntaryExit(epoch=epoch, validator_index=validator_index)
    return sign_voluntary_exit(spec, state, voluntary_exit, privkeys[validator_index])


@with_electra_and_later
@spec_state_test
def test_gossip_voluntary_exit__ignore_pending_partial_withdrawal(spec, state):
    """
    Test that a voluntary exit for a validator with a pending partial
    withdrawal is ignored (EIP-7251).
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH

    # Queue a partial withdrawal for the validator that is not yet withdrawable
    validator_index = 0
    current_epoch = spec.get_current_epoch(state)
    prepare_pending_withdrawal(
        spec,
        state,
        validator_index,
        withdrawable_epoch=spec.compute_activation_exit_epoch(current_epoch),
    )
    assert spec.get_pending_balance_to_withdraw(state, validator_index) > 0
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, state.slot)

    signed_exit = create_signed_voluntary_exit(spec, state, validator_index)
    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "ignore"
    assert reason == "validator has pending partial withdrawals"

    yield (
        "messages",
        "meta",
        [
            {
                "current_time_ms": int(current_time_ms),
                "message": get_filename(signed_exit),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )
