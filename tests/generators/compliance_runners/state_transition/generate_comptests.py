from __future__ import annotations

from tests.generators.compliance_runners.state_transition.provider import run


def test_generate_compliance_tests(comptests_output, handler, profile, preset):
    assert run(handler, comptests_output, profile, preset) == 0
