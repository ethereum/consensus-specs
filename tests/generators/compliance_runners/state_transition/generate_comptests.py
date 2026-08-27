from __future__ import annotations

from tests.generators.compliance_runners.state_transition.run import run


def test_generate_compliance_tests(comptests_output, handler, profile):
    assert run(handler, comptests_output, profile) == 0
