from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .io import read_jsonl


def build_timeline(raw_dir: Path, event_path: Path, alert_path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for action in read_jsonl(raw_dir / "actions.jsonl"):
        items.append(
            {
                "time": action["timestamp"],
                "kind": "action",
                "title": f"{action['action']} ({action['technique_id']})",
                "detail": action["description"],
            }
        )
    for event in read_jsonl(event_path):
        items.append(
            {
                "time": event["time"],
                "kind": "telemetry",
                "title": f"{event['activity_name']} / OCSF {event['class_uid']}",
                "detail": event["metadata"]["uid"],
            }
        )
    for alert in read_jsonl(alert_path):
        items.append(
            {
                "time": alert["time"],
                "kind": "alert",
                "title": alert["title"],
                "detail": f"{alert['rule_id']} · {', '.join(alert['tags'])}",
            }
        )
    return sorted(items, key=lambda item: (item["time"], item["kind"]))


def render_report(
    raw_dir: Path,
    event_path: Path,
    alert_path: Path,
    metrics: dict[str, Any],
    output_path: Path,
) -> None:
    timeline = build_timeline(raw_dir, event_path, alert_path)
    rows = "\n".join(
        f"""<li class="{html.escape(item['kind'])}">
          <time>{html.escape(item['time'])}</time>
          <div><strong>{html.escape(item['title'])}</strong><small>{html.escape(item['detail'])}</small></div>
        </li>"""
        for item in timeline
    )
    metric_cards = "\n".join(
        f"<div class='metric'><span>{html.escape(key.replace('_', ' ').title())}</span>"
        f"<strong>{html.escape(str(value))}</strong></div>"
        for key, value in metrics.items()
        if key in {"coverage_percent", "alert_count", "time_to_detect_seconds", "false_positive_rate"}
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Detection Time Machine Report</title>
<style>
:root{{--ink:#eef4ff;--muted:#8ea0ba;--panel:#111a2a;--line:#26364e;--action:#f2b84b;--telemetry:#55c2ff;--alert:#ff637d}}
*{{box-sizing:border-box}} body{{margin:0;background:#08101d;color:var(--ink);font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}}
main{{max-width:1050px;margin:auto;padding:48px 24px}} h1{{font-size:clamp(30px,6vw,64px);letter-spacing:-.06em;margin:0}}
.eyebrow{{color:#55c2ff;text-transform:uppercase;letter-spacing:.16em}} .subtitle{{color:var(--muted);max-width:700px}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:32px 0}}
.metric{{background:var(--panel);border:1px solid var(--line);padding:18px}} .metric span,.metric strong{{display:block}} .metric span{{color:var(--muted);font-size:12px}} .metric strong{{font-size:25px;margin-top:7px}}
ol{{list-style:none;padding:0;margin:34px 0}} li{{display:grid;grid-template-columns:210px 12px 1fr;gap:18px;position:relative;padding-bottom:25px}}
li:before{{content:"";grid-column:2;width:10px;height:10px;border-radius:50%;margin-top:7px;background:currentColor;z-index:1}}
li:after{{content:"";position:absolute;left:215px;top:17px;bottom:-7px;width:1px;background:var(--line)}} li:last-child:after{{display:none}}
time{{color:var(--muted);font-size:12px;padding-top:3px}} small{{display:block;color:var(--muted);margin-top:4px}}
.action{{color:var(--action)}} .telemetry{{color:var(--telemetry)}} .alert{{color:var(--alert)}} li div{{color:var(--ink)}}
pre{{white-space:pre-wrap;background:var(--panel);border:1px solid var(--line);padding:18px;color:var(--muted)}}
@media(max-width:650px){{li{{grid-template-columns:12px 1fr}}li time{{grid-column:2}}li:before{{grid-column:1;grid-row:1/3}}li:after{{left:5px}}}}
</style>
</head>
<body><main>
<p class="eyebrow">Reproducible detection experiment</p>
<h1>Detection Time Machine</h1>
<p class="subtitle">Attack actions, normalized OCSF telemetry, and Sigma alerts on one deterministic timeline.</p>
<section class="metrics">{metric_cards}</section>
<h2>Attack → telemetry → alert</h2>
<ol>{rows}</ol>
<h2>Experiment record</h2>
<pre>{html.escape(json.dumps(metrics, indent=2, sort_keys=True))}</pre>
</main></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")

