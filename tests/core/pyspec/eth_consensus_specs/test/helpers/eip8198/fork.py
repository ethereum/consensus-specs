from eth_consensus_specs.test.helpers.constants import (
    EIP8198,
)

EIP8198_FORK_TEST_META_TAGS = {
    "fork": EIP8198,
}


def run_fork_test(post_spec, pre_state):
    yield "pre", pre_state

    post_state = post_spec.upgrade_to_eip8198(pre_state)

    # EIP-8198 does not change the BeaconState container: every field except
    # ``fork`` must carry over unchanged.
    stable_fields = [name for name in pre_state.fields() if name != "fork"]
    for field in stable_fields:
        assert getattr(pre_state, field) == getattr(post_state, field)

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.config.EIP8198_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield "post", post_state

    return post_state
