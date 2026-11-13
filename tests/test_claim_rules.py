"""Public RULES.md command and packaged authoring-template checks."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/defensefactory/scripts/claim-rules.py"
REFERENCES = ROOT / "skills/defensefactory/references"


class ClaimRulesCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_packaged_rules_template_is_valid_and_extractable(self):
        output = self.root / "model.json"
        result = subprocess.run([sys.executable, str(SCRIPT), "extract", str(REFERENCES / "component-RULES.md"), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        model = json.loads(output.read_text())
        self.assertEqual(model["grammar"], "defensefactory/rules/v1")
        self.assertEqual(model["parser"], "factory-markdown-ast/1")
        self.assertEqual(model["claims"][0]["id"], "EXAMPLE-COMPONENT-BOUNDARY")

    def test_public_command_refuses_to_overwrite_output(self):
        output = self.root / "model.json"; output.write_text("preserve\n")
        result = subprocess.run([sys.executable, str(SCRIPT), "check", str(REFERENCES / "component-RULES.md"), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2); self.assertEqual(output.read_text(), "preserve\n")

    def test_descriptor_template_has_no_computed_state(self):
        descriptor = json.loads((REFERENCES / "contract-descriptor.json").read_text())
        raw = json.dumps(descriptor).lower()
        self.assertNotIn("sha256", raw); self.assertNotIn('"result"', raw); self.assertNotIn('"ticket"', raw)
        self.assertFalse(descriptor["requires"]["network"])


if __name__ == "__main__": unittest.main()
