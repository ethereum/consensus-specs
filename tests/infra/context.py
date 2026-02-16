from collections.abc import Callable, Sequence
from typing import Any

from lru import LRU

from eth2spec.test.helpers.genesis import create_genesis_state
from eth2spec.test.helpers.typing import Spec, SpecForks


def _prepare_state(
    balances_fn: Callable[[Any], Sequence[int]],
    threshold_fn: Callable[[Any], int],
    spec: Spec,
    phases: SpecForks,
):
    balances = balances_fn(spec)
    activation_threshold = threshold_fn(spec)
    state = create_genesis_state(
        spec=spec, validator_balances=balances, activation_threshold=activation_threshold
    )
    return state


_custom_state_cache_dict = LRU(size=10)


def with_custom_state(
    balances_fn: Callable[[Any], Sequence[int]], threshold_fn: Callable[[Any], int]
):
    def deco(fn):
        def entry(*args, spec: Spec, phases: SpecForks, **kw):
            # make a key for the state, unique to the fork + config (incl preset choice) and balances/activations
            key = (spec.fork, spec.config.__hash__(), spec.__file__, balances_fn, threshold_fn)
            if key not in _custom_state_cache_dict:
                state = _prepare_state(balances_fn, threshold_fn, spec, phases)
                _custom_state_cache_dict[key] = state.get_backing()

            # Take an entry out of the LRU.
            # No copy is necessary, as we wrap the immutable backing with a new view.
            state = spec.BeaconState(backing=_custom_state_cache_dict[key])
            kw["state"] = state
            return fn(*args, spec=spec, phases=phases, **kw)

        return entry

    return deco
