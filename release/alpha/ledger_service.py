"""Synthetic ticket-ledger and immutable attachment service for alpha trials."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from urllib.parse import unquote, urlparse

from .protocol import (ProtocolError, STAGES, canonical, identity, receipt_identity,
                       safe_identifier, sha256, validate_receipt, validate_ticket)


MAX_BODY = 8 * 1024 * 1024


class NotFound(ProtocolError):
    pass


class Conflict(ProtocolError):
    pass


class LedgerStore:
    """A tiny durable ledger. It is a local test double, not a Linear replacement."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def run_root(self, run_id: str) -> Path:
        return self.root / safe_identifier(run_id, "run id")

    @staticmethod
    def _atomic(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def create_run(self, run_id: str, ticket: dict) -> dict:
        validate_ticket(ticket)
        root = self.run_root(run_id)
        path = root / "ticket.json"
        payload = canonical(ticket)
        with self.lock:
            if path.exists():
                if path.read_bytes() != payload:
                    raise Conflict("Run id already binds another ticket snapshot")
                return self.summary(run_id)
            root.mkdir(parents=True, exist_ok=False)
            self._atomic(path, payload)
            (root / "attachments").mkdir()
            (root / "receipts").mkdir()
        return self.summary(run_id)

    def ticket(self, run_id: str) -> dict:
        path = self.run_root(run_id) / "ticket.json"
        if not path.is_file():
            raise NotFound("Unknown run")
        try:
            value = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            raise ProtocolError("Stored ticket is corrupt") from error
        return validate_ticket(value)

    def put_attachment(self, run_id: str, expected_sha256: str, data: bytes) -> dict:
        self.ticket(run_id)
        if len(data) == 0 or len(data) > MAX_BODY:
            raise ProtocolError("Attachment size is outside the alpha bound")
        if sha256(data) != expected_sha256:
            raise ProtocolError("Attachment digest does not match its address")
        path = self.run_root(run_id) / "attachments" / expected_sha256
        with self.lock:
            if path.exists():
                if path.read_bytes() != data:
                    raise Conflict("Immutable attachment address already has different bytes")
            else:
                self._atomic(path, data)
        return {"sha256": expected_sha256, "bytes": len(data)}

    def attachment(self, run_id: str, digest: str) -> bytes:
        self.ticket(run_id)
        path = self.run_root(run_id) / "attachments" / digest
        if not path.is_file():
            raise NotFound("Attachment is missing")
        data = path.read_bytes()
        if sha256(data) != digest:
            raise ProtocolError("Stored attachment bytes changed")
        return data

    def receipt(self, run_id: str, stage: str) -> dict:
        safe_identifier(stage, "stage")
        path = self.run_root(run_id) / "receipts" / f"{stage}.json"
        if not path.is_file():
            raise NotFound("Stage receipt is missing")
        try:
            value = json.loads(path.read_text())
        except json.JSONDecodeError as error:
            raise ProtocolError("Stored receipt is corrupt") from error
        ticket = self.ticket(run_id)
        index = STAGES.index(stage)
        previous = None if index == 0 else self.receipt(run_id, STAGES[index - 1])["receipt_sha256"]
        return validate_receipt(value, ticket, stage, previous)

    def put_receipt(self, run_id: str, stage: str, receipt: dict) -> dict:
        ticket = self.ticket(run_id)
        authorized = ticket["authorized_stages"]
        if stage not in authorized:
            raise ProtocolError("Stage is outside the ticket-authorized pipeline prefix")
        expected_index = len(self.receipt_names(run_id))
        if expected_index >= len(authorized) or authorized[expected_index] != stage:
            raise Conflict("Stage is not the next durable handoff")
        previous = None
        if expected_index:
            previous = self.receipt(run_id, authorized[expected_index - 1])["receipt_sha256"]
        validate_receipt(receipt, ticket, stage, previous)
        attachment = self.attachment(run_id, receipt["output_attachment"]["sha256"])
        if len(attachment) != receipt["output_attachment"]["bytes"]:
            raise ProtocolError("Receipt attachment size changed")
        stored = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        stored["receipt_sha256"] = receipt_identity(stored)
        path = self.run_root(run_id) / "receipts" / f"{stage}.json"
        with self.lock:
            if path.exists():
                raise Conflict("Stage receipt is immutable")
            self._atomic(path, canonical(stored))
        return stored

    def receipt_names(self, run_id: str) -> list[str]:
        self.ticket(run_id)
        root = self.run_root(run_id) / "receipts"
        return [stage for stage in STAGES if (root / f"{stage}.json").is_file()]

    def summary(self, run_id: str) -> dict:
        ticket = self.ticket(run_id)
        receipts = [self.receipt(run_id, stage) for stage in self.receipt_names(run_id)]
        return {
            "run_id": run_id,
            "ticket": ticket,
            "ticket_sha256": identity(ticket),
            "receipts": receipts,
            "next_stage": ticket["authorized_stages"][len(receipts)]
            if len(receipts) < len(ticket["authorized_stages"]) else None,
            "complete": len(receipts) == len(ticket["authorized_stages"]),
            "qualification": "Synthetic local ledger readback; authority and authorship are not authenticated.",
        }


def handler_for(store: LedgerStore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "DefenseFactoryAlphaLedger/1"

        def log_message(self, fmt, *args):
            print(json.dumps({"service": "ledger", "message": fmt % args}), flush=True)

        def send_bytes(self, status: int, data: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def send_json(self, status: int, value: dict) -> None:
            self.send_bytes(status, canonical(value), "application/json")

        def body(self) -> bytes:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ProtocolError("Invalid Content-Length") from error
            if length <= 0 or length > MAX_BODY:
                raise ProtocolError("Request body is outside the alpha bound")
            data = self.rfile.read(length)
            if len(data) != length:
                raise ProtocolError("Request body ended early")
            return data

        def parts(self) -> list[str]:
            return [unquote(item) for item in urlparse(self.path).path.split("/") if item]

        def dispatch(self):
            parts = self.parts()
            if self.command == "GET" and parts == ["healthz"]:
                return self.send_json(200, {"status": "ok"})
            if len(parts) < 3 or parts[:2] != ["v1", "runs"]:
                raise NotFound("Unknown endpoint")
            run_id = parts[2]
            if self.command == "POST" and len(parts) == 3:
                value = json.loads(self.body())
                return self.send_json(201, store.create_run(run_id, value))
            if self.command == "GET" and len(parts) == 3:
                return self.send_json(200, store.summary(run_id))
            if len(parts) == 5 and parts[3] == "attachments":
                digest = parts[4]
                if self.command == "PUT":
                    return self.send_json(201, store.put_attachment(run_id, digest, self.body()))
                if self.command == "GET":
                    return self.send_bytes(200, store.attachment(run_id, digest),
                                           "application/octet-stream")
            if len(parts) == 5 and parts[3] == "stages":
                stage = parts[4]
                if self.command == "PUT":
                    value = json.loads(self.body())
                    return self.send_json(201, store.put_receipt(run_id, stage, value))
                if self.command == "GET":
                    return self.send_json(200, store.receipt(run_id, stage))
            raise NotFound("Unknown endpoint")

        def respond(self):
            try:
                self.dispatch()
            except NotFound as error:
                self.send_json(404, {"error": str(error)})
            except Conflict as error:
                self.send_json(409, {"error": str(error)})
            except (ProtocolError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                self.send_json(422, {"error": str(error)})

        do_GET = respond
        do_POST = respond
        do_PUT = respond

    return Handler


def serve(root: Path, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), handler_for(LedgerStore(root)))
    print(json.dumps({"service": "ledger", "listen": f"{host}:{port}",
                      "qualification": "synthetic local test double"}), flush=True)
    server.serve_forever()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    serve(args.root, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
