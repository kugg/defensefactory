"""Container entrypoint for alpha ledger, source and disposable stage roles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import subprocess

from . import ledger_service, source_service, stage_worker
from .protocol import read_json, validate_profiles


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    ledger = sub.add_parser("ledger")
    ledger.add_argument("--root", type=Path, default=Path("/var/lib/defensefactory-ledger"))
    ledger.add_argument("--host", default="0.0.0.0")
    ledger.add_argument("--port", type=int, default=8080)
    source = sub.add_parser("source")
    source.add_argument("--fixture", type=Path,
                        default=Path("/opt/defensefactory/release/alpha/fixtures/source"))
    source.add_argument("--root", type=Path, default=Path("/tmp/source-service"))
    source.add_argument("--public-url", default="http://source:8081")
    source.add_argument("--host", default="0.0.0.0")
    source.add_argument("--port", type=int, default=8081)
    stage = sub.add_parser("stage")
    stage.add_argument("--stage", required=True, choices=stage_worker.STAGES)
    stage.add_argument("--ledger", default="http://ledger:8080")
    stage.add_argument("--run-id", required=True)
    stage.add_argument("--profiles", type=Path,
                       default=Path("/opt/defensefactory/release/alpha/capability-profiles.json"))
    stage.add_argument("--image-digest", required=True)
    stage.add_argument("--telemetry-endpoint", default="http://otel:4318")
    check = sub.add_parser("validate")
    check.add_argument("--profiles", type=Path,
                       default=Path("/opt/defensefactory/release/alpha/capability-profiles.json"))
    sub.add_parser("inventory")
    args = parser.parse_args(argv)
    if args.command == "ledger":
        ledger_service.serve(args.root, args.host, args.port)
        return 0
    if args.command == "source":
        source_service.serve(args.fixture, args.root, args.public_url, args.host, args.port)
        return 0
    if args.command == "stage":
        return stage_worker.main(["--stage", args.stage, "--ledger", args.ledger,
            "--run-id", args.run_id, "--profiles", str(args.profiles),
            "--image-digest", args.image_digest, "--telemetry-endpoint",
            args.telemetry_endpoint])
    if args.command == "inventory":
        def version(argv):
            completed = subprocess.run(argv, capture_output=True, text=True)
            return {"argv": argv, "exit_code": completed.returncode,
                    "version": (completed.stdout or completed.stderr).strip().splitlines()[0]}
        print(json.dumps({
            "schema": "defensefactory/alpha-dependency-inventory/v1",
            "platform": platform.platform(),
            "python": version(["python3", "--version"]),
            "git": version(["git", "--version"]),
            "node": version(["node", "--version"]),
            "go": version(["go", "version"]),
            "opencode": version(["opencode", "--version"]),
            "qualification": "Runtime version inventory, not a complete package-level SBOM.",
        }, sort_keys=True))
        return 0
    validate_profiles(read_json(args.profiles))
    print("alpha capability profiles: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
