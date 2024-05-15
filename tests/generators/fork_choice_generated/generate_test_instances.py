from dataclasses import dataclass, field
from itertools import product
from typing import Iterable
from toolz.dicttoolz import merge
from minizinc import Instance, Model, Solver
from ruamel.yaml import YAML
from typing_extensions import TypedDict


def solve_sm_links(anchor_epoch: int, number_of_epochs: int, number_of_links: int, number_of_solutions: int):
    sm_links = Model('./model/minizinc/SM_links.mzn')
    solver = Solver.lookup("gecode")
    instance = Instance(solver, sm_links)
    instance['AE'] = anchor_epoch  # anchor epoch
    instance['NE'] = number_of_epochs  # number of epochs, starting from AE
    instance['NL'] = number_of_links  # number of super-majority links

    assert number_of_solutions is None
    solutions = instance.solve(all_solutions=True)

    for i in range(len(solutions)):
        yield {'sm_links': list(zip(solutions[i, 'sources'], solutions[i, 'targets']))}


def generate_sm_links(params):
    anchor_epoch = params['anchor_epoch']
    number_of_epochs = params['number_of_epochs']
    number_of_links = params['number_of_links']
    number_of_solutions = params.get('number_of_solutions')
    yield from solve_sm_links(anchor_epoch, number_of_epochs, number_of_links, number_of_solutions)


def solve_block_tree(number_of_blocks: int,
                    max_children: int,
                    number_of_solutions: int) -> Iterable[dict]:
    model = Model('./model/minizinc/Block_tree.mzn')
    solver = Solver.lookup("gecode")
    instance = Instance(solver, model)
    instance['NB'] = number_of_blocks
    instance['MC'] = max_children

    if number_of_solutions is None:
        solutions = instance.solve(all_solutions=True)
    else:
        solutions = instance.solve(nr_solutions=number_of_solutions)
    
    return [{'block_parents': s.parent} for s in solutions]


def generate_block_tree(params) -> Iterable[dict]:
    number_of_blocks = params['number_of_blocks']
    max_children = params['max_children']
    number_of_solutions = params.get('number_of_solutions')
    yield from solve_block_tree(number_of_blocks, max_children, number_of_solutions)


def solve_block_cover(anchor_epoch: int,
                      store_justified_epoch_equal_zero: bool,
                      block_voting_source_epoch_equal_store_justified_epoch: bool,
                      block_voting_source_epoch_plus_two_greater_or_equal_current_epoch: bool,
                      block_is_leaf: bool,
                      number_of_solutions: int):
    block_cover3 = Model('./model/minizinc/Block_cover3.mzn')
    solver = Solver.lookup("gecode")
    instance = Instance(solver, block_cover3)
    instance['AE'] = anchor_epoch
    instance['store_je_eq_zero'] = store_justified_epoch_equal_zero
    instance['block_vse_eq_store_je'] = block_voting_source_epoch_equal_store_justified_epoch
    instance['block_vse_plus_two_ge_curr_e'] = block_voting_source_epoch_plus_two_greater_or_equal_current_epoch
    instance['block_is_leaf'] = block_is_leaf

    assert number_of_solutions is not None
    result = instance.solve(nr_solutions=number_of_solutions)

    if anchor_epoch == 0 and not store_justified_epoch_equal_zero:
        return

    for s in result.solution:
        max_block = s.max_block
        yield {'block_epochs': s.es[:max_block + 1],
               'parents': s.parents[:max_block + 1],
               'previous_justifications': s.prevs[:max_block + 1],
               'current_justifications': s.currs[:max_block + 1],
               'current_epoch': s.curr_e,
               'store_justified_epoch': s.store_je,
               'target_block': s.target_block,
               'predicates': {
                   'store_je_eq_zero': store_justified_epoch_equal_zero,
                   'block_vse_eq_store_je': block_voting_source_epoch_equal_store_justified_epoch,
                   'block_vse_plus_two_ge_curr_e': block_voting_source_epoch_plus_two_greater_or_equal_current_epoch,
                   'block_is_leaf': block_is_leaf
               }}


def generate_block_cover(params):
    anchor_epoch = params['anchor_epoch']
    number_of_solutions = params.get('number_of_solutions', 1)

    for ps in product(*([(True, False)] * 4)):
        yield from solve_block_cover(anchor_epoch, *ps, number_of_solutions)


# models = {
#     'sm_links': ModelKind('SMLinks', './model/minizinc/SM_links.mzn', {'AE': int, 'NE': int, 'NL': int}),
#     'block_cover': ModelKind('BlockCover', './model/minizinc/Block_cover3.mzn',
#                              {
#                                  'AE': int,
#                                  'store_je_eq_zero': bool,
#                                  'block_vse_eq_store_je': bool,
#                                  'block_vse_plus_two_ge_curr_e': bool,
#                                  'block_is_leaf': bool,
#                                  'block_is_justified_descendant': bool
#                              })
# }

gen_params = {
    ###################
    # small instances #
    ###################

    'block_tree_tree_small': {
        'out_path': 'block_tree_tree_small.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_epochs': 4, 'number_of_links': 3}, {'number_of_blocks': 8, 'max_children': 2, 'number_of_solutions': 3}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 16, 'max_children': 2, 'number_of_solutions': 3}),
        ]
    },
    'block_tree_other_small': {
        'out_path': 'block_tree_other_small.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 12, 'max_children': 2, 'number_of_solutions': 3}),
        ]
    },
    'block_cover_small': {
        'out_path': 'block_cover_small.yaml',
        'models': ['block_cover'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_solutions': 1},),
            ({'anchor_epoch': 2, 'number_of_solutions': 1},),
        ]
    },

    ###################
    # smoke instances #
    ###################

    'block_tree_tree_smoke': {
        'out_path': 'block_tree_tree_smoke.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_epochs': 5, 'number_of_links': 3}, {'number_of_blocks': 16, 'max_children': 2, 'number_of_solutions': 2}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 5, 'max_children': 3, 'number_of_solutions': None}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 12, 'max_children': 2, 'number_of_solutions': 73}),
        ]
    },
    'block_tree_tree_smoke_2': {
        'out_path': 'block_tree_tree_smoke_2.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_epochs': 6, 'number_of_links': 4}, {'number_of_blocks': 16, 'max_children': 2, 'number_of_solutions': 2}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 6, 'max_children': 4, 'number_of_solutions': None}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 12, 'max_children': 2, 'number_of_solutions': 283}),
        ]
    },
    'block_tree_other_smoke': {
        'out_path': 'block_tree_other_smoke.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 12, 'max_children': 2, 'number_of_solutions': 4}),
        ]
    },
    'block_cover_smoke': {
        'out_path': 'block_cover_smoke.yaml',
        'models': ['block_cover'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_solutions': 2},),
            ({'anchor_epoch': 2, 'number_of_solutions': 2},),
        ]
    },

    ######################
    # standard instances #
    ######################

    'block_tree_tree': {
        'out_path': 'block_tree_tree.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_epochs': 6, 'number_of_links': 4}, {'number_of_blocks': 16, 'max_children': 2, 'number_of_solutions': 5}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 6, 'max_children': 4, 'number_of_solutions': None}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 7, 'max_children': 2, 'number_of_solutions': None}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 16, 'max_children': 2, 'number_of_solutions': 358}),
        ]
    },
    'block_tree_tree_2': {
        'out_path': 'block_tree_tree_2.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_epochs': 6, 'number_of_links': 4}, {'number_of_blocks': 16, 'max_children': 2, 'number_of_solutions': 5}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 6, 'max_children': 4, 'number_of_solutions': None}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 7, 'max_children': 3, 'number_of_solutions': None}),
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 16, 'max_children': 2, 'number_of_solutions': 3101}),
        ]
    },
    'block_tree_other': {
        'out_path': 'block_tree_other.yaml',
        'models': ['sm_link', 'block_tree'],
        'params': [
            ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}],  {'number_of_blocks': 12, 'max_children': 2, 'number_of_solutions': 8}),
        ]
    },
    'block_cover': {
        'out_path': 'block_cover.yaml',
        'models': ['block_cover'],
        'params': [
            ({'anchor_epoch': 0, 'number_of_solutions': 2},),
            ({'anchor_epoch': 2, 'number_of_solutions': 5},),
        ]
    },


    #############
    # old stuff #
    #############

    # 'attester_slashings_test': {
    #     'out_path': 'attester_slashings.yaml',
    #     'models': ['sm_link', 'block_tree'],
    #     'params': [
    #         ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}], {'number_of_blocks': 16, 'max_children': 3, 'number_of_solutions': 4}),
    #         ({'anchor_epoch': 0, 'number_of_epochs': 4, 'number_of_links': 3}, {'number_of_blocks': 4, 'max_children': 3, 'number_of_solutions': 4}),
    #         ({'anchor_epoch': 0, 'number_of_epochs': 5, 'number_of_links': 4}, {'number_of_blocks': 4, 'max_children': 3, 'number_of_solutions': 4}),
    #     ]
    # },
    # 'invalid_messages_test': {
    #     'out_path': 'invalid_messages.yaml',
    #     'models': ['sm_link', 'block_tree'],
    #     'params': [
    #         ([{'sm_links': [[0, 1], [0, 2], [2, 3], [3, 4]]}], {'number_of_blocks': 16, 'max_children': 3, 'number_of_solutions': 4}),
    #         ({'anchor_epoch': 0, 'number_of_epochs': 4, 'number_of_links': 3}, {'number_of_blocks': 4, 'max_children': 3, 'number_of_solutions': 4}),
    #         ({'anchor_epoch': 0, 'number_of_epochs': 5, 'number_of_links': 4}, {'number_of_blocks': 4, 'max_children': 3, 'number_of_solutions': 4}),
    #     ]
    # },
    # 'block_cover_1': {
    #     'out_path': 'block_cover_1.yaml',
    #     'models': ['block_cover'],
    #     'params': [
    #         ({'anchor_epoch': 0, 'number_of_solutions': 1},),
    #         ({'anchor_epoch': 2, 'number_of_solutions': 1},),
    #     ]
    # },
    # 'block_cover_100': {
    #     'out_path': 'block_cover_100.yaml',
    #     'models': ['block_cover'],
    #     'params': [
    #         ({'anchor_epoch': 0, 'number_of_solutions': 100},),
    #         ({'anchor_epoch': 2, 'number_of_solutions': 100},),
    #     ]
    # }
}


if __name__ == '__main__':
    yaml = YAML(typ='safe')
    sm_links = []

    for model_name, parameters in gen_params.items():
        print(f'processing {model_name}')
        out_path = parameters['out_path']
        models = parameters['models']
        solutions = []
        for params in parameters['params']:
            model_solutions = []
            for model, mod_params in zip(models, params):
                print(f'  model: {model}')
                print(f'  parameters: {mod_params}')
                if isinstance(mod_params, list):
                    model_solutions.append(mod_params)
                elif isinstance(mod_params, dict):
                    if model == 'sm_link':
                        model_solutions.append(list(generate_sm_links(mod_params)))
                    elif model == 'block_tree':
                        model_solutions.append(list(generate_block_tree(mod_params)))
                    elif model == 'block_cover':
                        model_solutions.append(list(generate_block_cover(mod_params)))
                    else:
                        print('todo', model, mod_params)
                else:
                    assert False
            results = [merge(*sol) for sol in product(*model_solutions)]
            solutions.extend(results)
        with open(out_path, 'w') as f:
            yaml.dump(solutions, f)
