"""Concrete witnesses for inactivity-score saturation and leak boundaries."""

from functools import cache
from itertools import product


@cache
def arithmetic_witnesses(threshold, bias, recovery, comparisons):
    """One witness per arithmetic signature.

    Each comparison and saturation branch is constant between its integer
    boundaries. Include the boundaries and their two nearest neighbours to
    represent every cmp5 bucket and score-change outcome in those intervals.
    """
    score_cmp, leak_cmp, recovery_cmp = comparisons
    selected = {}
    delays = {max(0, threshold + offset) for offset in (-2, -1, 0, 1, 2)} | {0}
    for participating in (False, True):
        centers = (0, 1, recovery + 1 if participating else recovery - bias)
        scores = {max(0, center + offset) for center in centers for offset in (-2, -1, 0, 1, 2)}
        for score, delay in product(sorted(scores), sorted(delays)):
            intermediate = max(0, score - 1) if participating else score + bias
            leaking = delay > threshold
            post_score = intermediate if leaking else max(0, intermediate - recovery)
            record = {
                "is_participating": participating,
                "score_gt_zero": score_cmp.abstract(score),
                "leaking": leak_cmp.abstract(delay - threshold),
                "score_delta": (
                    "DECREASED"
                    if post_score < score
                    else "INCREASED"
                    if post_score > score
                    else "UNCHANGED"
                ),
            }
            if not leaking:
                record["score_vs_recovery_rate"] = recovery_cmp.abstract(intermediate - recovery)
            selected.setdefault(tuple(sorted(record.items())), (score, delay))
    return selected
