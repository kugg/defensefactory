"""Serve a deterministic exact-ref Git fixture over dumb HTTP."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess

from .protocol import canonical


GIT_ENV = {
    "GIT_AUTHOR_NAME": "Defense Factory Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Defense Factory Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
}


def command(argv, *, cwd=None, env=None) -> str:
    completed = subprocess.run(argv, cwd=cwd, env={**os.environ, **(env or {})},
                               check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def prepare(fixture: Path, root: Path, public_url: str) -> dict:
    root = root.resolve()
    work = root / "work"
    web = root / "www"
    if root.exists():
        shutil.rmtree(root)
    work.mkdir(parents=True)
    web.mkdir()
    for source in sorted(fixture.iterdir()):
        target = work / source.name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    command(["git", "init", "--initial-branch=main"], cwd=work)
    command(["git", "add", "-A"], cwd=work)
    command(["git", "commit", "-m", "Synthetic alpha fixture"], cwd=work, env=GIT_ENV)
    revision = command(["git", "rev-parse", "HEAD"], cwd=work)
    bare = web / "fixture.git"
    command(["git", "clone", "--bare", str(work), str(bare)])
    command(["git", "update-server-info"], cwd=bare)
    metadata = {
        "schema": "defensefactory/alpha-source-fixture/v1",
        "repository": public_url.rstrip("/") + "/fixture.git",
        "revision": revision,
        "qualification": "Deterministic synthetic source fixture; no product claim.",
    }
    (web / "metadata.json").write_bytes(canonical(metadata))
    return metadata


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(json.dumps({"service": "source", "message": fmt % args}), flush=True)


def serve(fixture: Path, root: Path, public_url: str, host: str, port: int) -> None:
    metadata = prepare(fixture, root, public_url)
    handler = partial(QuietHandler, directory=str(root / "www"))
    print(json.dumps({"service": "source", "listen": f"{host}:{port}", **metadata}), flush=True)
    ThreadingHTTPServer((host, port), handler).serve_forever()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--public-url", default="http://source:8081")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args(argv)
    serve(args.fixture, args.root, args.public_url, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
