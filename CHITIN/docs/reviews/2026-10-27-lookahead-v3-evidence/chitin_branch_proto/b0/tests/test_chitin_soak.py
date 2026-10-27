"""Endurance evidence must exclude intervals containing inactive transitions."""

import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "CHITIN" / "battle_evolution.py"
SPEC = importlib.util.spec_from_file_location("chitin_soak_test", SOURCE)
chitin = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = chitin
SPEC.loader.exec_module(chitin)


class SoakAccountingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = 100.0
        clock = patch.object(chitin.time, "perf_counter", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        self.root = SimpleNamespace(
            after=lambda *args: None,
            state=lambda: "normal",
            winfo_ismapped=lambda: True,
            title=lambda *args: None,
        )
        self.app = object.__new__(chitin.BattleApp)
        self.app.root = self.root
        self.app.world = SimpleNamespace(
            tick=0,
            seed=42,
            max_agents=60,
            episode=1,
            agents=[],
            factions=[],
            last_ledger_error=0.0,
            snapshot=lambda: {},
        )
        self.app.tk = SimpleNamespace(TkVersion=8.6)
        self.app.ink = SimpleNamespace(pool={})
        self.app.last_frame_ms = 1.0
        self.app.fps = 20.0
        self.app.running = True
        self.app.closed = False
        self.app.error = None
        self.app._activity_revision = 0
        self.app._motion = lambda *args: None
        self.app.draw = lambda: None
        self.recorder = chitin.SoakRecorder(
            self.app, 1, Path(self.directory.name) / "report.json"
        )

    def probe(self, duration=1.0, advance=True):
        self.now += duration
        if advance:
            self.app.world.tick += 1
        self.recorder._probe()

    def toggle(self):
        self.app._key(SimpleNamespace(keysym="space"))

    def test_pause_resume_between_probes_is_excluded(self):
        self.now += 0.1
        self.toggle()
        self.now += 0.7
        self.toggle()
        self.probe(0.2)
        self.assertEqual(self.recorder.active, 0.0)
        self.probe()
        self.assertAlmostEqual(self.recorder.active, 1.0)

    def test_unmap_remap_between_probes_is_excluded(self):
        self.app._visibility(SimpleNamespace(widget=self.root, type="18"))
        self.app._visibility(SimpleNamespace(widget=self.root, type="19"))
        self.probe()
        self.assertEqual(self.recorder.active, 0.0)

    def test_mixed_interval_cannot_complete(self):
        self.recorder.target = 0.5
        self.toggle()
        self.toggle()
        self.probe()
        self.assertFalse(self.recorder.finished)
        self.probe()
        self.assertTrue(self.recorder.finished)

    def test_continuous_running_is_credited_once(self):
        self.probe()
        self.probe()
        self.assertEqual(self.recorder.active, 2.0)

    def test_paused_stalled_and_long_gap_are_excluded(self):
        self.toggle()
        self.probe()
        self.toggle()
        self.probe(4.0)
        self.probe(1.0, advance=False)
        self.assertEqual(self.recorder.active, 0.0)

    def test_unmapped_endpoint_is_excluded(self):
        self.root.winfo_ismapped = lambda: False
        self.probe()
        self.assertEqual(self.recorder.active, 0.0)

    def test_error_cannot_complete(self):
        self.recorder.target = 0.5
        self.app.error = "test failure"
        self.probe()
        self.assertTrue(self.recorder.finished)
        import json

        self.assertEqual(json.loads(self.recorder.path.read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
