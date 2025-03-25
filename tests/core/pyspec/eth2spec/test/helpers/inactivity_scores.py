from random import Random


def randomize_inactivity_scores(
    spec, state, minimum=0, maximum=50000, rng=Random(4242)
):
    state.inactivity_scores = [
        rng.randint(minimum, maximum) for _ in range(len(state.validators))
    ]


def zero_inactivity_scores(spec, state, rng=None):
    state.inactivity_scores = [0] * len(state.validators)
