from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import yaml
import os


@dataclass
class Manifest:
    fork_name: str | None = None
    preset_name: str | None = None
    runner_name: str | None = None
    handler_name: str | None = None
    suite_name: str | None = None
    case_name: str | None = None

    def override(self, manifest: Manifest) -> Manifest:
        return Manifest(
            fork_name=self.fork_name if self.fork_name is not None else manifest.fork_name,
            preset_name=self.preset_name if self.preset_name is not None else manifest.preset_name,
            runner_name=self.runner_name if self.runner_name is not None else manifest.runner_name,
            handler_name=self.handler_name
            if self.handler_name is not None
            else manifest.handler_name,
            suite_name=self.suite_name if self.suite_name is not None else manifest.suite_name,
            case_name=self.case_name if self.case_name is not None else manifest.case_name,
        )

    def is_complete(self) -> bool:
        """Return True if all fields are not None."""
        return all(
            [
                self.fork_name is not None,
                self.preset_name is not None,
                self.runner_name is not None,
                self.handler_name is not None,
                self.suite_name is not None,
                self.case_name is not None,
            ]
        )
    
    def save_to_yaml(self, directory: str) -> None:
        """
        Save the manifest data as manifest.yml inside the given directory.
        """
        manifest_path = os.path.join(directory, "manifest.yml")
        data = {
            "fork_name": self.fork_name,
            "preset_name": self.preset_name,
            "runner_name": self.runner_name,
            "handler_name": self.handler_name,
            "suite_name": self.suite_name,
            "case_name": self.case_name,
        }

        with open(manifest_path, "w") as f:
            yaml.dump(data, f, sort_keys=False)


def manifest(
    _manifest: Manifest | None = None,
    fork_name: str | None = None,
    preset_name: str | None = None,
    runner_name: str | None = None,
    handler_name: str | None = None,
    suite_name: str | None = None,
    case_name: str | None = None,
    base_dir: str = "tests",
) -> Callable:
    """
    Decorator that adds the manifest to a vector generating test.
    The manifest is the metadata about which test vector this is generating,
    and overrides the defaults calculated from the framework.
    """

    def decorator(func: Callable) -> Callable:
        # Set the manifest attribute
        func.manifest = Manifest(
            fork_name=fork_name,
            preset_name=preset_name,
            runner_name=runner_name,
            handler_name=handler_name,
            suite_name=suite_name,
            case_name=case_name,
        )

        if _manifest is not None:
            func.manifest = func.manifest.override(_manifest)

        parts = [
            base_dir,
            func.manifest.preset_name,
            func.manifest.fork_name,
            func.manifest.runner_name,
            func.manifest.handler_name,
            func.manifest.suite_name,
            func.manifest.case_name,
        ]
        output_dir = os.path.join(*[p for p in parts if p])
        os.makedirs(output_dir, exist_ok=True)

        func.manifest.save_to_yaml(output_dir)

        return func

    return decorator
