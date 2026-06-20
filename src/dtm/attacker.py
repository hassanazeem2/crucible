from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .io import append_jsonl
from .scenario import Scenario


def _request(url: str, payload: dict[str, object]) -> int:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "dtm-attacker/0.1"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def wait_for_victim(base_url: str, attempts: int = 30) -> None:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1):
                return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError(f"victim did not become ready at {base_url}")


def run_scenario(
    scenario: Scenario,
    base_url: str,
    raw_dir: Path,
    now: Callable[[], str],
) -> None:
    wait_for_victim(base_url)
    for index, step in enumerate(scenario.steps, 1):
        action_time = now()
        append_jsonl(
            raw_dir / "actions.jsonl",
            {
                "timestamp": action_time,
                "scenario_id": scenario.id,
                "source": "attacker",
                "sequence": index,
                "action": step["action"],
                "technique_id": step["technique_id"],
                "description": step["description"],
            },
        )
        status = _request(f"{base_url}{step['path']}", step["payload"])
        append_jsonl(
            raw_dir / "network.jsonl",
            {
                "timestamp": now(),
                "scenario_id": scenario.id,
                "source": "network",
                "event_type": "network_connection",
                "src_ip": "attacker",
                "dst_ip": "victim",
                "protocol": "HTTP",
                "method": "POST",
                "path": step["path"],
                "status": status,
                "action_sequence": index,
            },
        )

