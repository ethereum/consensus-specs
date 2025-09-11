from .manifest import Manifest, manifest


def test_manifest_decorator_basic():
    """Test that the manifest decorator adds manifest attribute to function."""

    @manifest(fork_name="phase0", preset_name="minimal")
    def test_function():
        return "test"

    assert hasattr(test_function, "manifest")
    assert test_function.manifest.fork_name == "phase0"
    assert test_function.manifest.preset_name == "minimal"
    assert test_function() == "test"


def test_manifest_decorator_all_params():
    """Test that the manifest decorator works with all parameters."""

    @manifest(
        fork_name="deneb",
        preset_name="mainnet",
        runner_name="state_test",
        handler_name="block_processing",
        suite_name="attestation",
        case_name="valid_attestation",
    )
    def test_function():
        return "test"

    assert test_function.manifest.fork_name == "deneb"
    assert test_function.manifest.preset_name == "mainnet"
    assert test_function.manifest.runner_name == "state_test"
    assert test_function.manifest.handler_name == "block_processing"
    assert test_function.manifest.suite_name == "attestation"
    assert test_function.manifest.case_name == "valid_attestation"


def test_manifest_override():
    """Test that Manifest.override() works correctly."""
    base_manifest = Manifest(fork_name="phase0", preset_name="minimal")
    override_manifest = Manifest(fork_name="altair", runner_name="test")

    result = override_manifest.override(base_manifest)

    assert result.fork_name == "altair"  # Override takes precedence
    assert result.preset_name == "minimal"  # Falls back to base
    assert result.runner_name == "test"  # From override
    assert result.handler_name is None
    assert result.suite_name is None
    assert result.case_name is None
