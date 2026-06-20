from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .io import read_jsonl, write_jsonl


STREAMS = ("authentication", "endpoint", "application", "network")


def _uid(event: dict[str, Any]) -> str:
    stable = "|".join(str(event.get(key, "")) for key in ("timestamp", "source", "event_type", "path"))
    return hashlib.sha256(stable.encode()).hexdigest()[:16]


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    event_type = event.get("event_type")
    common: dict[str, Any] = {
        "time": event["timestamp"],
        "metadata": {
            "uid": _uid(event),
            "product": {"name": "Detection Time Machine", "vendor_name": "DTM"},
            "version": "1.1.0",
            "original_event": event,
        },
        "scenario_id": event.get("scenario_id"),
        "src_endpoint": {"ip": event.get("src_ip")},
        "dst_endpoint": {"ip": event.get("dst_ip")},
        "severity_id": 1,
    }

    if event_type == "authentication":
        return {
            **common,
            "category_uid": 3,
            "class_uid": 3002,
            "activity_name": "Logon",
            "activity_id": 1,
            "status": event.get("outcome"),
            "status_id": 1 if event.get("outcome") == "success" else 2,
            "user": {"name": event.get("username")},
            "auth_protocol": event.get("method"),
        }
    if event_type == "process_start":
        return {
            **common,
            "category_uid": 1,
            "class_uid": 1007,
            "activity_name": "Launch",
            "activity_id": 1,
            "process": {
                "name": event.get("process_name"),
                "cmd_line": event.get("command_line"),
                "parent_process": {"name": event.get("parent_process")},
            },
            "unmapped": {"simulated": event.get("simulated", False)},
        }
    if event_type == "http_request":
        return {
            **common,
            "category_uid": 4,
            "class_uid": 4002,
            "activity_name": "HTTP Request",
            "activity_id": 1,
            "http_request": {
                "http_method": event.get("method"),
                "url": {"path": event.get("path")},
                "user_agent": event.get("user_agent"),
            },
            "http_response": {"code": event.get("status")},
            "user": {"name": event.get("username")},
        }
    if event_type == "network_connection":
        return {
            **common,
            "category_uid": 4,
            "class_uid": 4001,
            "activity_name": "Open",
            "activity_id": 1,
            "connection_info": {"protocol_name": event.get("protocol")},
            "traffic": {
                "method": event.get("method"),
                "path": event.get("path"),
                "status": event.get("status"),
            },
        }
    raise ValueError(f"unsupported event_type: {event_type!r}")


def normalize_directory(raw_dir: Path, output_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for stream in STREAMS:
        for event in read_jsonl(raw_dir / f"{stream}.jsonl"):
            events.append(normalize_event(event))
    events.sort(key=lambda item: (item["time"], item["metadata"]["uid"]))
    write_jsonl(output_path, events)
    return events

