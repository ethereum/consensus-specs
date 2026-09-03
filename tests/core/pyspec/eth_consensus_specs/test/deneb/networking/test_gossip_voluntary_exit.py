from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_deneb_and_later,
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


def create_signed_voluntary_exit(spec, state, validator_index, epoch=None, fork_version=None):
    if epoch is None:
        epoch = spec.get_current_epoch(state)
    voluntary_exit = spec.VoluntaryExit(epoch=epoch, validator_index=validator_index)
    return sign_voluntary_exit(
        spec, state, voluntary_exit, privkeys[validator_index], fork_version=fork_version
    )


@with_deneb_and_later
@spec_state_test
def test_gossip_voluntary_exit__valid_capella_signature(spec, state):
    """
    Test that a voluntary exit signed under CAPELLA_FORK_VERSION passes gossip
    validation on Deneb.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    signed_exit = create_signed_voluntary_exit(spec, state, validator_index=0)
    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 0, "message": get_filename(signed_exit), "expected": "valid"}],
    )


@with_deneb_and_later
@spec_state_test
@always_bls
def test_gossip_voluntary_exit__reject_deneb_signature(spec, state):
    """
    Test that a voluntary exit signed under DENEB_FORK_VERSION (i.e. not pinned
    to CAPELLA_FORK_VERSION per EIP-7044) is rejected.
    """
    yield "topic", "meta", "voluntary_exit"

    seen = get_seen(spec)
    state.slot += spec.Uint64(spec.config.SHARD_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    yield "state", state

    store, signed_anchor = get_store_from_state(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    current_time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(current_time_ms)

    # Sign with DENEB fork version (the wrong domain under EIP-7044).
    signed_exit = create_signed_voluntary_exit(
        spec, state, validator_index=0, fork_version=spec.config.DENEB_FORK_VERSION
    )
    yield get_filename(signed_exit), signed_exit

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_voluntary_exit=signed_exit,
        current_time_ms=current_time_ms,
    )
    assert result == "reject"
    assert reason == "invalid voluntary exit signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_exit),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
