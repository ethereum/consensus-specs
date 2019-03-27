import random
import sys
import os

import yaml

from constants import ACTIVATION_EXIT_DELAY, FAR_FUTURE_EPOCH
from core_helpers import get_shuffling
from yaml_objects import Validator


def noop(self, *args, **kw):
    # Prevent !!str or !!binary tags
    pass


yaml.emitter.Emitter.process_tag = noop


EPOCH = 1000  # The epoch, also a mean for the normal distribution

# Standard deviation, around 8% validators will activate or exit within
# ENTRY_EXIT_DELAY inclusive from EPOCH thus creating an edge case for validator
# shuffling
RAND_EPOCH_STD = 35
MAX_EXIT_EPOCH = 5000  # Maximum exit_epoch for easier reading


def active_exited_validators_generator():
    """
    Random cases with variety of validator's activity status
    """
    # Order not preserved - https://github.com/yaml/pyyaml/issues/110
    metadata = {
        'title': 'Shuffling Algorithm Tests 1',
        'summary': 'Test vectors for validator shuffling with different validator\'s activity status.'
                   ' Note: only relevant validator fields are defined.',
        'test_suite': 'shuffle',
        'fork': 'phase0-0.5.0',
    }

    # Config
    random.seed(int("0xEF00BEAC", 16))
    num_cases = 10

    test_cases = []

    for case in range(num_cases):
        seedhash = bytes(random.randint(0, 255) for byte in range(32))
        idx_max = random.randint(128, 512)

        validators = []
        for idx in range(idx_max):
            v = Validator(original_index=idx)
            # 4/5 of all validators are active
            if random.random() < 0.8:
                # Choose a normally distributed epoch number
                rand_epoch = round(random.gauss(EPOCH, RAND_EPOCH_STD))

                # for 1/2 of *active* validators rand_epoch is the activation epoch
                if random.random() < 0.5:
                    v.activation_epoch = rand_epoch

                    # 1/4 of active validators will exit in forseeable future
                    if random.random() < 0.5:
                        v.exit_epoch = random.randint(
                            rand_epoch + ACTIVATION_EXIT_DELAY + 1, MAX_EXIT_EPOCH)
                    # 1/4 of active validators in theory remain in the set indefinitely
                    else:
                        v.exit_epoch = FAR_FUTURE_EPOCH
                # for the other active 1/2 rand_epoch is the exit epoch
                else:
                    v.activation_epoch = random.randint(
                        0, rand_epoch - ACTIVATION_EXIT_DELAY)
                    v.exit_epoch = rand_epoch

            # The remaining 1/5 of all validators is not activated
            else:
                v.activation_epoch = FAR_FUTURE_EPOCH
                v.exit_epoch = FAR_FUTURE_EPOCH

            validators.append(v)

        input_ = {
            'validators': validators,
            'epoch': EPOCH
        }
        output = get_shuffling(
            seedhash, validators, input_['epoch'])

        test_cases.append({
            'seed': '0x' + seedhash.hex(), 'input': input_, 'output': output
        })

    return {
        'metadata': metadata,
        'filename': 'test_vector_shuffling.yml',
        'test_cases': test_cases
    }


def validators_set_size_variety_generator():
    """
    Different validator set size cases, inspired by removed manual `permutated_index` tests
    https://github.com/ethereum/eth2.0-test-generators/tree/bcd9ab2933d9f696901d1dfda0828061e9d3093f/permutated_index
    """
    # Order not preserved - https://github.com/yaml/pyyaml/issues/110
    metadata = {
        'title': 'Shuffling Algorithm Tests 2',
        'summary': 'Test vectors for validator shuffling with different validator\'s set size.'
                   ' Note: only relevant validator fields are defined.',
        'test_suite': 'shuffle',
        'fork': 'tchaikovsky',
        'version': 1.0
    }

    # Config
    random.seed(int("0xEF00BEAC", 16))

    test_cases = []

    seedhash = bytes(random.randint(0, 255) for byte in range(32))
    idx_max = 4096
    set_sizes = [1, 2, 3, 1024, idx_max]

    for size in set_sizes:
        validators = []
        for idx in range(size):
            v = Validator(original_index=idx)
            v.activation_epoch = EPOCH
            v.exit_epoch = FAR_FUTURE_EPOCH
            validators.append(v)
        input_ = {
            'validators': validators,
            'epoch': EPOCH
        }
        output = get_shuffling(
            seedhash, validators, input_['epoch'])

        test_cases.append({
            'seed': '0x' + seedhash.hex(), 'input': input_, 'output': output
        })

    return {
        'metadata': metadata,
        'filename': 'shuffling_set_size.yml',
        'test_cases': test_cases
    }


if __name__ == '__main__':
    output_dir = sys.argv[2]
    for generator in [active_exited_validators_generator, validators_set_size_variety_generator]:
        result = generator()
        filename = os.path.join(output_dir, result['filename'])
        with open(filename, 'w') as outfile:
            # Dump at top level
            yaml.dump(result['metadata'], outfile, default_flow_style=False)
            # default_flow_style will unravel "ValidatorRecord" and "committee" line, exploding file size
            yaml.dump({'test_cases': result['test_cases']}, outfile)
