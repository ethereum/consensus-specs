import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "check_markdown_headings", Path(__file__).with_name("check_markdown_headings.py")
)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class HeadingTests(unittest.TestCase):
    def check(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.md"
            path.write_text(content, encoding="utf-8")
            return checker.check_file(path)

    def test_reports_real_heading_jump(self):
        self.assertEqual(len(self.check("# Title\n### Skipped\n")), 1)

    def test_ignores_tilde_fence(self):
        self.assertEqual(self.check("# Title\n~~~markdown\n#### Code\n~~~\n## Section\n"), [])

    def test_shorter_fence_does_not_close_longer_fence(self):
        self.assertEqual(self.check("# Title\n````markdown\n```\n#### Code\n````\n## Section\n"), [])

    def test_closing_fence_cannot_have_an_info_string(self):
        self.assertEqual(self.check("# Title\n```markdown\n```example\n#### Code\n```\n## Section\n"), [])

    def test_indented_fence_is_recognized(self):
        self.assertEqual(self.check("# Title\n   ~~~\n#### Code\n   ~~~\n## Section\n"), [])


if __name__ == "__main__":
    unittest.main()
