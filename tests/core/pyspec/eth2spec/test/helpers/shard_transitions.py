from eth2spec.test.context import expect_assertion_error


def run_shard_transitions_processing(spec, state, shard_transitions, attestations, valid=True):
    """
    Run ``process_shard_transitions``, yielding:
      - pre-state ('pre')
      - shard_transitions ('shard_transitions')
      - attestations ('attestations')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state
    yield 'pre', state
    yield 'shard_transitions', shard_transitions
    yield 'attestations', attestations

    # If the attestation is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_shard_transitions(state, shard_transitions, attestations))
        yield 'post', None
        return

    # process crosslinks
    spec.process_shard_transitions(state, shard_transitions, attestations)

    # yield post-state
    yield 'post', state


def get_shard_transition_of_committee(spec, state, committee_index, shard_blocks=None):
    if shard_blocks is None:
        shard_blocks = []

    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    shard_transition = spec.get_shard_transition(state, shard, shard_blocks=shard_blocks)
    return shard_transition
