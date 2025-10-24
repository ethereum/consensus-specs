from eth2spec.test.context import (
    default_activation_threshold,
    default_balances,
    zero_activation_threshold,
)
from eth2spec.test.helpers.constants import MINIMAL, PHASE0
from eth2spec.test.helpers.specs import spec_targets
from tests.infra.context import _custom_state_cache_dict, with_custom_state


class TestWithCustomState:
    """Test suite for with_custom_state decorator."""

    def setup_method(self):
        """Clear custom state cache before each test."""
        _custom_state_cache_dict.clear()

    def teardown_method(self):
        """Clear custom state cache after each test."""
        _custom_state_cache_dict.clear()

    def test_with_custom_state_injects_state_view(self):
        spec = spec_targets[MINIMAL][PHASE0]

        @with_custom_state(default_balances, default_activation_threshold)
        def case(*, spec, phases, state):
            return state

        state = case(spec=spec, phases={})
        assert isinstance(state, spec.BeaconState)

    def test_with_custom_state_caches_for_identical_key(self):
        spec = spec_targets[MINIMAL][PHASE0]

        @with_custom_state(default_balances, default_activation_threshold)
        def case(*, spec, phases, state):
            return state

        assert len(_custom_state_cache_dict) == 0
        s1 = case(spec=spec, phases={})
        assert len(_custom_state_cache_dict) == 1
        s2 = case(spec=spec, phases={})
        assert len(_custom_state_cache_dict) == 1
        assert s1.hash_tree_root() == s2.hash_tree_root()

    def test_with_custom_state_changes_cache_key_when_balances_fn_differs(self):
        spec = spec_targets[MINIMAL][PHASE0]

        @with_custom_state(default_balances, default_activation_threshold)
        def c1(*, spec, phases, state):
            return state

        def fewer_balances(s):
            return [s.MAX_EFFECTIVE_BALANCE] * (s.SLOTS_PER_EPOCH * 4)

        @with_custom_state(fewer_balances, default_activation_threshold)
        def c2(*, spec, phases, state):
            return state

        assert len(_custom_state_cache_dict) == 0
        _ = c1(spec=spec, phases={})
        assert len(_custom_state_cache_dict) == 1
        _ = c2(spec=spec, phases={})
        assert len(_custom_state_cache_dict) == 2

    def test_with_custom_state_changes_cache_key_when_threshold_fn_differs(self):
        spec = spec_targets[MINIMAL][PHASE0]

        @with_custom_state(default_balances, default_activation_threshold)
        def c1(*, spec, phases, state):
            return state

        @with_custom_state(default_balances, zero_activation_threshold)
        def c2(*, spec, phases, state):
            return state

        assert len(_custom_state_cache_dict) == 0
        _ = c1(spec=spec, phases={})
        assert len(_custom_state_cache_dict) == 1
        _ = c2(spec=spec, phases={})
        assert len(_custom_state_cache_dict) == 2
