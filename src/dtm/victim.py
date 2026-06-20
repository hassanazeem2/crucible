from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from .io import append_jsonl


LAB_USER = "analyst"
LAB_PASSWORD = "time-machine"


def make_handler(raw_dir: Path, now: Callable[[], str], scenario_id: str):
    class VictimHandler(BaseHTTPRequestHandler):
        server_version = "DTMVictim/0.1"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _body(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            if not length:
                return {}
            return json.loads(self.rfile.read(length))

        def _event(self, stream: str, event: dict[str, object]) -> None:
            append_jsonl(
                raw_dir / f"{stream}.jsonl",
                {
                    "timestamp": now(),
                    "scenario_id": scenario_id,
                    "source": stream,
                    "src_ip": self.client_address[0],
                    "dst_ip": self.server.server_address[0],
                    **event,
                },
            )

        def _reply(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            self._event(
                "application",
                {
                    "event_type": "http_request",
                    "method": "GET",
                    "path": self.path,
                    "status": 200 if self.path == "/health" else 404,
                    "user_agent": self.headers.get("User-Agent", ""),
                },
            )
            if self.path == "/health":
                self._reply(200, {"status": "ok"})
            else:
                self._reply(404, {"error": "not found"})

        def do_POST(self) -> None:
            body = self._body()
            if self.path == "/login":
                user = str(body.get("username", ""))
                success = user == LAB_USER and body.get("password") == LAB_PASSWORD
                self._event(
                    "authentication",
                    {
                        "event_type": "authentication",
                        "username": user,
                        "outcome": "success" if success else "failure",
                        "method": "password",
                    },
                )
                self._reply(200 if success else 401, {"authenticated": success})
                return

            if self.path == "/admin/simulate-command":
                command = str(body.get("command", ""))
                self._event(
                    "application",
                    {
                        "event_type": "http_request",
                        "method": "POST",
                        "path": self.path,
                        "status": 200,
                        "username": str(body.get("username", "")),
                    },
                )
                self._event(
                    "endpoint",
                    {
                        "event_type": "process_start",
                        "process_name": "simulation-shell",
                        "command_line": command,
                        "parent_process": "dtm-victim",
                        "simulated": True,
                    },
                )
                self._reply(200, {"simulated": True, "output": "lab-only placeholder"})
                return

            self._reply(404, {"error": "not found"})

    return VictimHandler


def create_server(
    host: str,
    port: int,
    raw_dir: Path,
    now: Callable[[], str],
    scenario_id: str,
) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(raw_dir, now, scenario_id))

