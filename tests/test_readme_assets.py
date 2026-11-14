import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReadmeEvidenceTests(unittest.TestCase):
    def test_synthetic_record_is_deterministic_and_explicitly_qualified(self):
        result = subprocess.run(
            [sys.executable, "docs/demo/synthetic_trial.py", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        actual = json.loads(result.stdout)
        expected = json.loads(
            (ROOT / "docs/demo/synthetic-trial.json").read_text(encoding="utf-8")
        )
        self.assertEqual(actual, expected)
        self.assertEqual(
            actual["verification"]["outcome"], "class_remediated_within_scope"
        )
        self.assertTrue(actual["delivery"]["proof_section_generated"])
        self.assertIn("No live finding", " ".join(actual["limitations"]))

    def test_published_media_have_expected_formats_and_source_frames(self):
        assets = ROOT / "docs/assets"
        self.assertEqual(
            (assets / "dark-factory-logo.png").read_bytes()[:8],
            b"\x89PNG\r\n\x1a\n",
        )
        self.assertEqual(
            (assets / "dark-factory-demo-poster.png").read_bytes()[:8],
            b"\x89PNG\r\n\x1a\n",
        )
        self.assertEqual(
            (assets / "dark-factory-demo.gif").read_bytes()[:6], b"GIF89a"
        )
        self.assertEqual(
            (assets / "dark-factory-demo.webm").read_bytes()[:4],
            b"\x1aE\xdf\xa3",
        )
        frames = sorted((ROOT / "docs/demo/frames").glob("*.svg"))
        self.assertEqual(len(frames), 5)
        for frame in frames:
            text = frame.read_text(encoding="utf-8")
            self.assertIn("SYNTHETIC HELPER DEMO", text)
            self.assertIn("NO MODEL OR SERVICE CALLS", text)

    def test_readme_local_links_and_media_targets_exist(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "A dark factory turning bugs into architectural enforcement.", readme
        )
        self.assertIn("Bugs go in security architecture comes out.", readme)
        self.assertIn("sequenceDiagram", readme)
        self.assertIn("experimental, manually operated workflow", readme)

        markdown_targets = re.findall(r"\[[^\]]*\]\(([^)]+)\)", readme)
        html_targets = re.findall(r'(?:href|src)="([^"]+)"', readme)
        for target in markdown_targets + html_targets:
            if target.startswith(("http://", "https://", "#")):
                continue
            local = target.split("#", 1)[0]
            self.assertTrue((ROOT / local).exists(), f"missing README target: {target}")


if __name__ == "__main__":
    unittest.main()
