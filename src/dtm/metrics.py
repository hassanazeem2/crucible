from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .io import read_jsonl
from .scenario import Scenario


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def calculate_metrics(
    scenario: Scenario,
    raw_dir: Path,
    alert_path: Path,
    benign_alerts: int = 0,
    benign_events: int = 0,
) -> dict[str, Any]:
    actions = list(read_jsonl(raw_dir / "actions.jsonl"))
    alerts = list(read_jsonl(alert_path))
    detected = sorted({alert["rule_id"] for alert in alerts})
    expected = set(scenario.expected_rules)
    covered = expected.intersection(detected)

    first_action = min((_time(action["timestamp"]) for action in actions), default=None)
    first_alert = min((_time(alert["time"]) for alert in alerts), default=None)
    ttd = None
    if first_action and first_alert:
        ttd = max(0.0, (first_alert - first_action).total_seconds())

    return {
        "scenario_id": scenario.id,
        "expected_rule_count": len(expected),
        "detected_rule_count": len(covered),
        "coverage_percent": round(100 * len(covered) / len(expected), 2) if expected else 100.0,
        "missed_rules": sorted(expected - covered),
        "unexpected_rules": sorted(set(detected) - expected),
        "alert_count": len(alerts),
        "time_to_detect_seconds": ttd,
        "benign_event_count": benign_events,
        "false_positive_count": benign_alerts,
        "false_positive_rate": round(benign_alerts / benign_events, 4) if benign_events else 0.0,
    }

