from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from .attacker import run_scenario
from .clock import DeterministicClock
from .metrics import calculate_metrics
from .normalize import normalize_directory
from .pipeline import replay, run_demo, validate_recording
from .report import render_report
from .scenario import load_scenario
from .sigma import detect
from .victim import create_server


def project_root() -> Path:
    return Path(os.environ.get("DTM_ROOT", Path.cwd())).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(prog="dtm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo", help="run the complete local experiment")
    demo_parser.add_argument("--output", default="artifacts/latest")

    victim_parser = subparsers.add_parser("victim", help="run the victim service")
    victim_parser.add_argument("--host", default="0.0.0.0")
    victim_parser.add_argument("--port", type=int, default=8080)
    victim_parser.add_argument("--raw-dir", default="/data/raw")

    attack_parser = subparsers.add_parser("attack", help="execute the safe scenario")
    attack_parser.add_argument("--url", default="http://victim:8080")
    attack_parser.add_argument("--raw-dir", default="/data/raw")

    monitor_parser = subparsers.add_parser("monitor", help="normalize and detect")
    monitor_parser.add_argument("--raw-dir", default="/data/raw")
    monitor_parser.add_argument("--output-dir", default="/data")

    replay_parser = subparsers.add_parser("replay", help="re-run rules over a recording")
    replay_parser.add_argument("recording")
    replay_parser.add_argument("--output", default="artifacts/replay")

    gui_parser = subparsers.add_parser("gui", help="start the local web interface")
    gui_parser.add_argument("--host", default="127.0.0.1")
    gui_parser.add_argument("--port", type=int, default=8765)
    gui_parser.add_argument("--artifact-dir", default="artifacts/latest")
    gui_parser.add_argument("--no-open", action="store_true", help="do not open a browser automatically")

    args = parser.parse_args()
    root = project_root()
    scenario = load_scenario(root / "scenarios" / "credential-access.json")

    if args.command == "demo":
        metrics = run_demo(root, root / args.output)
    elif args.command == "gui":
        from .gui import serve_gui

        serve_gui(
            root,
            host=args.host,
            port=args.port,
            artifact_dir=root / args.artifact_dir,
            open_browser=not args.no_open,
        )
        return
    elif args.command == "victim":
        clock = DeterministicClock()
        server = create_server(args.host, args.port, Path(args.raw_dir), clock.now, scenario.id)
        server.serve_forever()
        return
    elif args.command == "attack":
        clock = DeterministicClock()
        run_scenario(scenario, args.url, Path(args.raw_dir), clock.now)
        metrics = {"status": "scenario complete"}
    elif args.command == "monitor":
        output = Path(args.output_dir)
        events = output / "ocsf-events.jsonl"
        alerts = output / "alerts.jsonl"
        normalize_directory(Path(args.raw_dir), events)
        detect(events, root / "rules", alerts)
        benign_raw = output / "benign-raw"
        if benign_raw.exists():
            shutil.rmtree(benign_raw)
        shutil.copytree(root / "fixtures" / "benign", benign_raw)
        benign_events = normalize_directory(benign_raw, output / "benign-ocsf-events.jsonl")
        benign_alerts = detect(
            output / "benign-ocsf-events.jsonl",
            root / "rules",
            output / "benign-alerts.jsonl",
        )
        metrics = calculate_metrics(
            scenario,
            Path(args.raw_dir),
            alerts,
            benign_alerts=len(benign_alerts),
            benign_events=len(benign_events),
        )
        (output / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        render_report(Path(args.raw_dir), events, alerts, metrics, output / "report.html")
    else:
        metrics = replay(root, Path(args.recording), Path(args.output))
        validate_recording(Path(args.recording))
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
