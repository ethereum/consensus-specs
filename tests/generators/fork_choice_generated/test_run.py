import argparse
from collections import namedtuple
from glob import glob
import os
from pathlib import Path
from pathos.multiprocessing import ProcessingPool as Pool
from ruamel.yaml import YAML
from snappy import uncompress
from tqdm import tqdm
from typing import Iterable


from eth2spec.test.helpers.specs import spec_targets
from eth2spec.utils import bls


bls.bls_active = False


def read_yaml(fp):
    with open(fp) as f:
        yaml = YAML(typ='safe')
        return yaml.load(f.read())

def read_ssz_snappy(fp):
    with open(fp, 'rb') as f:
        res =  uncompress(f.read())
        return res


def get_test_case(spec, td):
    def get_prefix(p):
        return p[p.rindex('/')+1:p.rindex('.')]
    return (read_yaml(f'{td}/meta.yaml'),
            spec.BeaconBlock.decode_bytes(read_ssz_snappy(f'{td}/anchor_block.ssz_snappy')),
            spec.BeaconState.decode_bytes(read_ssz_snappy(f'{td}/anchor_state.ssz_snappy')),
            {get_prefix(b): spec.SignedBeaconBlock.decode_bytes(read_ssz_snappy(b)) for b in glob(f'{td}/block_*.ssz_snappy')},
            {get_prefix(b): spec.Attestation.decode_bytes(read_ssz_snappy(b)) for b in glob(f'{td}/attestation_*.ssz_snappy')},
            {get_prefix(b): spec.AttesterSlashing.decode_bytes(read_ssz_snappy(b)) for b in glob(f'{td}/attester_slashing_*.ssz_snappy')},
            read_yaml(f'{td}/steps.yaml'))


TestInfo = namedtuple('TestInfo', ['preset', 'fork', 'test_dir',])


def run_test(test_info):
    preset, fork, test_dir = test_info
    spec = spec_targets[preset][fork]
    meta, anchor_block, anchor_state, blocks, atts, slashings, steps = get_test_case(spec, test_dir)
    store = spec.get_forkchoice_store(anchor_state, anchor_block)
    for step in steps:
        if 'tick' in step:
            time = step['tick']
            spec.on_tick(store, time)
        elif 'block' in step:
            block_id = step['block']
            valid = step.get('valid', True)
            signed_block = blocks[block_id]
            if valid:
                spec.on_block(store, signed_block)
                for block_att in signed_block.message.body.attestations:
                    try:
                        spec.on_attestation(store, block_att, is_from_block=True)
                    except AssertionError:
                        pass
                for block_att_slashing in signed_block.message.body.attester_slashings:
                    try:
                        spec.on_attester_slashing(store, block_att_slashing)
                    except AssertionError:
                        pass
            else:
                try:
                    spec.on_block(store, signed_block)
                    assert False
                except AssertionError:
                    pass
        elif 'attestation' in step:
            att_id = step['attestation']
            valid = step.get('valid', True)
            attestation = atts[att_id]
            if valid:
                spec.on_attestation(store, attestation, is_from_block=False)
            else:
                try:
                    spec.on_attestation(store, attestation, is_from_block=False)
                    assert False
                except AssertionError:
                    pass
        elif 'attester_slashing' in step:
            slashing_id = step['attester_slashing']
            valid = step.get('valid', True)
            assert valid
            slashing = slashings[slashing_id]
            spec.on_attester_slashing(store, slashing)
        elif 'checks' in step:
            checks = step['checks']
            for check, value in checks.items():
                if check == 'time':
                    expected_time = value
                    assert store.time == expected_time
                elif check == 'head':
                    assert str(spec.get_head(store)) == value['root']
                elif check == 'proposer_boost_root':
                    assert str(store.proposer_boost_root) == str(value)
                elif check == 'justified_checkpoint':
                    checkpoint = store.justified_checkpoint
                    assert checkpoint.epoch == value['epoch']
                    assert str(checkpoint.root) == str(value['root'])
                elif check == 'finalized_checkpoint':
                    checkpoint = store.finalized_checkpoint
                    assert checkpoint.epoch == value['epoch']
                    assert str(checkpoint.root) == str(value['root'])
                elif check == 'viable_for_head_roots_and_weights':
                    filtered_block_roots = spec.get_filtered_block_tree(store).keys()
                    leaves_viable_for_head = [root for root in filtered_block_roots
                                            if not any(c for c in filtered_block_roots if store.blocks[c].parent_root == root)]
                    viable_for_head_roots_and_weights = {
                        str(viable_for_head_root): int(spec.get_weight(store, viable_for_head_root))
                        for viable_for_head_root in leaves_viable_for_head
                    }
                    expected = { kv['root']: kv['weight'] for kv in value}
                    assert expected == viable_for_head_roots_and_weights
                else:
                    assert False
        else:
            assert False


def gather_tests(tests_dir) -> Iterable[TestInfo]:
    for preset in [p.name for p in Path(tests_dir).glob('*') if p.name in spec_targets]:
        for fork in [f.name for f in (Path(tests_dir) / preset).glob('*') if f.name in spec_targets[preset]]:
            print(f'{preset}/{fork}')
            for test_dir in sorted([td for td in (Path(tests_dir) / preset / fork).glob('*/*/*/*')]):
                yield TestInfo(preset, fork, test_dir)


def runt_tests_parallel(tests_dir, num_proc=os.cpu_count()):
    def runner(test_info: TestInfo):
        try:
            run_test(test_info)
        except Exception as e:
            raise e

    tests = list(gather_tests(tests_dir))
    with Pool(processes=num_proc) as pool:
        for _ in tqdm(pool.imap(runner, tests), total=len(tests)):
            pass


def run_tests(tests_dir):
    for test_info in gather_tests(tests_dir):
        print(test_info.test_dir)
        run_test(test_info)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-i",
        "--test-dir",
        dest="test_dir",
        required=True,
        help="directory with generated tests"
    )
    args = arg_parser.parse_args()
    runt_tests_parallel(args.test_dir)


if __name__ == '__main__':
    main()
