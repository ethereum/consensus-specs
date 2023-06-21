
from eth2spec.test.context import (
    spec_state_test,
    with_presets,
    with_all_phases
)
from eth2spec.test.helpers.attestations import get_valid_attestation_at_slot, next_epoch_with_attestations, next_slots_with_attestations
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.fork_choice import (
    add_block,
    get_genesis_forkchoice_store_and_block,
)

from eth2spec.test.helpers.state import (
    next_epoch,
)

def on_tick_step(spec, store, time, test_steps):
    spec.on_tick(store, time)
    test_steps.append({'tick': int(time)})
    
def tick_to_next_slot(spec, store, test_steps):
        time = store.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        on_tick_step(spec, store, time, test_steps)    
    
def tick_and_add_block(spec, store, signed_block, test_steps, valid=True,
                       merge_block=False, block_not_found=False, is_optimistic=False):
    pre_state = store.block_states[signed_block.message.parent_root]
    if merge_block:
        assert spec.is_merge_transition_block(pre_state, signed_block.message.body)

    block_time = pre_state.genesis_time + signed_block.message.slot * spec.config.SECONDS_PER_SLOT
    while store.time < block_time:
        time = pre_state.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        on_tick_step(spec, store, time, test_steps)

    post_state = yield from add_block(
        spec, store, signed_block, test_steps,
        valid=valid,
        block_not_found=block_not_found,
        is_optimistic=is_optimistic,
    )

    return post_state
    
def apply_next_epoch_with_attestations(spec,
                                       state,
                                       store,
                                       fill_cur_epoch,
                                       fill_prev_epoch,
                                       participation_fn=None,
                                       test_steps=None):
    if test_steps is None:
        test_steps = []

    _, new_signed_blocks, post_state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn)
    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from tick_and_add_block(spec, store, signed_block, test_steps, is_optimistic=True)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block  

def apply_next_slots_with_attestations(spec,
                                       state,
                                       store,
                                       slots,
                                       fill_cur_epoch,
                                       fill_prev_epoch,
                                       test_steps,
                                       participation_fn=None):
    _, new_signed_blocks, post_state = next_slots_with_attestations(
        spec, state, slots, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn)
    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from tick_and_add_block(spec, store, signed_block, test_steps, is_optimistic=True)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block  


def get_ancestor(
    store,
    root,
    ancestor_number
):
    if ancestor_number == 0:
        return root
    else:
        return get_ancestor(store, store.blocks[root].parent_root, ancestor_number-1)
    
def get_block_root_from_head(
    spec,
    store,
    depth
):
    head_root = spec.get_head(store)
    return get_ancestor(store, head_root, depth)
        
def get_valid_attestation_for_block(
    spec,
    store,
    block_root,
    perc
):
    """
    Get attestation filled by `perc`%
    """
    return list(
        get_valid_attestation_at_slot(store.block_states[block_root], 
                                      spec, spec.get_slots_since_genesis(store), 
                                      lambda slot, index, comm: set(list(comm)[0:int(len(comm)*perc)]))
        )    

class ConfirmationRuleWrapper:
    def __init__(self, spec, confirmation_byzantine_threshold, confirmation_slashing_threshold):
        self.spec = spec
        self.confirmation_byzantine_threshold = confirmation_byzantine_threshold
        self.confirmation_slashing_threshold = confirmation_slashing_threshold
        
    def check_is_confirmed(
        self,
        store,
        block_root,
        test_steps,
        expected=None
    ):
        confirmed = self.spec.is_confirmed(store, self.confirmation_byzantine_threshold, self.confirmation_slashing_threshold, block_root)
        if expected != None:
            assert confirmed == expected
        test_steps.append({
            'check_is_confirmed': {
                'result': confirmed,
                'block_root': str(block_root)
            }
        }) 
        
    def is_lmd_confirmed(
        self,
        store,
        block_root,
    ):
        return self.spec.is_lmd_confirmed(store, self.confirmation_byzantine_threshold, block_root)         
    
    def is_ffg_confirmed(
        self,
        store,
        block_root,
    ):
        return self.spec.is_ffg_confirmed(store, self.confirmation_byzantine_threshold, self.confirmation_slashing_threshold, block_root)                   
                                        
    def check_get_confirmation_score(
        self,
        store,
        block_root,
        test_steps,
        expected=None
    ):
        confirmation_score = int(self.spec.get_confirmation_score(store, self.confirmation_slashing_threshold, block_root))
        if expected != None:
            assert confirmation_score == expected
        test_steps.append({
            'check_get_confirmation_score': {
                'result': confirmation_score,
                'block_root': str(block_root)
            }
        })     
        
    def get_confirmation_score(
        self,
        store,
        block_root
    ):
        return self.spec.get_confirmation_score(store, self.confirmation_slashing_threshold, block_root)
    
    def get_lmd_confirmation_score(
        self,
        store,
        block_root
    ):
        return self.spec.get_lmd_confirmation_score(store, self.confirmation_slashing_threshold, block_root)     
    
    def get_ffg_confirmation_score(
        self,
        store,
        block_root
    ):
        return self.spec.get_lmd_confirmation_score(store, self.confirmation_slashing_threshold, block_root)          
        
    
def confirmation_rule_setup(confirmation_byzantine_threshold: int, confirmation_slashing_threshold: int):        
    def decorator(func):
        def wrapped(*args, **kwargs):                         
            yield 'setup', {
                    'confirmation_byzantine_threshold': confirmation_byzantine_threshold,
                    'confirmation_slashing_threshold': confirmation_slashing_threshold
                }
            yield from func(
                    *args, 
                    conf_rule_wrapper=ConfirmationRuleWrapper(
                        spec=kwargs['spec'],
                        confirmation_slashing_threshold=confirmation_slashing_threshold,
                        confirmation_byzantine_threshold=confirmation_byzantine_threshold
                    ),
                    **kwargs
                )
        return wrapped
    return decorator

@with_all_phases
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=0, confirmation_slashing_threshold=0)
def test_confirm_current_epoch_no_byz(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    # Fill epoch 1 to 2
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
        
    state, store, _ = yield from apply_next_slots_with_attestations(spec, state, store, 2 , True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 1)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)
    
    conf_rule_wrapper.check_is_confirmed(store, root, test_steps, True)
    
    yield 'steps', test_steps

@with_all_phases
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=0, confirmation_slashing_threshold=0)
def test_confirm_previous_epoch_no_byz(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 1)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)
    
    conf_rule_wrapper.check_is_confirmed(store, root, test_steps, True)
    
    yield 'steps', test_steps

@with_all_phases
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=0, confirmation_slashing_threshold=0)
def test_no_confirm_current_epoch_due_to_justified_checkpoint(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    # Fill epoch 1 to 2
    for _ in range(1):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
        
    state, store, _ = yield from apply_next_slots_with_attestations(spec, state, store, 2 , True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 1)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)
    
    assert conf_rule_wrapper.is_lmd_confirmed(store, root)
    assert conf_rule_wrapper.is_ffg_confirmed(store, root)
    
    conf_rule_wrapper.check_is_confirmed(store, root, test_steps, False)
    conf_rule_wrapper.check_get_confirmation_score(store, root, test_steps, -1)
    
    yield 'steps', test_steps
    
@with_all_phases
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=0, confirmation_slashing_threshold=0)
def test_no_confirm_previous_epoch_due_to_justified_checkpoint(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 1)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)
    
    assert conf_rule_wrapper.is_lmd_confirmed(store, root)
    assert conf_rule_wrapper.is_ffg_confirmed(store, root)    
    conf_rule_wrapper.check_is_confirmed(store, root, test_steps, False)
    conf_rule_wrapper.check_get_confirmation_score(store, root, test_steps, -1)
    
    yield 'steps', test_steps
    
@with_all_phases
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=30, confirmation_slashing_threshold=0)
def test_no_confirm_current_epoch_but_ffg_confirmed(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
        
    state, store, _ = yield from apply_next_slots_with_attestations(spec, state, store, 2 , True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 1)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)
    
    assert conf_rule_wrapper.is_ffg_confirmed(store, root)  
    block_state = store.block_states[root]
    assert block_state.current_justified_checkpoint.epoch + 1 == spec.get_current_store_epoch(store)  
    conf_rule_wrapper.check_is_confirmed(store, root, test_steps, False)
    assert conf_rule_wrapper.get_confirmation_score(store, root) < 30
    conf_rule_wrapper.check_get_confirmation_score(store, root, test_steps)
    
    yield 'steps', test_steps
    
@with_all_phases
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=30, confirmation_slashing_threshold=0)
def test_no_confirm_previous_epoch_but_ffg_confirmed(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 1)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)
    
    assert conf_rule_wrapper.is_ffg_confirmed(store, root)  
    block_state = store.block_states[root]
    assert block_state.current_justified_checkpoint.epoch + 2 == spec.get_current_store_epoch(store)      
    conf_rule_wrapper.check_is_confirmed(store, root, test_steps, False)
    assert conf_rule_wrapper.get_confirmation_score(store, root) < 30
    conf_rule_wrapper.check_get_confirmation_score(store, root, test_steps)
    
    yield 'steps', test_steps
    
@with_all_phases
@with_presets([MINIMAL])
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=15, confirmation_slashing_threshold=2048000000000)
def test_no_confirm_current_epoch_but_lmd_confirmed(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
        
    state, store, _ = yield from apply_next_slots_with_attestations(spec, state, store, 3 , True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 2)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)
    
    assert conf_rule_wrapper.is_lmd_confirmed(store, root)  
    block_state = store.block_states[root]
    assert block_state.current_justified_checkpoint.epoch + 1 == spec.get_current_store_epoch(store)  

    conf_rule_wrapper.check_is_confirmed(store, root, test_steps, False)
    assert conf_rule_wrapper.get_confirmation_score(store, root) < 15
    conf_rule_wrapper.check_get_confirmation_score(store, root, test_steps)
    
    yield 'steps', test_steps
    
# @with_all_phases
# @with_presets([MINIMAL])
# @spec_state_test
# @confirmation_rule_setup(confirmation_byzantine_threshold=15, confirmation_slashing_threshold=2048000000000)
# def test_no_confirm_previous_epoch_but_lmd_confirmed(
#     spec, 
#     state, 
#     check_is_confirmed, 
#     check_get_confirmation_score,
#     is_lmd_confirmed,
#     is_ffg_confirmed
# ):
#     assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
#     test_steps = []
#     # Initialization
#     store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
#     yield 'anchor_state', state
#     yield 'anchor_block', anchor_block
#     current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
#     on_tick_step(spec, store, current_time, test_steps)
#     assert store.time == current_time

#     next_epoch(spec, state)
#     on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

#     # Fill epoch 1 to 3
#     for _ in range(3):
#         state, store, _ = yield from apply_next_epoch_with_attestations(
#             spec, state, store, True, True, test_steps=test_steps)
    
#     root = get_block_root_from_head(spec, store, 1)
#     block = store.block_states[root]
    
#     assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)
    
#     # assert is_lmd_confirmed(spec, store, root)  
#     block_state = store.block_states[root]
#     assert block_state.current_justified_checkpoint.epoch + 2 == spec.get_current_store_epoch(store)  
#     print(spec.get_confirmation_score(store, 2048000000000, root))    
#     print(spec.get_lmd_confirmation_score(store, root))    
#     print(spec.get_ffg_confirmation_score(store, 2048000000000, root))    
#     # check_is_confirmed(spec, store, root, test_steps, False)
    
#     yield 'steps', test_steps


@with_all_phases
@with_presets([MINIMAL])
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=0, confirmation_slashing_threshold=0)
def test_current_get_confirmation_score_no_slashing_threshold(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
        
    state, store, _ = yield from apply_next_slots_with_attestations(spec, state, store, 3 , True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 2)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)
     
    conf_rule_wrapper.check_get_confirmation_score(store, root, test_steps, 23)
    
    yield 'steps', test_steps
    
@with_all_phases
@with_presets([MINIMAL])
@spec_state_test
@confirmation_rule_setup(confirmation_byzantine_threshold=0, confirmation_slashing_threshold=2048000000000)
def test_current_get_confirmation_score_slashing_threshold(
    spec, 
    state, 
    conf_rule_wrapper
):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
        
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps)
        
    state, store, _ = yield from apply_next_slots_with_attestations(spec, state, store, 3 , True, True, test_steps=test_steps)
    
    root = get_block_root_from_head(spec, store, 2)
    block = store.block_states[root]
    
    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)
    
    conf_rule_wrapper.check_get_confirmation_score(store, root, test_steps, 13)
    
    yield 'steps', test_steps
    
