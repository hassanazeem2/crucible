from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

from .attacker import run_scenario
from .clock import DeterministicClock
from .io import read_jsonl
from .metrics import calculate_metrics
from .normalize import normalize_directory
from .report import render_report
from .scenario import load_scenario
from .sigma import detect
from .victim import create_server


def run_demo(root: Path, artifact_dir: Path) -> dict[str, object]:
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True)
    scenario = load_scenario(root / "scenarios" / "credential-access.json")
    clock = DeterministicClock()
    server = create_server("127.0.0.1", 0, raw_dir, clock.now, scenario.id)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        run_scenario(scenario, f"http://127.0.0.1:{port}", raw_dir, clock.now)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    event_path = artifact_dir / "ocsf-events.jsonl"
    alert_path = artifact_dir / "alerts.jsonl"
    normalize_directory(raw_dir, event_path)
    detect(event_path, root / "rules", alert_path, now=clock.now)

    benign_source = root / "fixtures" / "benign"
    benign_raw = artifact_dir / "benign-raw"
    shutil.copytree(benign_source, benign_raw)
    benign_events_path = artifact_dir / "benign-ocsf-events.jsonl"
    benign_alert_path = artifact_dir / "benign-alerts.jsonl"
    benign_events = normalize_directory(benign_raw, benign_events_path)
    benign_alerts = detect(benign_events_path, root / "rules", benign_alert_path)

    metrics = calculate_metrics(
        scenario,
        raw_dir,
        alert_path,
        benign_alerts=len(benign_alerts),
        benign_events=len(benign_events),
    )
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    render_report(raw_dir, event_path, alert_path, metrics, artifact_dir / "report.html")
    return metrics


def replay(root: Path, recording_dir: Path, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario = load_scenario(root / "scenarios" / "credential-access.json")
    source_events = recording_dir / "ocsf-events.jsonl"
    alert_path = output_dir / "alerts.jsonl"
    detect(source_events, root / "rules", alert_path)
    metrics = calculate_metrics(scenario, recording_dir / "raw", alert_path)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return metrics


def validate_recording(artifact_dir: Path) -> None:
    required = ("ocsf-events.jsonl", "alerts.jsonl", "metrics.json", "report.html")
    missing = [name for name in required if not (artifact_dir / name).exists()]
    if missing:
        raise RuntimeError(f"recording is incomplete: {', '.join(missing)}")
    if not list(read_jsonl(artifact_dir / "ocsf-events.jsonl")):
        raise RuntimeError("recording contains no OCSF events")

