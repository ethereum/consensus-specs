from eth_consensus_specs.test.helpers.state import next_epoch_with_full_participation


def state_preprocessor(fn):
    """
    `fn` accepts `spec` (instance of consensus specification) and `state` (instance of the BeaconState)
    and returns a modified BeaconState;
    If defined `fn` should be applied to the BeaconState before any model solution is materialized.
    """
    return fn


@state_preprocessor
def common_state_preprocessor(spec, state) -> object:
	mod_state = state.copy()
	# Advance for 2 epochs
	for _ in range(2):
		next_epoch_with_full_participation(spec, mod_state)
	return mod_state
