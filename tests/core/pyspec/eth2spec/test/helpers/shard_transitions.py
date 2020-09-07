from eth2spec.test.context import expect_assertion_error


def run_shard_transition_processing(spec, state, shard_transition, valid=True):
    """
    Run ``process_shard_transition``, yielding:
      - pre-state ('pre')
      - shard_transition ('shard_transition')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state
    yield 'pre', state
    yield 'shard_transition', shard_transition

    # If the shard transition is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_shard_transition(state, shard_transition))
        yield 'post', None
        return

    # process crosslinks
    spec.process_shard_transition(state, shard_transition)

    # yield post-state
    yield 'post', state


def get_shard_transition_of_committee(spec, state, committee_index, shard_blocks=None):
    if shard_blocks is None:
        shard_blocks = []

    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    shard_transition = spec.get_shard_transition(state, shard, shard_blocks=shard_blocks)
    return shard_transition


def is_full_crosslink(spec, state):
    epoch = spec.compute_epoch_at_slot(state.slot)
    return spec.get_committee_count_per_slot(state, epoch) >= spec.get_active_shard_count(state)
