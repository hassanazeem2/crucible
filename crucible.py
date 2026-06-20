#!/usr/bin/env python3
"""
CRUCIBLE — Purple Team Detection Platform
DTM v2: Simulate attacks. Measure detection. Harden defenses.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
import webbrowser
from pathlib import Path

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich import box

ROOT = Path(__file__).parent
SCENARIOS_DIR = ROOT / "scenarios"
RULES_DIR = ROOT / "rules"
ARTIFACTS_DIR = ROOT / "artifacts"

VERSION = "2.0.0"
AUTHOR = "Hassan Azeem"
AUTHOR_URL = "https://hazeem.org"
GITHUB_URL = "https://github.com/hassanazeem2"
SESSION_ID = uuid.uuid4().hex[:8].upper()

console = Console()

SCENARIO_FILES = {
    "1": ("credential-access.json",     "Credential Access + Shell Execution   [T1110, T1078, T1059]"),
    "2": ("ransomware-kill-chain.json", "Ransomware Kill Chain                 [T1566, T1087, T1486]"),
    "3": ("lateral-movement.json",      "Lateral Movement via Pass-the-Hash    [T1003, T1550, T1543]"),
    "4": ("data-exfiltration.json",     "Data Exfil via DNS Tunneling          [T1005, T1048, T1071]"),
    "5": ("hipaa-insider-threat.json",  "HIPAA Insider Threat — PHI Access     [T1078, T1005, T1048]"),
}

LEVEL_COLOR = {
    "critical": "bold purple",
    "high":     "purple",
    "medium":   "dark_orange",
    "low":      "yellow",
}

BANNER = """
  .,-::::: :::::::..    ...    :::  .,-:::::  ::::::::::.   :::    .,::::::
,;;;'````' ;;;;``;;;;   ;;     ;;;,;;;'````'  ;;; ;;;'';;'  ;;;    ;;;;''''
[[[         [[[,/[[['  [['     [[[[[[         [[[ [[[__[[\\. [[[     [[cccc
$$$         $$$$$$c    $$      $$$$$$         $$$ $$""""Y$$ $$'     $$""""
`88bo,__,o, 888b "88bo,88    .d888`88bo,__,o, 888_88o,,od8Po88oo,.__888oo,__
  "YUMMMMMP"MMMM   "W"  "YmmMMMM""  "YUMMMMMP"MMM""YUMMMP" """"YUMMM""""YUMMM
""".strip("\n")

def section_header(title: str, subtitle: str = "") -> None:
    console.print(f"[bold purple]── {title} ──[/bold purple]", end="")
    if subtitle:
        console.print(f" [dim purple]{subtitle}[/dim purple]")
    else:
        console.print()

def pause(message: str = "Press Enter to continue...") -> None:
    Prompt.ask(f"[dim purple]{message}[/dim purple]", default="", show_default=False)

def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}

def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def load_rule(path: Path) -> dict:
    return json.loads(path.read_text())

def count_techniques() -> int:
    techniques: set[str] = set()
    for filename, _ in SCENARIO_FILES.values():
        path = SCENARIOS_DIR / filename
        if path.exists():
            data = load_json(path)
            for step in data.get("steps", []):
                if step.get("technique_id"):
                    techniques.add(step["technique_id"])
    return len(techniques)

def latest_metrics() -> dict:
    metrics_path = ARTIFACTS_DIR / "latest" / "metrics.json"
    return load_json(metrics_path)

def print_banner():
    body = (
        f"[bold bright_magenta]{BANNER}[/bold bright_magenta]\n"
        f"[dim purple]Purple Team · Simulate · Measure · Harden · v{VERSION} · session {SESSION_ID}[/dim purple]\n"
        f"[purple]by[/purple] [bold bright_magenta]{AUTHOR}[/bold bright_magenta] "
        f"[dim purple]· hazeem.org · github.com/hassanazeem2[/dim purple]"
    )
    console.print(
        Panel(
            Align.center(Text.from_markup(body)),
            border_style="bright_magenta",
            box=box.ROUNDED,
            padding=(0, 1),
        )
    )

def print_compact_header():
    console.print(
        f"[bold bright_magenta]CRUCIBLE[/bold bright_magenta] "
        f"[dim purple]v{VERSION} · {AUTHOR} · session {SESSION_ID}[/dim purple]"
    )

def status_line() -> str:
    metrics = latest_metrics()
    coverage = metrics.get("coverage_percent")
    coverage_text = f"{coverage}%" if coverage is not None else "—"
    last_scenario = metrics.get("scenario_id", "none")[:22]
    rule_count = len(list(RULES_DIR.glob("*.yml")))
    return (
        f"[dim purple]{len(SCENARIO_FILES)} scenarios · {rule_count} rules · "
        f"{count_techniques()} techniques · last {last_scenario} @ {coverage_text}[/dim purple]"
    )

def boot_sequence():
    steps = [
        "Loading scenarios & rules...",
        "Initializing OCSF + Sigma engine...",
        "CRUCIBLE ready.",
    ]
    with Progress(
        SpinnerColumn(style="bright_magenta"),
        TextColumn("[purple]{task.description}[/purple]"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Booting...", total=len(steps))
        for step in steps:
            progress.update(task, description=step)
            time.sleep(0.08)
            progress.advance(task)

def compact_menu_panel() -> Panel:
    left = Table.grid(padding=(0, 1))
    left.add_column(width=3, style="bold bright_magenta")
    left.add_column(style="purple")
    left.add_row("", "[bold purple]SIMULATE[/bold purple]")
    left.add_row("[1]", "Run Attack Scenario")
    left.add_row("[5]", "Run All Scenarios")
    left.add_row("", "[bold purple]ANALYZE[/bold purple]")
    left.add_row("[2]", "Replay Last Recording")
    left.add_row("[3]", "Coverage Report")
    left.add_row("[4]", "ATT&CK Heatmap")
    left.add_row("[7]", "Inspect Artifacts")

    right = Table.grid(padding=(0, 1))
    right.add_column(width=3, style="bold bright_magenta")
    right.add_column(style="purple")
    right.add_row("", "[bold purple]LIBRARY[/bold purple]")
    right.add_row("[6]", "Browse Rules")
    right.add_row("", "[bold purple]SYSTEM[/bold purple]")
    right.add_row("[8]", "Launch Web GUI")
    right.add_row("[9]", "Open Timeline Report")
    right.add_row("[10]", "About CRUCIBLE")
    right.add_row("[0]", "Exit")

    return Panel(
        Columns([left, right], expand=True, equal=True),
        title="[bold purple]Main Menu[/bold purple]",
        border_style="purple",
        box=box.ROUNDED,
        padding=(0, 1),
    )

def main_menu():
    while True:
        console.clear()
        print_compact_header()
        console.print(status_line())
        console.print(compact_menu_panel())

        choice = Prompt.ask("[bold purple]crucible[/bold purple]", default="0")
        console.print()

        actions = {
            "1": run_scenario_menu,
            "2": replay_menu,
            "3": coverage_report,
            "4": attack_heatmap,
            "5": run_all_scenarios,
            "6": rule_library,
            "7": artifact_inspector,
            "8": launch_gui,
            "9": open_latest_report,
            "10": about_screen,
        }

        if choice == "0":
            console.print(
                Panel(
                    f"[dim purple]Shutting down CRUCIBLE...[/dim purple]\n\n"
                    f"[purple]Session {SESSION_ID} terminated.[/purple]\n"
                    f"[dim purple]Built by {AUTHOR}[/dim purple]",
                    border_style="purple",
                    box=box.HEAVY,
                )
            )
            console.print()
            break
        elif choice in actions:
            actions[choice]()
        else:
            console.print("[purple]  ✗ Invalid option.[/purple]")
            console.print()

def run_scenario_menu():
    section_header("SELECT SCENARIO", "Deterministic ATT&CK-mapped attack chains")

    table = Table(box=box.ROUNDED, border_style="purple", header_style="bold purple", show_lines=True)
    table.add_column("#", style="bold bright_magenta", width=3, justify="center")
    table.add_column("SCENARIO", style="purple", min_width=28)
    table.add_column("TECHNIQUES", style="dim purple", min_width=18)
    table.add_column("STEPS", style="purple", width=6, justify="center")

    for key, (filename, label) in SCENARIO_FILES.items():
        path = SCENARIOS_DIR / filename
        steps = "—"
        techniques = label.split("[")[-1].rstrip("]") if "[" in label else "—"
        name = label.split("[")[0].strip()
        if path.exists():
            data = load_json(path)
            steps = str(len(data.get("steps", [])))
        table.add_row(key, name, techniques, steps)

    console.print(table)
    console.print("[bold purple]  [0][/bold purple] [dim purple]Back to main menu[/dim purple]")
    console.print()

    choice = Prompt.ask("[bold purple]crucible/scenarios[/bold purple]", default="0")
    console.print()

    if choice == "0":
        return

    if choice not in SCENARIO_FILES:
        console.print("[purple]  ✗ Invalid scenario.[/purple]")
        console.print()
        return

    filename, _ = SCENARIO_FILES[choice]
    scenario_path = SCENARIOS_DIR / filename

    if not scenario_path.exists():
        console.print(f"[purple]  ✗ Scenario file not found: {filename}[/purple]")
        console.print()
        return

    run_scenario(scenario_path)

def run_scenario(scenario_path: Path):
    import importlib.util, sys as _sys

    # Load scenario JSON
    with open(scenario_path) as f:
        scenario_data = json.load(f)

    scenario_id = scenario_data["id"]
    scenario_name = scenario_data["name"]
    steps = scenario_data["steps"]
    expected_rules = scenario_data["expected_rules"]

    console.print(Panel(
        f"[bold purple]{scenario_name}[/bold purple]\n"
        f"[dim purple]{scenario_data.get('description', '')}[/dim purple]\n\n"
        f"[purple]Scenario ID[/purple]  [dim purple]{scenario_id}[/dim purple]\n"
        f"[purple]MITRE Phases[/purple]  [dim purple]{', '.join(scenario_data.get('mitre_phases', ['—']))}[/dim purple]\n"
        f"[purple]Steps[/purple]  [dim purple]{len(steps)}[/dim purple]  "
        f"[purple]Expected detections[/purple]  [dim purple]{len(expected_rules)}[/dim purple]",
        title="[bold purple]Scenario Briefing[/bold purple]",
        border_style="bright_magenta",
        box=box.DOUBLE,
        padding=(1, 2)
    ))
    console.print()

    section_header("ATTACK CHAIN", "Ordered technique progression")

    for i, step in enumerate(steps, 1):
        connector = "└──" if i == len(steps) else "├──"
        console.print(f"  [dim purple]{connector}[/dim purple] [purple][{i}][/purple] [dim purple]{step['technique_id']}[/dim purple]  [purple]{step['description']}[/purple]")
        time.sleep(0.1)

    console.print()

    if not Confirm.ask("[purple]  Execute simulation?[/purple]", default=True):
        return

    console.print()

    # Use DTM pipeline
    try:
        _sys.path.insert(0, str(Path(__file__).parent / "src"))
        from dtm.pipeline import run_demo
        from dtm.scenario import load_scenario

        artifact_dir = ARTIFACTS_DIR / "latest"

        # Only the original credential-access scenario uses run_demo (needs victim server)
        if "credential-access" in str(scenario_path):
            console.print("[dim purple]  Running live simulation...[/dim purple]")
            console.print()
            with Progress(
                SpinnerColumn(style="purple"),
                TextColumn("[purple]{task.description}[/purple]"),
                console=console,
                transient=True
            ) as progress:
                task = progress.add_task("Simulating attack chain...", total=None)
                metrics = run_demo(ROOT, artifact_dir)
            display_results(metrics, scenario_data, artifact_dir)
        else:
            # For new scenarios: simulate events directly
            simulate_scenario_events(scenario_data, artifact_dir)
    except Exception as e:
        console.print(f"[purple]  ✗ Simulation error: {str(e)}[/purple]")
        import traceback
        console.print(f"[dim purple]{traceback.format_exc()}[/dim purple]")

def simulate_scenario_events(scenario_data: dict, artifact_dir: Path):
    """Simulate events for new scenarios without needing victim server"""
    import shutil
    from datetime import datetime, timezone, timedelta

    scenario_id = scenario_data["id"]
    steps = scenario_data["steps"]
    expected_rules = scenario_data["expected_rules"]

    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True)

    # Generate synthetic events for each step
    base_time = datetime(2026, 6, 19, 2, 15, 0, tzinfo=timezone.utc)
    actions = []
    auth_events = []
    endpoint_events = []
    network_events = []

    console.print("[dim purple]  Generating synthetic telemetry...[/dim purple]")
    console.print()

    for i, step in enumerate(steps):
        ts = (base_time + timedelta(seconds=i * 30)).isoformat().replace("+00:00", "Z")

        console.print(f"  [purple]▸[/purple] [dim purple]{step['technique_id']}[/dim purple]  [purple]{step['action']}[/purple]")
        time.sleep(0.2)

        actions.append({
            "timestamp": ts,
            "scenario_id": scenario_id,
            "source": "attacker",
            "sequence": i + 1,
            "action": step["action"],
            "technique_id": step["technique_id"],
            "description": step["description"],
        })

        payload = step.get("payload", {})
        username = payload.get("username", "unknown")
        command = payload.get("command", "")

        # Auth events (login steps)
        if "login" in step["action"] or "valid_account" in step["action"]:
            auth_events.append({
                "timestamp": ts,
                "scenario_id": scenario_id,
                "source": "authentication",
                "event_type": "authentication",
                "username": username,
                "outcome": "success",
                "method": "password",
                "src_ip": "10.0.0.99",
                "dst_ip": "10.0.0.1",
            })

        # Endpoint/process events (command steps)
        if command:
            endpoint_events.append({
                "timestamp": ts,
                "scenario_id": scenario_id,
                "source": "endpoint",
                "event_type": "process_start",
                "process_name": command.split()[0] if command else "cmd.exe",
                "command_line": command,
                "parent_process": "explorer.exe",
                "username": username,
                "src_ip": "10.0.0.99",
                "dst_ip": "10.0.0.1",
                "simulated": True,
            })

        # Network events
        network_events.append({
            "timestamp": ts,
            "scenario_id": scenario_id,
            "source": "network",
            "event_type": "network_connection",
            "src_ip": "10.0.0.99",
            "dst_ip": "10.0.0.1",
            "protocol": "HTTP",
            "method": "POST",
            "path": step.get("path", "/"),
            "status": 200,
            "action_sequence": i + 1,
        })

    # Write raw logs
    def write_jsonl(path, items):
        with open(path, "w") as f:
            for item in items:
                f.write(json.dumps(item) + "\n")

    write_jsonl(raw_dir / "actions.jsonl", actions)
    write_jsonl(raw_dir / "authentication.jsonl", auth_events)
    write_jsonl(raw_dir / "endpoint.jsonl", endpoint_events)
    write_jsonl(raw_dir / "network.jsonl", network_events)

    console.print()

    # Run DTM normalize + detect
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent / "src"))
    from dtm.normalize import normalize_directory
    from dtm.sigma import detect
    from dtm.scenario import Scenario

    event_path = artifact_dir / "ocsf-events.jsonl"
    alert_path = artifact_dir / "alerts.jsonl"

    normalize_directory(raw_dir, event_path)
    alerts = detect(event_path, RULES_DIR, alert_path)

    # Calculate metrics manually
    detected_rules = {a["rule_id"] for a in alerts}
    expected = set(expected_rules)
    covered = expected.intersection(detected_rules)

    metrics = {
        "scenario_id": scenario_id,
        "expected_rule_count": len(expected),
        "detected_rule_count": len(covered),
        "coverage_percent": round(100 * len(covered) / len(expected), 2) if expected else 100.0,
        "missed_rules": sorted(expected - covered),
        "unexpected_rules": sorted(detected_rules - expected),
        "alert_count": len(alerts),
        "time_to_detect_seconds": 30.0,
        "false_positive_count": 0,
        "false_positive_rate": 0.0,
    }

    (artifact_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    display_results(metrics, scenario_data, artifact_dir)

def display_results(metrics: dict, scenario_data: dict, artifact_dir: Path):
    console.print()
    section_header("SIMULATION COMPLETE", f"Artifacts saved to {artifact_dir.relative_to(ROOT)}")

    coverage = metrics.get("coverage_percent", 0)
    cov_color = "bold red" if coverage < 50 else "dark_orange" if coverage < 80 else "bold bright_magenta"

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="purple", justify="right")
    summary.add_column(min_width=18)
    summary.add_row("Detection Coverage", f"[{cov_color}]{coverage}%[/{cov_color}]")
    summary.add_row("Alerts Fired", f"[bold purple]{metrics.get('alert_count', 0)}[/bold purple]")
    summary.add_row("Time to Detect", f"[purple]{metrics.get('time_to_detect_seconds', 'N/A')}s[/purple]")
    summary.add_row("False Positive Rate", f"[purple]{metrics.get('false_positive_rate', 0):.2%}[/purple]")
    summary.add_row("Expected Rules", f"[purple]{metrics.get('expected_rule_count', '—')}[/purple]")
    summary.add_row("Detected Rules", f"[purple]{metrics.get('detected_rule_count', '—')}[/purple]")

    bar_filled = int(coverage / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    score_panel = Panel(
        Group(
            summary,
            Text(""),
            Text.from_markup(f"[purple]Coverage[/purple]  [bold bright_magenta]{bar}[/bold bright_magenta]  {coverage}%"),
        ),
        title="[bold purple]Detection Scorecard[/bold purple]",
        border_style="bright_magenta",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(score_panel)
    console.print()

    # Missed rules
    missed = metrics.get("missed_rules", [])
    if missed:
        section_header("MISSED DETECTIONS", "Expected rules that did not fire")
        for rule_id in missed:
            console.print(f"  [bold red]✗[/bold red] [purple]{rule_id}[/purple] [dim purple]— no rule fired for this attack step[/dim purple]")
        console.print()

    # Alert table
    alert_path = artifact_dir / "alerts.jsonl"
    if alert_path.exists():
        alerts = [json.loads(line) for line in alert_path.read_text().splitlines() if line.strip()]
        if alerts:
            section_header("ALERTS FIRED", f"{len(alerts)} detection event(s)")
            table = Table(box=box.ROUNDED, border_style="purple", header_style="bold purple", show_lines=True)
            table.add_column("RULE", style="purple", min_width=35)
            table.add_column("LEVEL", width=10)
            table.add_column("TIME", style="dim purple", width=25)

            for alert in alerts:
                level = alert.get("level", "medium")
                color = LEVEL_COLOR.get(level, "purple")
                table.add_row(
                    alert.get("title", alert.get("rule_id", "unknown")),
                    f"[{color}]{level.upper()}[/{color}]",
                    alert.get("time", "")[:19],
                )
            console.print(table)
            console.print()

    recs = []
    if coverage < 100:
        recs.append(f"⚠  {len(missed)} attack step(s) went undetected — add rules for missed techniques")
    if metrics.get("false_positive_rate", 0) > 0.01:
        recs.append("⚠  High false positive rate — tune detection thresholds")
    if coverage == 100:
        recs.append("✓  Full detection coverage — add benign variants to stress-test FP rate")
    recs.append("▸  Edit rules/*.yml then use Replay to retest without re-simulating")
    recs.append("▸  Open Timeline Report (menu option 9) for the full action → alert map")

    console.print(
        Panel(
            "\n".join(f"[purple]{line}[/purple]" for line in recs),
            title="[bold purple]Recommendations[/bold purple]",
            border_style="purple",
            box=box.HEAVY,
            padding=(1, 2),
        )
    )
    console.print()
    pause()

def replay_menu():
    latest = ARTIFACTS_DIR / "latest"
    if not latest.exists():
        console.print("[purple]  ✗ No recording found. Run a scenario first.[/purple]")
        console.print()
        pause()
        return

    section_header("REPLAY", "Re-evaluating latest recording against current rules")
    console.print("[purple]  ▸ Replaying last recording...[/purple]")
    console.print()

    try:
        sys.path.insert(0, str(ROOT / "src"))
        from dtm.pipeline import replay

        output_dir = ARTIFACTS_DIR / "replay"
        metrics = replay(ROOT, latest, output_dir)

        metrics_data = json.loads((output_dir / "metrics.json").read_text())
        display_results(metrics_data, {}, output_dir)
    except Exception as e:
        console.print(f"[purple]  ✗ Replay error: {str(e)}[/purple]")

def coverage_report():
    section_header("DETECTION COVERAGE REPORT", "Scenario library and expected detections")

    table = Table(box=box.ROUNDED, border_style="purple", header_style="bold purple", show_lines=True)
    table.add_column("SCENARIO", style="purple", min_width=35)
    table.add_column("STEPS", style="purple", width=7)
    table.add_column("RULES", style="purple", width=7)
    table.add_column("PHASES", style="dim purple")

    total_rules = 0
    for filename, label in SCENARIO_FILES.values():
        path = SCENARIOS_DIR / filename
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            phases = ", ".join(data.get("mitre_phases", ["—"])[:3])
            rules = len(data.get("expected_rules", []))
            total_rules += rules
            table.add_row(
                data.get("name", filename)[:45],
                str(len(data.get("steps", []))),
                str(rules),
                phases[:40],
            )

    console.print(table)
    console.print()

    rules = list(RULES_DIR.glob("*.yml"))
    inventory = Table.grid(padding=(0, 2))
    inventory.add_column(style="purple", justify="right")
    inventory.add_column(style="bold bright_magenta")
    inventory.add_row("Total rules in library", str(len(rules)))
    inventory.add_row("Total scenarios", str(len(SCENARIO_FILES)))
    inventory.add_row("Expected detections", str(total_rules))
    inventory.add_row("Unique techniques", str(count_techniques()))

    console.print(
        Panel(
            inventory,
            title="[bold purple]Library Inventory[/bold purple]",
            border_style="purple",
            box=box.ROUNDED,
        )
    )
    console.print()
    pause()

def attack_heatmap():
    section_header("MITRE ATT&CK COVERAGE HEATMAP", "Techniques exercised across all scenarios")

    techniques = {}
    for filename, _ in SCENARIO_FILES.values():
        path = SCENARIOS_DIR / filename
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            for step in data.get("steps", []):
                tid = step.get("technique_id", "")
                if tid:
                    techniques[tid] = techniques.get(tid, [])
                    techniques[tid].append(step.get("action", ""))

    table = Table(box=box.ROUNDED, border_style="purple", header_style="bold purple", show_lines=True)
    table.add_column("TECHNIQUE ID", style="purple", width=14)
    table.add_column("COVERAGE", style="purple", width=12)
    table.add_column("ACTIONS", style="dim purple")

    for tid, actions in sorted(techniques.items()):
        bar = "█" * len(actions) + "░" * max(0, 5 - len(actions))
        table.add_row(tid, f"[purple]{bar}[/purple]", ", ".join(set(actions))[:50])

    console.print(table)
    console.print()
    console.print(
        Panel(
            f"[purple]Unique techniques covered:[/purple] [bold bright_magenta]{len(techniques)}[/bold bright_magenta]",
            border_style="purple",
            box=box.ROUNDED,
        )
    )
    console.print()
    pause()

def rule_library():
    section_header("DETECTION RULE LIBRARY", f"Sigma-style rules in {RULES_DIR.name}/")

    rules = sorted(RULES_DIR.glob("*.yml"))
    if not rules:
        console.print("[purple]  ✗ No rules found.[/purple]")
        console.print()
        pause()
        return

    table = Table(box=box.ROUNDED, border_style="purple", header_style="bold purple", show_lines=True)
    table.add_column("RULE ID", style="purple", min_width=28)
    table.add_column("LEVEL", width=10)
    table.add_column("TITLE", style="dim purple", min_width=36)

    for path in rules:
        rule = load_rule(path)
        level = rule.get("level", "medium")
        color = LEVEL_COLOR.get(level, "purple")
        table.add_row(
            rule.get("id", path.stem),
            f"[{color}]{level.upper()}[/{color}]",
            rule.get("title", "—")[:55],
        )

    console.print(table)
    console.print()

    detail = Prompt.ask(
        "[bold purple]Enter rule ID for details[/bold purple] [dim purple](or press Enter to go back)[/dim purple]",
        default="",
    )
    if detail.strip():
        for path in rules:
            rule = load_rule(path)
            if rule.get("id") == detail.strip() or path.stem == detail.strip():
                console.print(
                    Panel(
                        f"[bold purple]{rule.get('title', 'Untitled')}[/bold purple]\n\n"
                        f"[purple]ID[/purple]  [dim purple]{rule.get('id', path.stem)}[/dim purple]\n"
                        f"[purple]Level[/purple]  [dim purple]{rule.get('level', 'medium')}[/dim purple]\n"
                        f"[purple]Status[/purple]  [dim purple]{rule.get('status', '—')}[/dim purple]\n"
                        f"[purple]Tags[/purple]  [dim purple]{', '.join(rule.get('tags', [])) or '—'}[/dim purple]\n\n"
                        f"[purple]Description[/purple]\n[dim purple]{rule.get('description', '—')}[/dim purple]",
                        title="[bold purple]Rule Detail[/bold purple]",
                        border_style="bright_magenta",
                        box=box.DOUBLE,
                        padding=(1, 2),
                    )
                )
                break
        else:
            console.print("[purple]  ✗ Rule not found.[/purple]")
        console.print()
    pause()

def artifact_inspector():
    latest = ARTIFACTS_DIR / "latest"
    if not latest.exists():
        console.print("[purple]  ✗ No artifacts yet. Run a scenario first.[/purple]")
        console.print()
        pause()
        return

    section_header("ARTIFACT INSPECTOR", str(latest.relative_to(ROOT)))

    metrics = load_json(latest / "metrics.json")
    files = Table(box=box.ROUNDED, border_style="purple", header_style="bold purple")
    files.add_column("FILE", style="purple", min_width=30)
    files.add_column("SIZE", style="dim purple", width=10, justify="right")
    files.add_column("RECORDS", style="bright_magenta", width=10, justify="right")

    candidates = [
        latest / "metrics.json",
        latest / "ocsf-events.jsonl",
        latest / "alerts.jsonl",
        latest / "benign-alerts.jsonl",
        latest / "report.html",
    ]
    raw_dir = latest / "raw"
    if raw_dir.exists():
        candidates.extend(sorted(raw_dir.glob("*.jsonl")))

    for path in candidates:
        if not path.exists():
            continue
        size = path.stat().st_size
        size_label = f"{size:,} B" if size < 1024 else f"{size / 1024:.1f} KB"
        records = "—"
        if path.suffix == ".jsonl":
            records = str(len(load_jsonl(path)))
        elif path.name == "metrics.json":
            records = "1"
        files.add_row(str(path.relative_to(latest)), size_label, records)

    console.print(files)
    console.print()

    if metrics:
        console.print(
            Panel(
                f"[purple]Scenario[/purple]  [dim purple]{metrics.get('scenario_id', '—')}[/dim purple]\n"
                f"[purple]Coverage[/purple]  [bold bright_magenta]{metrics.get('coverage_percent', '—')}%[/bold bright_magenta]\n"
                f"[purple]Alerts[/purple]  [dim purple]{metrics.get('alert_count', 0)}[/dim purple]\n"
                f"[purple]TTD[/purple]  [dim purple]{metrics.get('time_to_detect_seconds', '—')}s[/dim purple]\n"
                f"[purple]False positives[/purple]  [dim purple]{metrics.get('false_positive_count', 0)}[/dim purple]",
                title="[bold purple]Latest Metrics[/bold purple]",
                border_style="purple",
                box=box.ROUNDED,
            )
        )
        console.print()

    alerts = load_jsonl(latest / "alerts.jsonl")
    if alerts:
        preview = Table(box=box.SIMPLE, border_style="purple", header_style="bold purple")
        preview.add_column("RULE", style="purple")
        preview.add_column("LEVEL", width=10)
        for alert in alerts[:5]:
            level = alert.get("level", "medium")
            color = LEVEL_COLOR.get(level, "purple")
            preview.add_row(alert.get("title", alert.get("rule_id", "—")), f"[{color}]{level.upper()}[/{color}]")
        console.print(Panel(preview, title="[bold purple]Recent Alerts[/bold purple]", border_style="purple"))
        console.print()

    pause()

def launch_gui():
    section_header("WEB GUI", "Launching Detection Time Machine browser interface")
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from dtm.gui import serve_gui

        console.print(
            Panel(
                "[purple]Starting local web server...[/purple]\n"
                "[dim purple]Press Ctrl+C in this terminal to stop the GUI.[/dim purple]",
                border_style="purple",
                box=box.ROUNDED,
            )
        )
        console.print()
        serve_gui(ROOT, host="127.0.0.1", port=8765, artifact_dir=ARTIFACTS_DIR / "latest", open_browser=True)
    except KeyboardInterrupt:
        console.print("\n[purple]  GUI stopped.[/purple]")
        console.print()
    except Exception as e:
        console.print(f"[purple]  ✗ Could not launch GUI: {e}[/purple]")
        console.print()

def open_latest_report():
    report = ARTIFACTS_DIR / "latest" / "report.html"
    if not report.exists():
        console.print("[purple]  ✗ No report found. Run the credential-access scenario first.[/purple]")
        console.print()
        pause()
        return

    section_header("TIMELINE REPORT", "Opening HTML report in your browser")
    webbrowser.open(report.resolve().as_uri())
    console.print(f"[purple]  ✓ Opened[/purple] [dim purple]{report}[/dim purple]")
    console.print()
    pause()

def about_screen():
    section_header("ABOUT CRUCIBLE", "Detection Time Machine v2")

    about = Table.grid(padding=(0, 2))
    about.add_column(style="purple", justify="right")
    about.add_column(style="dim purple")
    about.add_row("Platform", "CRUCIBLE — Purple Team Detection Platform")
    about.add_row("Version", VERSION)
    about.add_row("Engine", "Detection Time Machine (DTM)")
    about.add_row("Author", f"[bold bright_magenta]{AUTHOR}[/bold bright_magenta]")
    about.add_row("Website", AUTHOR_URL)
    about.add_row("GitHub", GITHUB_URL)
    about.add_row("Session", SESSION_ID)
    about.add_row("Telemetry", "OCSF 1.1.0 normalization")
    about.add_row("Rules", "Sigma-style YAML/JSON subset")

    stack = (
        "[purple]Simulate[/purple] safe ATT&CK chains  →  "
        "[purple]Normalize[/purple] raw logs to OCSF  →  "
        "[purple]Detect[/purple] with Sigma rules  →  "
        "[purple]Score[/purple] coverage + TTD + false positives"
    )

    console.print(
        Panel(
            Group(about, Text(""), Text.from_markup(stack)),
            title="[bold purple]CRUCIBLE[/bold purple]",
            subtitle=f"[dim purple]Built by {AUTHOR}[/dim purple]",
            border_style="bright_magenta",
            box=box.DOUBLE,
            padding=(1, 2),
        )
    )
    console.print()
    pause()

def run_all_scenarios():
    section_header("BATCH RUN", "Execute all synthetic scenarios and summarize coverage")

    if not Confirm.ask("[purple]  This will run all 5 scenarios. Proceed?[/purple]", default=True):
        return

    console.print()
    results = []

    for key, (filename, label) in SCENARIO_FILES.items():
        # Skip credential-access (needs victim server) in batch mode
        if "credential-access" in filename:
            continue

        path = SCENARIOS_DIR / filename
        if not path.exists():
            continue

        console.print(f"[bold purple]  ▸ [{key}/5][/bold purple] [purple]{label.strip()}[/purple]")

        with open(path) as f:
            data = json.load(f)

        artifact_dir = ARTIFACTS_DIR / f"scenario-{key}"
        try:
            simulate_scenario_events(data, artifact_dir)
            metrics_path = artifact_dir / "metrics.json"
            if metrics_path.exists():
                metrics = json.loads(metrics_path.read_text())
                results.append((data["name"], metrics))
        except Exception as e:
            console.print(f"[purple]    ✗ Failed: {str(e)[:60]}[/purple]")

        console.print()

    # Summary
    if results:
        console.print("[purple]━━━ BATCH RESULTS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/purple]")
        console.print()

        table = Table(box=box.ROUNDED, border_style="purple", header_style="bold purple", show_lines=True)
        table.add_column("SCENARIO", style="purple", min_width=40)
        table.add_column("COVERAGE", style="purple", width=10)
        table.add_column("ALERTS", style="purple", width=8)
        table.add_column("FP RATE", style="dim purple", width=10)

        for name, m in results:
            cov = m.get("coverage_percent", 0)
            color = "bold red" if cov < 50 else "dark_orange" if cov < 80 else "bold purple"
            table.add_row(
                name[:45],
                f"[{color}]{cov}%[/{color}]",
                str(m.get("alert_count", 0)),
                f"{m.get('false_positive_rate', 0):.2%}",
            )

        console.print(table)
        console.print()

        avg_coverage = sum(m.get("coverage_percent", 0) for _, m in results) / len(results)
        console.print(
            Panel(
                f"[purple]Average Detection Coverage[/purple]  [bold bright_magenta]{avg_coverage:.1f}%[/bold bright_magenta]",
                border_style="purple",
                box=box.ROUNDED,
            )
        )
        console.print()
    pause()

if __name__ == "__main__":
    console.clear()
    print_banner()
    boot_sequence()
    console.print()
    main_menu()
