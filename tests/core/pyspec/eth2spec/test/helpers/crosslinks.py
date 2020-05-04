from eth2spec.test.context import expect_assertion_error


def run_crosslinks_processing(spec, state, shard_transitions, attestations, valid=True):
    """
    Run ``process_attestation``, yielding:
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
        expect_assertion_error(lambda: spec.process_crosslinks(state, shard_transitions, attestations))
        yield 'post', None
        return

    # process crosslinks
    spec.process_crosslinks(state, shard_transitions, attestations)

    # yield post-state
    yield 'post', state
