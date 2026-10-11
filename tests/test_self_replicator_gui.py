"""Native Tk smoke tests. Run on a desktop or Xvfb; no third-party packages.

    python -m unittest discover -s tests -v

These complement `python self_replicator.py --selftest` and skip if no display
is available. Screenshot tooling is deliberately not a runtime dependency.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import self_replicator as sr


class NativeInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.destroy()
        except (ImportError, RuntimeError) as error:
            raise unittest.SkipTest(str(error))
        except Exception as error:
            if type(error).__name__ == "TclError":
                raise unittest.SkipTest(f"No Tk display: {error}")
            raise

    def setUp(self):
        self.app = sr.App()
        self.app.running = False
        self.errors = []
        self.app.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.app.root.update()
        self.app.draw()
        self.app.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def test_pending_settings_reset_pause_and_single_step(self):
        app = self.app
        app.pending["resources"].set(500)
        self.assertEqual(app.world.cfg.resources, 1800)
        self.assertIn("Pending", app.dirty.get())
        app.new_run()
        self.assertEqual(app.world.cfg.resources, 500)
        self.assertEqual(app.world.tick, 0)
        app.step_once()
        self.assertEqual(app.world.tick, 1)
        self.assertFalse(app.running)
        app.toggle()
        self.assertTrue(app.running)
        app.toggle()
        self.assertFalse(app.running)

    def test_canvas_selection_and_all_mechanisms_at_minimum_size(self):
        app = self.app
        for _ in range(80):
            app.world.step()
        app.root.geometry("1120x790")
        app.root.update()
        app.draw()
        agent = app.world.agents[-1]
        ax, ay, aw, ah = app.view.arena
        app.canvas.event_generate("<Button-1>", x=int(ax+agent.x/sr.COLS*aw), y=int(ay+agent.y/sr.ROWS*ah))
        app.root.update()
        self.assertIsNotNone(app.uid)
        selected = app.view.selected(app.world, app.uid)
        self.assertIsNotNone(selected)
        self.assertAlmostEqual(selected.x, agent.x, delta=.8)
        app.set_tab("Mechanisms")
        for i in range(8):
            app.concept = i
            app.draw()
            app.root.update()
            self.assertGreater(len(app.canvas.find_all()), 20)

    def test_canvas_pool_stays_bounded_on_identical_frames(self):
        app = self.app
        app.draw()
        total = len(app.canvas.find_all())
        for _ in range(30):
            app.draw()
        self.assertEqual(total, len(app.canvas.find_all()))

    def test_comparison_is_frozen_and_cancellable(self):
        app = self.app
        app.start_compare()
        self.assertFalse(app.running)
        snapshot = app.job["config"]
        app.pending["mutation"].set(1)
        self.assertEqual(app.job["config"], snapshot)
        app.advance_compare()
        self.assertEqual(app.world.tick, 0)
        app.cancel_compare()
        self.assertIsNone(app.job)
        self.assertIsNone(app.comparison)
        self.assertFalse(app.running)

    def test_comparison_completes_with_seeded_trials(self):
        app = self.app
        app.trials_var.set("3")
        app.steps_var.set("30")
        app.start_compare()
        while app.job:
            app.advance_compare()
        self.assertEqual(app.comparison["seeds"], [42, 43, 44])
        self.assertEqual(len(app.comparison["runs"]), 3)
        self.assertTrue(all(r["history"][-1]["tick"] == 30 for r in app.comparison["runs"]))
        app.draw()
        app.root.update()

    def test_json_csv_export_and_reload_settings(self):
        app = self.app
        app.step_once()
        with tempfile.TemporaryDirectory() as tmp:
            json_path = str(Path(tmp)/"run.json")
            csv_path = str(Path(tmp)/"run.csv")
            with patch("tkinter.filedialog.asksaveasfilename", return_value=json_path):
                app.export_json()
            with patch("tkinter.filedialog.asksaveasfilename", return_value=csv_path):
                app.export_csv()
            data = json.loads(Path(json_path).read_text())
            self.assertEqual(data["live_run"]["history"][-1]["tick"], 1)
            self.assertIn("config_json", Path(csv_path).read_text())
            app.pending["resources"].set(300)
            with patch("tkinter.filedialog.askopenfilename", return_value=json_path):
                app.load_settings()
            self.assertEqual(app.read_config(), app.world.cfg)

    def test_event_loop_advances_and_close_cancels_callback(self):
        app = self.app
        app.running = True
        app.last_frame -= .1
        app.frame()
        app.root.update()
        self.assertGreater(app.world.tick, 0)
        self.assertIsNotNone(app.after_id)


if __name__ == "__main__":
    unittest.main()
