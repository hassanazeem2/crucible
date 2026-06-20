# CRUCIBLE
### Purple Team Detection Platform (DTM v2)

> Simulate. Measure. Harden.

CRUCIBLE is a purple team detection platform built on top of Detection Time Machine. It simulates realistic attack chains, normalizes telemetry to OCSF, evaluates Sigma detection rules, and scores your detection coverage — all from an interactive red CLI.

---

## What's New vs Detection Time Machine

| Feature | DTM | CRUCIBLE |
|---|---|---|
| Scenarios | 1 (credential access) | 5 (ransomware, lateral movement, exfil, HIPAA) |
| CLI | Basic | Interactive red-themed menu |
| ATT&CK Heatmap | ✗ | ✓ |
| Batch scenario runner | ✗ | ✓ |
| Healthcare/HIPAA scenarios | ✗ | ✓ |
| Detection recommendations | ✗ | ✓ |

---

## Quick Start

```bash
pip install rich pyfiglet
pip install -e .

python crucible.py
```

## Scenarios

| # | Scenario | Techniques |
|---|---|---|
| 1 | Credential Access + Shell Execution | T1110, T1078, T1059 |
| 2 | Ransomware Kill Chain | T1566, T1087, T1486 |
| 3 | Lateral Movement via Pass-the-Hash | T1003, T1550, T1543 |
| 4 | Data Exfil via DNS Tunneling | T1005, T1048, T1071 |
| 5 | HIPAA Insider Threat — PHI Access | T1078, T1005, T1048 |

## Menu Options

```
[1] Run Attack Scenario       — pick a scenario, simulate, get scored
[2] Replay Last Recording     — retest with updated rules, no re-simulation
[3] Detection Coverage Report — see all scenarios + rule counts
[4] ATT&CK Coverage Heatmap   — visualize technique coverage
[5] Run All Scenarios         — batch run + summary table
```

## How It Works

1. Select an attack scenario
2. CRUCIBLE generates synthetic OCSF telemetry for each ATT&CK step
3. Sigma rules are evaluated against the telemetry
4. Detection coverage, time-to-detect, and false positive rate are scored
5. Missed detections and tuning recommendations are surfaced

## Adding Scenarios

Create a JSON file in `scenarios/`:

```json
{
  "id": "my-scenario-001",
  "name": "My Attack Scenario",
  "description": "What this simulates",
  "mitre_phases": ["Initial Access", "Execution"],
  "expected_rules": ["my-rule-id"],
  "steps": [
    {
      "action": "phishing_login",
      "technique_id": "T1566.001",
      "description": "What this step does",
      "path": "/login",
      "payload": {"username": "victim", "password": "stolen"}
    }
  ]
}
```

Add matching rules in `rules/` and run `python crucible.py`.

## Stack

- Python 3.11+
- `rich` — red-themed terminal UI
- `pyfiglet` — ASCII banner
- OCSF 1.1.0 telemetry normalization
- Sigma rule evaluation (subset)
- MITRE ATT&CK mapped scenarios

## Author

Hassan Azeem — [hazeem.org](https://hazeem.org) | [github.com/hassanazeem2](https://github.com/hassanazeem2)
