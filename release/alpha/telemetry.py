"""Minimal OTLP/HTTP JSON emission without adding an SDK to the alpha image."""
from __future__ import annotations

import json
import secrets
import time
from urllib.request import Request, urlopen


def span_payload(name: str, attributes: dict, start_ns: int, end_ns: int) -> dict:
    def attribute(key, value):
        if isinstance(value, bool):
            encoded = {"boolValue": value}
        elif isinstance(value, int):
            encoded = {"intValue": str(value)}
        else:
            encoded = {"stringValue": str(value)}
        return {"key": key, "value": encoded}

    return {
        "resourceSpans": [{
            "resource": {"attributes": [attribute("service.name", "defensefactory-alpha-stage")]},
            "scopeSpans": [{
                "scope": {"name": "defensefactory.release.alpha", "version": "1"},
                "spans": [{
                    "traceId": secrets.token_hex(16),
                    "spanId": secrets.token_hex(8),
                    "name": name,
                    "kind": 1,
                    "startTimeUnixNano": str(start_ns),
                    "endTimeUnixNano": str(end_ns),
                    "attributes": [attribute(key, value) for key, value in sorted(attributes.items())],
                    "status": {"code": 1},
                }],
            }],
        }],
    }


def emit(endpoint: str, name: str, attributes: dict, start_ns: int, end_ns: int,
         timeout: float = 5.0) -> bool:
    if not endpoint:
        return False
    url = endpoint.rstrip("/") + "/v1/traces"
    data = json.dumps(span_payload(name, attributes, start_ns, end_ns),
                      separators=(",", ":")).encode()
    request = Request(url, method="POST", data=data,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        if response.status not in (200, 202):
            raise ValueError(f"OTLP collector returned {response.status}")
    return True


def now_ns() -> int:
    return time.time_ns()
