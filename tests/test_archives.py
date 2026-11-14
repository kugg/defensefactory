"""Python-version-independent safe archive extraction tests."""
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/defensefactory/scripts"))

from factorycore.archives import extract_data
from factorycore.core import GateError


class ArchiveCompatibilityTests(unittest.TestCase):
    def archive(self, rows):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w") as handle:
            for name, body, kind in rows:
                info = tarfile.TarInfo(name)
                if kind == "file":
                    raw = body.encode(); info.size = len(raw); info.mode = 0o755 if name.endswith(".sh") else 0o644
                    handle.addfile(info, io.BytesIO(raw))
                elif kind == "symlink":
                    info.type = tarfile.SYMTYPE; info.linkname = body; handle.addfile(info)
        output.seek(0)
        return output

    def extract(self, rows):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        destination = Path(temporary.name)
        with tarfile.open(fileobj=self.archive(rows), mode="r:") as archive:
            extract_data(archive, destination)
        return destination

    def test_regular_files_and_bounded_symlinks_extract_without_filter_argument(self):
        destination = self.extract([("bin/check.sh", "#!/bin/sh\n", "file"), ("check-link", "bin/check.sh", "symlink")])
        self.assertEqual((destination / "bin/check.sh").read_text(), "#!/bin/sh\n")
        self.assertTrue((destination / "bin/check.sh").stat().st_mode & 0o111)
        self.assertEqual((destination / "check-link").resolve(), destination.resolve() / "bin/check.sh")

    def test_traversal_and_escaping_symlink_are_rejected(self):
        with self.assertRaisesRegex(GateError, "escapes the destination"):
            self.extract([("../escape", "bad", "file")])
        with self.assertRaisesRegex(GateError, "symlink escapes"):
            self.extract([("escape", "../../outside", "symlink")])


if __name__ == "__main__": unittest.main()
