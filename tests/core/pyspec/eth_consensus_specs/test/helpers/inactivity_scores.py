from random import Random


def randomize_inactivity_scores(spec, state, minimum=0, maximum=50000, rng=None):
    if rng is None:
        rng = Random(4242)
    state.inactivity_scores = spec.InactivityScores(
        data=[rng.randint(minimum, maximum) for _ in range(len(state.validators))]
    )


def zero_inactivity_scores(spec, state, rng=None):
    state.inactivity_scores = spec.InactivityScores(data=[0] * len(state.validators))
