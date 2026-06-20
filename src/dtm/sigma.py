from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import load_document, read_jsonl, write_jsonl


def get_path(document: dict[str, Any], dotted_path: str) -> Any:
    value: Any = document
    for part in dotted_path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _match_value(actual: Any, expected: Any, modifier: str) -> bool:
    if isinstance(expected, list):
        return any(_match_value(actual, candidate, modifier) for candidate in expected)
    if modifier == "contains":
        return str(expected).lower() in str(actual or "").lower()
    if modifier == "startswith":
        return str(actual or "").lower().startswith(str(expected).lower())
    if modifier == "endswith":
        return str(actual or "").lower().endswith(str(expected).lower())
    if modifier == "re":
        return bool(re.search(str(expected), str(actual or ""), re.IGNORECASE))
    return actual == expected


def matches_selection(event: dict[str, Any], selection: dict[str, Any]) -> bool:
    for expression, expected in selection.items():
        field, _, modifier = expression.partition("|")
        if not _match_value(get_path(event, field), expected, modifier):
            return False
    return True


def matches_rule(event: dict[str, Any], rule: dict[str, Any]) -> bool:
    detection = rule["detection"]
    condition = detection.get("condition", "selection").strip()
    tokens = condition.split()
    result: bool | None = None
    operator = "and"
    negate = False
    for token in tokens:
        if token in {"and", "or"}:
            operator = token
            continue
        if token == "not":
            negate = True
            continue
        if token not in detection or not isinstance(detection[token], dict):
            raise ValueError(f"unsupported Sigma condition token: {token}")
        selected = matches_selection(event, detection[token])
        if negate:
            selected = not selected
            negate = False
        result = selected if result is None else (result and selected if operator == "and" else result or selected)
    return bool(result)


def load_rules(rule_dir: Path) -> list[dict[str, Any]]:
    return [load_document(path) for path in sorted(rule_dir.glob("*.yml"))]


def detect(
    event_path: Path,
    rule_dir: Path,
    alert_path: Path,
    now=None,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    rules = load_rules(rule_dir)
    for event in read_jsonl(event_path):
        for rule in rules:
            if matches_rule(event, rule):
                alerts.append(
                    {
                        "time": now() if now else event["time"],
                        "event_time": event["time"],
                        "scenario_id": event.get("scenario_id"),
                        "rule_id": rule["id"],
                        "title": rule["title"],
                        "level": rule.get("level", "medium"),
                        "tags": rule.get("tags", []),
                        "event_uid": event["metadata"]["uid"],
                    }
                )
    alerts.sort(key=lambda item: (item["time"], item["rule_id"], item["event_uid"]))
    write_jsonl(alert_path, alerts)
    return alerts

