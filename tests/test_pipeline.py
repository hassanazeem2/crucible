from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dtm.gui import recording_state
from dtm.io import read_jsonl
from dtm.pipeline import replay, run_demo, validate_recording


ROOT = Path(__file__).resolve().parents[1]


class PipelineTest(unittest.TestCase):
    def test_demo_produces_complete_recording(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "recording"
            metrics = run_demo(ROOT, output)

            self.assertEqual(metrics["coverage_percent"], 100.0)
            self.assertEqual(metrics["false_positive_count"], 0)
            self.assertGreaterEqual(metrics["alert_count"], 3)
            self.assertIsNotNone(metrics["time_to_detect_seconds"])
            validate_recording(output)

            events = list(read_jsonl(output / "ocsf-events.jsonl"))
            self.assertEqual({event["class_uid"] for event in events}, {1007, 3002, 4001, 4002})
            self.assertTrue((output / "report.html").read_text().startswith("<!doctype html>"))

    def test_recording_can_be_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recording = Path(directory) / "recording"
            replay_output = Path(directory) / "replay"
            run_demo(ROOT, recording)
            metrics = replay(ROOT, recording, replay_output)

            self.assertEqual(metrics["coverage_percent"], 100.0)
            self.assertTrue((replay_output / "alerts.jsonl").exists())

    def test_metrics_file_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "recording"
            run_demo(ROOT, output)
            metrics = json.loads((output / "metrics.json").read_text())
            self.assertEqual(metrics["missed_rules"], [])

    def test_gui_state_summarizes_recording(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "recording"
            run_demo(ROOT, output)
            state = recording_state(ROOT, output)

            self.assertTrue(state["has_recording"])
            self.assertEqual(state["metrics"]["coverage_percent"], 100.0)
            self.assertEqual(state["counts"]["alerts"], state["metrics"]["alert_count"])
            self.assertGreaterEqual(len(state["timeline"]), state["counts"]["alerts"])
            self.assertEqual(state["report_url"], "/report")


if __name__ == "__main__":
    unittest.main()

