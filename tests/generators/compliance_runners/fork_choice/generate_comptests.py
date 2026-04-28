from __future__ import annotations

import shutil

from tests.generators.compliance_runners.gen_base.output import dump_test_case_result
from tests.infra.dumper import Dumper


def test_generate_compliance_group(test_group, comptests_output_dir):
    dumper = Dumper()

    for test_case in test_group.test_cases:
        test_case.set_output_dir(comptests_output_dir)
        if test_case.dir.exists():
            shutil.rmtree(test_case.dir)

    for test_case_result in test_group.group_fn():
        dump_test_case_result(test_case_result, dumper)
