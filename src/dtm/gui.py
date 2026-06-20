from __future__ import annotations

import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .io import read_jsonl
from .pipeline import replay, run_demo, validate_recording
from .report import build_timeline


DEFAULT_ARTIFACT_DIR = Path("artifacts/latest")
DEFAULT_REPLAY_DIR = Path("artifacts/replay")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    return value if isinstance(value, dict) else {}


def _load_preview(path: Path, limit: int = 25) -> list[dict[str, Any]]:
    return list(read_jsonl(path))[:limit]


def recording_state(root: Path, artifact_dir: Path) -> dict[str, Any]:
    raw_dir = artifact_dir / "raw"
    event_path = artifact_dir / "ocsf-events.jsonl"
    alert_path = artifact_dir / "alerts.jsonl"
    metrics = _load_json(artifact_dir / "metrics.json")
    events = _load_preview(event_path)
    alerts = _load_preview(alert_path)
    actions = _load_preview(raw_dir / "actions.jsonl")
    timeline: list[dict[str, Any]] = []
    if raw_dir.exists() and event_path.exists() and alert_path.exists():
        timeline = build_timeline(raw_dir, event_path, alert_path)

    return {
        "root": str(root),
        "artifact_dir": str(artifact_dir),
        "has_recording": bool(metrics),
        "report_url": "/report" if (artifact_dir / "report.html").exists() else None,
        "metrics": metrics,
        "counts": {
            "actions": len(actions),
            "events": sum(1 for _ in read_jsonl(event_path)),
            "alerts": sum(1 for _ in read_jsonl(alert_path)),
        },
        "actions": actions,
        "events": events,
        "alerts": alerts,
        "timeline": timeline,
    }


def _resolve_under_root(root: Path, value: str | None, default: Path) -> Path:
    candidate = Path(value or default)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


class GuiServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], root: Path, artifact_dir: Path) -> None:
        super().__init__(address, GuiRequestHandler)
        self.root = root
        self.artifact_dir = artifact_dir
        self.lock = threading.Lock()


def _bind_gui_server(host: str, port: int, root: Path, artifact_dir: Path) -> tuple[GuiServer, int]:
    last_error: OSError | None = None
    for offset in range(20):
        candidate = port + offset
        try:
            server = GuiServer((host, candidate), root, artifact_dir)
            if offset:
                print(
                    f"Port {port} is busy; using http://{host}:{candidate} instead.",
                    flush=True,
                )
            return server, candidate
        except OSError as exc:
            if exc.errno not in {48, 98}:  # macOS / Linux: address already in use
                raise
            last_error = exc
    raise RuntimeError(
        f"Could not bind GUI server on {host}:{port}-{port + 19}. "
        "Stop the other Detection Time Machine GUI process and try again."
    ) from last_error


class GuiRequestHandler(BaseHTTPRequestHandler):
    server: GuiServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_text(INDEX_HTML, "text/html; charset=utf-8")
        elif path == "/api/state":
            self._send_json(recording_state(self.server.root, self.server.artifact_dir))
        elif path == "/report":
            report_path = self.server.artifact_dir / "report.html"
            if report_path.exists():
                self._send_text(report_path.read_text(encoding="utf-8"), "text/html; charset=utf-8")
            else:
                self._send_json({"error": "Run the demo first to generate report.html"}, HTTPStatus.NOT_FOUND)
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/demo":
            self._run_demo()
        elif path == "/api/replay":
            self._run_replay()
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def _run_demo(self) -> None:
        with self.server.lock:
            metrics = run_demo(self.server.root, self.server.artifact_dir)
        self._send_json({"ok": True, "metrics": metrics, "state": recording_state(self.server.root, self.server.artifact_dir)})

    def _run_replay(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        payload = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(payload or "{}")
        recording_dir = _resolve_under_root(self.server.root, data.get("recording"), self.server.artifact_dir)
        output_dir = _resolve_under_root(self.server.root, data.get("output"), DEFAULT_REPLAY_DIR)
        with self.server.lock:
            validate_recording(recording_dir)
            metrics = replay(self.server.root, recording_dir, output_dir)
        self._send_json({"ok": True, "metrics": metrics, "output_dir": str(output_dir)})

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, payload: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_gui(
    root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    artifact_dir: Path | None = None,
    open_browser: bool = True,
) -> None:
    artifact_path = (artifact_dir or root / DEFAULT_ARTIFACT_DIR).resolve()
    print("Starting Detection Time Machine GUI...", flush=True)
    server, bound_port = _bind_gui_server(host, port, root.resolve(), artifact_path)
    url = f"http://{host}:{bound_port}"
    print(f"Detection Time Machine GUI running at {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Detection Time Machine GUI</title>
<style>
:root{color-scheme:dark;--bg:#020304;--ink:#f5f7fb;--muted:#8d96a6;--soft:#c6cedb;--panel:#080a0d;--panel2:#0d1015;--panel3:#11151c;--line:#202733;--line2:#303846;--blue:#7dd3fc;--gold:#f8d889;--red:#fb7185;--green:#86efac;--shadow:0 28px 90px rgba(0,0,0,.58);--ease:cubic-bezier(.16,1,.3,1)}
*{box-sizing:border-box}html{background:#000}body{margin:0;min-height:100vh;background:radial-gradient(circle at 20% -10%,rgba(125,211,252,.14),transparent 32rem),radial-gradient(circle at 85% 10%,rgba(248,216,137,.10),transparent 28rem),linear-gradient(180deg,#050607 0%,#000 52%,#030405 100%);color:var(--ink);font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:72px 72px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.7),transparent 70%);animation:grid-drift 22s linear infinite}
main{max-width:1240px;margin:auto;padding:42px 22px 70px}.shell{position:relative;border:1px solid rgba(255,255,255,.08);border-radius:34px;background:linear-gradient(180deg,rgba(255,255,255,.065),rgba(255,255,255,.02));box-shadow:var(--shadow);overflow:hidden;animation:stage-in .8s var(--ease) both}.shell:before{content:"";position:absolute;inset:-1px;background:linear-gradient(105deg,transparent 0%,rgba(125,211,252,.18) 34%,rgba(248,216,137,.14) 50%,transparent 68%);transform:translateX(-70%);animation:sheen 8s var(--ease) infinite;pointer-events:none}.hero{display:grid;gap:24px;grid-template-columns:1fr auto;align-items:end;padding:34px;border-bottom:1px solid rgba(255,255,255,.08);background:linear-gradient(135deg,rgba(255,255,255,.08),rgba(255,255,255,.015))}
h1{font-size:clamp(42px,7vw,92px);line-height:.86;letter-spacing:-.085em;margin:0;max-width:760px;animation:rise .72s var(--ease) .08s both}.eyebrow{display:inline-flex;align-items:center;gap:10px;color:var(--gold);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.18em;margin:0 0 18px;animation:rise .64s var(--ease) both}.eyebrow:before{content:"";width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 22px var(--green);animation:pulse 2.6s ease-in-out infinite}.subtitle{max-width:760px;color:var(--soft);font-size:17px;margin:18px 0 0;animation:rise .72s var(--ease) .16s both}.actions{display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end;animation:rise .72s var(--ease) .22s both}
button,a.button{appearance:none;border:1px solid rgba(255,255,255,.12);background:linear-gradient(180deg,#f7fafc,#b9c4d2);color:#020304;padding:13px 17px;border-radius:999px;font-weight:850;cursor:pointer;text-decoration:none;display:inline-flex;gap:8px;align-items:center;box-shadow:0 14px 36px rgba(255,255,255,.08);transition:transform .22s var(--ease),border-color .22s ease,background .22s ease,box-shadow .22s ease}button:hover,a.button:hover{transform:translateY(-2px) scale(1.015);border-color:rgba(255,255,255,.32);box-shadow:0 18px 46px rgba(255,255,255,.12)}button:active,a.button:active{transform:translateY(0) scale(.985)}button.secondary,a.secondary{background:rgba(255,255,255,.045);color:var(--ink);box-shadow:none}button:disabled{opacity:.48;cursor:not-allowed;transform:none}.is-loading button:not(:disabled){animation:soft-breathe 1.8s ease-in-out infinite}
.content{padding:24px 24px 30px}.status{display:flex;justify-content:space-between;gap:12px;margin:0 0 18px;color:var(--muted);font-size:13px;animation:rise .7s var(--ease) .3s both}.status strong{color:var(--ink)}.is-loading .status strong{color:var(--blue);animation:pulse 1.2s ease-in-out infinite}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card,.panel{position:relative;background:linear-gradient(180deg,rgba(255,255,255,.07),rgba(255,255,255,.025));border:1px solid rgba(255,255,255,.09);border-radius:24px;box-shadow:0 18px 52px rgba(0,0,0,.28);overflow:hidden;transition:transform .28s var(--ease),border-color .28s ease,box-shadow .28s ease}.card:hover,.panel:hover{transform:translateY(-3px);border-color:rgba(255,255,255,.16);box-shadow:0 24px 70px rgba(0,0,0,.38)}.card:after,.panel:after{content:"";position:absolute;inset:0;pointer-events:none;border-radius:inherit;box-shadow:inset 0 1px rgba(255,255,255,.08)}
.metric{padding:19px;animation:rise .62s var(--ease) both}.metric:nth-child(1){animation-delay:.34s}.metric:nth-child(2){animation-delay:.4s}.metric:nth-child(3){animation-delay:.46s}.metric:nth-child(4){animation-delay:.52s}.metric span{display:block;color:var(--muted);font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.12em}.metric strong{display:block;font-size:34px;letter-spacing:-.04em;margin-top:8px;transition:filter .25s ease,text-shadow .25s ease}.metric:hover strong{filter:brightness(1.15);text-shadow:0 0 28px currentColor}.metric small{display:block;color:var(--muted);margin-top:6px}.ok{color:var(--green)}.warn{color:var(--gold)}.bad{color:var(--red)}
.layout{display:grid;grid-template-columns:1.08fr .92fr;gap:16px;margin-top:16px}.panel{padding:0;animation:rise .72s var(--ease) both}.layout:nth-of-type(3) .panel{animation-delay:.58s}.layout:nth-of-type(4) .panel{animation-delay:.66s}.panel-head{display:flex;align-items:end;justify-content:space-between;gap:14px;padding:20px 20px 14px;border-bottom:1px solid rgba(255,255,255,.08)}.panel h2{margin:0;font-size:16px;letter-spacing:-.02em}.panel .hint{margin:2px 0 0;color:var(--muted);font-size:12px}.panel-body{padding:16px 20px 20px}
.timeline{display:grid;gap:0}.item{display:grid;grid-template-columns:120px 1fr;gap:16px;position:relative;padding:14px 0;border-top:1px solid rgba(255,255,255,.07);animation:slide-in .48s var(--ease) both;animation-delay:calc(var(--i,0) * 34ms)}.item:first-child{border-top:0;padding-top:0}.time{color:var(--muted);font:12px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace}.item-main{padding-left:18px;border-left:1px solid var(--line2);transition:transform .2s var(--ease),border-color .2s ease}.item:hover .item-main{transform:translateX(3px);border-color:currentColor}.item-main:before{content:"";position:absolute;left:127px;top:20px;width:9px;height:9px;border-radius:50%;background:currentColor;box-shadow:0 0 20px currentColor;animation:pulse 2.8s ease-in-out infinite}.pill{display:inline-block;font-size:10px;font-weight:850;letter-spacing:.12em;text-transform:uppercase;border:1px solid currentColor;border-radius:999px;padding:3px 8px;margin-bottom:7px;background:rgba(255,255,255,.035)}.action{color:var(--gold)}.telemetry{color:var(--blue)}.alert{color:var(--red)}small{color:var(--muted)}
.table-wrap{overflow:auto;border:1px solid rgba(255,255,255,.075);border-radius:16px;background:rgba(0,0,0,.18);animation:fade-in .42s ease both}table{width:100%;border-collapse:collapse;min-width:560px}th,td{text-align:left;padding:12px 13px;border-top:1px solid rgba(255,255,255,.07);vertical-align:top}tr{transition:background .18s ease,transform .18s var(--ease)}tbody tr:hover{background:rgba(255,255,255,.045);transform:translateX(2px)}tr:first-child td{border-top:0}th{color:var(--muted);font-size:11px;font-weight:850;text-transform:uppercase;letter-spacing:.11em;background:rgba(255,255,255,.035)}td{color:#e8edf5}code{color:var(--blue)}pre{white-space:pre-wrap;overflow:auto;background:#030405;border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:15px;max-height:344px;color:#d8dee9;animation:fade-in .42s ease both}
.empty{border:1px dashed rgba(255,255,255,.16);border-radius:22px;padding:30px;color:var(--muted);text-align:center;background:rgba(255,255,255,.025);animation:fade-in .36s ease both}.hidden{display:none}
@keyframes stage-in{from{opacity:0;transform:translateY(18px) scale(.985);filter:blur(8px)}to{opacity:1;transform:none;filter:none}}@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}@keyframes slide-in{from{opacity:0;transform:translateX(-12px)}to{opacity:1;transform:none}}@keyframes fade-in{from{opacity:0}to{opacity:1}}@keyframes pulse{0%,100%{opacity:.68;box-shadow:0 0 14px currentColor}50%{opacity:1;box-shadow:0 0 30px currentColor}}@keyframes grid-drift{from{background-position:0 0,0 0}to{background-position:72px 72px,72px 72px}}@keyframes sheen{0%,72%{transform:translateX(-72%);opacity:0}82%{opacity:1}100%{transform:translateX(72%);opacity:0}}@keyframes soft-breathe{0%,100%{box-shadow:0 0 0 rgba(125,211,252,0)}50%{box-shadow:0 0 26px rgba(125,211,252,.18)}}
@media(max-width:940px){.hero,.layout{grid-template-columns:1fr}.actions{justify-content:flex-start}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:590px){main{padding:16px 10px 40px}.hero,.content{padding:20px}.grid{grid-template-columns:1fr}.item{grid-template-columns:1fr}.item-main{padding-left:14px}.item-main:before{left:0}}@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation-duration:.001ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition:none!important}}
</style>
</head>
<body><main><div class="shell">
<header class="hero">
<div>
<p class="eyebrow">Local cyber range interface</p>
<h1>Detection Time Machine</h1>
<p class="subtitle">Run the safe attack simulation, inspect normalized OCSF telemetry, review Sigma alerts, and open the generated timeline report without using the command line.</p>
</div>
<div class="actions">
<button id="run-demo">Run Demo</button>
<button id="run-replay" class="secondary">Replay Latest</button>
<a id="report-link" class="button secondary hidden" href="/report" target="_blank" rel="noreferrer">Open Report</a>
</div>
</header>
<div class="content">
<p id="status" class="status"><span>Loading current recording...</span><strong>Local only</strong></p>
<section id="empty" class="empty hidden">No recording found yet. Click <strong>Run Demo</strong> to generate artifacts and populate the GUI.</section>
<section class="grid" id="metrics"></section>
<section class="layout">
<div class="panel"><div class="panel-head"><div><h2>Detection Timeline</h2><p class="hint">Actions, telemetry, and alerts in sequence.</p></div></div><div class="panel-body"><div id="timeline" class="timeline"></div></div></div>
<div class="panel"><div class="panel-head"><div><h2>Alerts</h2><p class="hint">Sigma detections generated from normalized events.</p></div></div><div class="panel-body"><div id="alerts"></div></div></div>
</section>
<section class="layout">
<div class="panel"><div class="panel-head"><div><h2>Telemetry Preview</h2><p class="hint">First normalized OCSF records from the latest run.</p></div></div><div class="panel-body"><div id="events"></div></div></div>
<div class="panel"><div class="panel-head"><div><h2>Metrics JSON</h2><p class="hint">Machine-readable experiment summary.</p></div></div><div class="panel-body"><pre id="json"></pre></div></div>
</section>
</div>
</div></main>
<script>
const statusEl = document.querySelector("#status");
const emptyEl = document.querySelector("#empty");
const metricEl = document.querySelector("#metrics");
const timelineEl = document.querySelector("#timeline");
const alertEl = document.querySelector("#alerts");
const eventEl = document.querySelector("#events");
const jsonEl = document.querySelector("#json");
const reportLink = document.querySelector("#report-link");
const demoButton = document.querySelector("#run-demo");
const replayButton = document.querySelector("#run-replay");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function metricClass(key, value) {
  if (key === "coverage_percent") return Number(value) === 100 ? "ok" : "warn";
  if (key === "false_positive_count" || key === "false_positive_rate") return Number(value) === 0 ? "ok" : "bad";
  return "";
}

function renderTable(rows, columns) {
  if (!rows.length) return '<div class="empty">Nothing to show yet.</div>';
  return `<div class="table-wrap"><table><thead><tr>${columns.map(([label]) => `<th>${escapeHtml(label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map(([, getter]) => `<td>${escapeHtml(getter(row))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function render(state) {
  emptyEl.classList.toggle("hidden", state.has_recording);
  reportLink.classList.toggle("hidden", !state.report_url);
  const metrics = state.metrics || {};
  const metricCards = [
    ["coverage_percent", "Expected rule coverage"],
    ["alert_count", "Detections produced"],
    ["time_to_detect_seconds", "Seconds to first alert"],
    ["false_positive_count", "Benign alerts"]
  ];
  metricEl.innerHTML = metricCards.map(([key, helper]) => `<article class="card metric"><span>${escapeHtml(key.replaceAll("_", " "))}</span><strong class="${metricClass(key, metrics[key])}">${escapeHtml(metrics[key] ?? "n/a")}</strong><small>${escapeHtml(helper)}</small></article>`).join("");
  timelineEl.innerHTML = state.timeline.length ? state.timeline.map((item, index) => `<div class="item ${escapeHtml(item.kind)}" style="--i:${index}"><div class="time">${escapeHtml(item.time)}</div><div class="item-main"><span class="pill">${escapeHtml(item.kind)}</span><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.detail)}</small></div></div>`).join("") : '<div class="empty">Run the demo to build the action, telemetry, and alert timeline.</div>';
  alertEl.innerHTML = renderTable(state.alerts, [["Time", (row) => row.time], ["Rule", (row) => row.rule_id], ["Level", (row) => row.level], ["Title", (row) => row.title]]);
  eventEl.innerHTML = renderTable(state.events, [["Time", (row) => row.time], ["Activity", (row) => row.activity_name], ["Class", (row) => row.class_uid], ["UID", (row) => row.metadata && row.metadata.uid]]);
  jsonEl.textContent = JSON.stringify(metrics, null, 2);
  statusEl.innerHTML = state.has_recording ? `<span>Showing <strong>${escapeHtml(state.artifact_dir)}</strong></span><strong>${escapeHtml(state.counts.alerts)} alerts</strong>` : "<span>No recording loaded.</span><strong>Ready</strong>";
}

async function loadState() {
  const response = await fetch("/api/state");
  render(await response.json());
}

async function postAction(url, label) {
  const buttons = [demoButton, replayButton];
  buttons.forEach((button) => button.disabled = true);
  document.body.classList.add("is-loading");
  statusEl.innerHTML = `<span>${escapeHtml(label)}</span><strong>Working</strong>`;
  try {
    const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed");
    if (data.state) render(data.state);
    statusEl.innerHTML = data.output_dir ? `<span>Replay complete: <strong>${escapeHtml(data.output_dir)}</strong></span><strong>Done</strong>` : "<span>Demo complete.</span><strong>Done</strong>";
    if (!data.state) await loadState();
  } catch (error) {
    statusEl.innerHTML = `<span>${escapeHtml(error.message)}</span><strong>Check logs</strong>`;
  } finally {
    document.body.classList.remove("is-loading");
    buttons.forEach((button) => button.disabled = false);
  }
}

demoButton.addEventListener("click", () => postAction("/api/demo", "Running deterministic demo..."));
replayButton.addEventListener("click", () => postAction("/api/replay", "Replaying latest recording..."));
loadState();
</script>
</body></html>
"""
