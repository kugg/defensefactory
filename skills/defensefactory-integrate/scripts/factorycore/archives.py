"""Safe source-archive extraction compatible with Python 3.10 and later."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

from .core import require


def _target(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    require(name and not relative.is_absolute() and ".." not in relative.parts and "\\" not in name,
            "Archive member escapes the destination: " + name)
    target = root.joinpath(*relative.parts)
    for parent in target.parents:
        if parent == root:
            break
        require(not parent.is_symlink(), "Archive member traverses a symlink: " + name)
    return target


def extract_data(archive: tarfile.TarFile, destination: str | Path) -> None:
    """Extract regular Git-style data without relying on Python 3.12 filters."""
    root = Path(destination).resolve()
    require(root.is_dir() and not root.is_symlink(), "Archive destination must be a real directory")
    for member in archive.getmembers():
        target = _target(root, member.name)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            require(target.is_dir() and not target.is_symlink(), "Archive directory is not safe: " + member.name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        _target(root, member.name)
        require(not target.exists() and not target.is_symlink(), "Duplicate archive destination: " + member.name)
        if member.isfile():
            stream = archive.extractfile(member)
            require(stream is not None, "Archive file has no content: " + member.name)
            with stream, target.open("xb") as output:
                shutil.copyfileobj(stream, output)
            os.chmod(target, 0o755 if member.mode & 0o111 else 0o644)
            continue
        if member.issym():
            link = PurePosixPath(member.linkname)
            require(member.linkname and not link.is_absolute() and "\\" not in member.linkname,
                    "Archive symlink target is unsafe: " + member.name)
            resolved = (target.parent / Path(*link.parts)).resolve(strict=False)
            require(resolved == root or root in resolved.parents,
                    "Archive symlink escapes the destination: " + member.name)
            target.symlink_to(member.linkname)
            continue
        require(False, "Archive contains unsupported member type: " + member.name)
