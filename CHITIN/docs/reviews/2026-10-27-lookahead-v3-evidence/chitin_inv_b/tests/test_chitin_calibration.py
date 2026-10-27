"""Calibration observes a held-action segment, not a later replanned policy."""

import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "CHITIN" / "battle_evolution.py"
SPEC = importlib.util.spec_from_file_location("chitin_calibration_regression", SOURCE)
chitin = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = chitin
SPEC.loader.exec_module(chitin)


class CalibrationTests(unittest.TestCase):
    def scenario(self):
        world = chitin.BattleWorld(seed=731, auto=False)
        actor = next(
            a for a in world.agents if world.factions[a.faction].method == "Lookahead"
        )
        actor.action, actor.target = "MINE", (20.0, 20.0)
        actor.next_decision, actor.decision_id = world.tick + 8, 1
        return world, actor

    @staticmethod
    def forecast(
        action="MINE", energy=80.0, health=70.0, long_energy=0.0, long_health=0.0
    ):
        return {
            "candidates": {
                action: [
                    {"ticks": h, "energy": long_energy, "health": long_health}
                    for h in (30, 90, 180)
                ]
            },
            "validation_candidates": {
                action: [
                    {"ticks": h, "energy": energy, "health": health}
                    for h in (1, 8, 9, 10, 11, 12)
                ]
            },
        }

    def test_replanning_outcomes_remain_visible_but_do_not_lower_trust(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        actor.energy, actor.health = 80.0, 70.0
        forecast = self.forecast()
        ledger.record(actor, forecast)
        ledger.record_validation(actor, forecast)
        world.tick = 8
        ledger.before_decision(actor)
        self.assertEqual(ledger.validation_count, 1)
        self.assertEqual(ledger.validation_error_sum, 0.0)
        actor.action, actor.target = "RETREAT", (5.0, 5.0)
        ledger.note_decision(actor)
        world.tick = 180
        ledger.step()
        self.assertEqual(ledger.count, 3)
        self.assertGreater(ledger.error_sum, 0.0)
        self.assertEqual(ledger.validation_error_sum, 0.0)
        self.assertTrue(
            all("action_changed" in r["interventions"] for r in ledger.outcomes)
        )
        sensed = world._sense(actor)
        _, _, projected = chitin.predictive_scores(
            world, actor, sensed, world._utility(actor, sensed)
        )
        self.assertEqual(projected["calibration"]["observations"], 1)
        self.assertEqual(projected["calibration"]["mean_error"], 0.0)

    def test_actual_short_error_lowers_confidence_after_six_observations(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        for n in range(6):
            actor.next_decision = world.tick + 8
            actor.decision_id += 1
            ledger.record_validation(actor, self.forecast(energy=100.0, health=70.0))
            actor.energy, actor.health = 10.0, 20.0
            world.tick += 8
            ledger.before_decision(actor)
        self.assertEqual(ledger.validation_count, 6)
        self.assertEqual(ledger.validation_error_sum, 420.0)
        sensed = world._sense(actor)
        _, _, projected = chitin.predictive_scores(
            world, actor, sensed, world._utility(actor, sensed)
        )
        self.assertLess(projected["calibration"]["trust"], 0.25)
        self.assertEqual(projected["calibration"]["mean_error"], 70.0)

    def test_early_death_is_adverse_calibration_not_a_filtered_sample(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        ledger.record(actor, self.forecast())
        ledger.record_validation(actor, self.forecast())
        world.tick = 3
        actor.health = 0.0
        world._die(actor)
        self.assertEqual(ledger.validation_count, 1)
        self.assertEqual(ledger.validation_error_sum, 70.0)
        result = ledger.validation_outcomes[-1]
        self.assertTrue(result["early_death"])
        self.assertIsNone(result["energy_error"])
        self.assertEqual(result["health_error"], 70.0)
        ledger.step()
        self.assertEqual(ledger.count, 3)
        self.assertTrue(all(row["early_death"] for row in ledger.outcomes))

    def test_same_action_different_target_is_an_explicit_intervention(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        ledger.record(actor, self.forecast())
        ledger.record_validation(actor, self.forecast())
        actor.target = (35.0, 20.0)
        world.tick = 4
        ledger.step()
        world.tick = 8
        ledger.before_decision(actor)
        self.assertEqual(ledger.validation_count, 0)
        self.assertEqual(ledger.validation_outcomes[-1]["status"], "censored")
        self.assertIn("target_changed", ledger.validation_outcomes[-1]["interventions"])
        world.tick = 180
        ledger.step()
        self.assertEqual(ledger.count, 3)
        self.assertTrue(
            all("target_changed" in row["interventions"] for row in ledger.outcomes)
        )

    def test_build_records_one_tick_segment_and_is_settled_before_new_planning(self):
        world, actor = self.scenario()
        world.command = None
        world.hazards.clear()
        actor.trophic = "forager"
        actor.age, actor.energy, actor.health = 110, 80.0, 70.0
        actor.metal, actor.merit = 6.0, 4.0
        actor.genes = [0.45, 1.8, 0.45, 0.45, 0.45, 0.45, 0.45, 0.45]
        for other in world.agents:
            other.x, other.y = 90.0, 55.0
        actor.x, actor.y = 10.0, 10.0
        world._rebuild_grid()
        world._choose(actor, world._sense(actor))
        self.assertEqual(actor.action, "BUILD")
        record = world.forecaster.validation_pending[actor.uid]
        self.assertEqual(record["point"]["ticks"], 1)
        world._build(actor)
        self.assertEqual(actor.next_decision, world.tick + 1)
        world.tick += 1
        world._metabolize(actor)
        observed_energy = actor.energy
        world._choose(actor, world._sense(actor))
        result = world.forecaster.validation_outcomes[-1]
        self.assertEqual(result["status"], "evaluated")
        self.assertEqual(result["actual_energy"], observed_energy)
        self.assertEqual(result["horizon"], 1)

    def test_epoch_reset_records_censoring_without_fabricating_error(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        ledger.record(actor, self.forecast())
        ledger.record_validation(actor, self.forecast())
        world.advance_episode()
        self.assertFalse(ledger.validation_pending)
        self.assertFalse(ledger.pending)
        self.assertEqual(ledger.validation_count, 0)
        self.assertEqual(ledger.validation_outcomes[-1]["reason"], "epoch_reset")
        self.assertEqual(len(ledger.outcomes), 3)
        self.assertTrue(all(row["status"] == "censored" for row in ledger.outcomes))

    def test_context_change_is_reported_without_mixing_confidence(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        ledger.record_validation(actor, self.forecast())
        world.set_mode("Scarcity")
        world.tick = 8
        ledger.before_decision(actor)
        self.assertEqual(ledger.validation_count, 0)
        self.assertIn(
            "context_changed", ledger.validation_outcomes[-1]["interventions"]
        )
        self.assertEqual(ledger.validation_censor_reasons["intervention"], 1)
        self.assertEqual(ledger.validation_interventions["context_changed"], 1)

    def test_death_after_mode_change_preserves_long_intervention(self):
        world, actor = self.scenario()
        actor.trophic = "hunter"
        actor.energy, actor.health = 0.0, 0.1
        ledger = world.forecaster
        ledger.record(actor, self.forecast())
        ledger.record_validation(actor, self.forecast())
        world.set_mode("Scarcity")
        world.step()
        self.assertNotIn(actor.uid, world._alive)
        outcomes = [r for r in ledger.outcomes if r["uid"] == actor.uid]
        self.assertEqual(len(outcomes), 3)
        self.assertTrue(all(r["early_death"] for r in outcomes))
        self.assertTrue(all("context_changed" in r["interventions"] for r in outcomes))

    def test_repeated_same_action_and_target_still_labels_long_replanning(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        ledger.record(actor, self.forecast())
        ledger.record_validation(actor, self.forecast())
        world.tick = 8
        ledger.before_decision(actor)
        self.assertEqual(ledger.validation_count, 1)
        actor.decision_id += 1
        ledger.note_decision(actor)
        world.tick = 30
        ledger.step()
        self.assertEqual(ledger.outcomes[-1]["interventions"], ["replanned"])

    def test_global_short_totals_survive_epoch_while_outcome_storage_is_bounded(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        for n in range(125):
            actor.next_decision = world.tick + 8
            actor.decision_id += 1
            ledger.record_validation(actor, self.forecast(energy=100.0, health=70.0))
            actor.energy, actor.health = 10.0, 20.0
            world.tick += 8
            ledger.before_decision(actor)
        self.assertEqual(ledger.validation_count, 125)
        self.assertEqual(ledger.validation_error_sum, 125 * 70.0)
        self.assertEqual(len(ledger.validation_outcomes), 120)
        world.advance_episode()
        self.assertEqual(ledger.validation_count, 125)
        self.assertEqual(ledger.validation_error_sum, 125 * 70.0)

    def test_ledger_does_not_consume_rng_or_count_segment_twice(self):
        world, actor = self.scenario()
        ledger = world.forecaster
        rng, tie_rng = world.rng.getstate(), world.tie_rng.getstate()
        ledger.record(actor, self.forecast())
        ledger.record_validation(actor, self.forecast())
        world.tick = 8
        ledger.before_decision(actor)
        ledger.before_decision(actor)
        self.assertEqual(ledger.validation_count, 1)
        self.assertEqual(world.rng.getstate(), rng)
        self.assertEqual(world.tie_rng.getstate(), tie_rng)

    def test_native_retreat_replan_keeps_old_bad_outcome_out_of_confidence(self):
        # Original discriminating audit scene; initial ATTACK is synthetic,
        # subsequent turns and the beneficial RETREAT use the real controller.
        world = chitin.BattleWorld(seed=0, auto=False)
        world.command, world.hazards, world.hazard = None, [], (0.0, 0.0, 0.0)
        actor = next(
            a for a in world.agents if a.faction == 5 and a.trophic == "hunter"
        )
        enemy = next(
            a for a in world.agents if a.faction != 5 and a.trophic == "hunter"
        )
        world.agents = [actor, enemy]
        world._alive = {a.uid: a for a in world.agents}
        actor.x, actor.y, actor.energy, actor.health = 30.0, 30.0, 60.0, 24.0
        enemy.x, enemy.y, enemy.energy, enemy.health = 31.7, 30.0, 60.0, 70.0
        actor.action = enemy.action = "ATTACK"
        actor.target, enemy.target = (enemy.x, enemy.y), (actor.x, actor.y)
        actor.next_decision, enemy.next_decision = 8, 100000
        world.level = 6
        world._rebuild_grid()
        world._refresh_ecology(0.0)
        world.metal_initial = world.metal_total()
        sensed = world._sense(actor)
        forecast = chitin.predictive_scores(
            world, actor, sensed, world._utility(actor, sensed)
        )[2]
        world.forecaster.record(actor, forecast)
        world.forecaster.record_validation(actor, forecast)
        for _ in range(8):
            world.step()
        self.assertEqual(actor.action, "RETREAT")
        calibrated = (
            world.forecaster.validation_count,
            world.forecaster.validation_error_sum,
        )
        self.assertEqual(calibrated[0], 1)
        for _ in range(22):
            world.step()
        self.assertIn(actor.uid, world._alive)
        outcome = next(
            row
            for row in world.forecaster.outcomes
            if row["uid"] == actor.uid and row["horizon"] == 30
        )
        self.assertIn("action_changed", outcome["interventions"])
        self.assertGreater(outcome["energy_error"] + outcome["health_error"], 0)
        self.assertEqual(
            (world.forecaster.validation_count, world.forecaster.validation_error_sum),
            calibrated,
        )


if __name__ == "__main__":
    unittest.main()
