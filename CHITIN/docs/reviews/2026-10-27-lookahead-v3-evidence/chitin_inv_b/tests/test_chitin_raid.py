"""RAID interception must use the same observed contact as its forecast."""

import importlib.util
import math
import sys
import unittest
from collections import deque
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "CHITIN" / "battle_evolution.py"
SPEC = importlib.util.spec_from_file_location("chitin_raid_regression", SOURCE)
chitin = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = chitin
SPEC.loader.exec_module(chitin)


class RaidIdentityTests(unittest.TestCase):
    def scenario(
        self, nearest_velocity=(0.0, 0.0), raid_velocity=(0.0, 0.0), same_identity=False
    ):
        world = chitin.BattleWorld(seed=17001, auto=False, max_agents=60)
        world.level = 6
        world.hazards.clear()
        actor = next(
            a for a in world.agents if a.faction == 5 and a.trophic == "forager"
        )
        nearest = next(
            a for a in world.agents if a.faction == 0 and a.trophic == "forager"
        )
        richest = next(
            a for a in world.agents if a.faction == 1 and a.trophic == "forager"
        )
        for index, agent in enumerate(world.agents):
            agent.x, agent.y = 90 + index % 5, 50 + index // 5
        actor.x, actor.y = 5.0, 10.0
        nearest.x, nearest.y = 10.0, 10.0
        richest.x, richest.y = 12.0, 10.0
        nearest.metal, richest.metal = (15.0, 0.0) if same_identity else (1.0, 14.0)
        for agent, velocity in ((nearest, nearest_velocity), (richest, raid_velocity)):
            agent.action = "MINE"
            agent.trail = deque(
                [
                    (agent.x - 3 * velocity[0], agent.y - 3 * velocity[1]),
                    (agent.x, agent.y),
                ],
                maxlen=16,
            )
        # All weights are within the model's inherited range; selection is real.
        actor.genes = [0.45, 0.45, 0.45, 0.45, 0.45, 0.45, 1.8, 0.45]
        actor.speed = 0.7 + 0.3 * actor.genes[0]
        actor.armor = 0.72 + 0.28 * actor.genes[4]
        actor.damage = 0.7 + 0.3 * actor.genes[2]
        world._rebuild_grid()
        sensed = world._sense(actor)
        self.assertEqual(sensed["enemy"].uid, nearest.uid)
        self.assertEqual(
            sensed["raid_target"].uid, nearest.uid if same_identity else richest.uid
        )
        return world, actor, nearest, richest, sensed

    def expected_lead(self, actor, contact, default, velocity):
        distance = math.hypot(actor.x - contact.x, actor.y - contact.y)
        lead = min(18.0, distance / max(0.15, 0.23 * actor.speed) * 0.28)
        return default[0] + velocity[0] * lead, default[1] + velocity[1] * lead

    def test_unrelated_motion_changes_neither_raid_forecast_target_nor_movement(self):
        observations = []
        for velocity in ((0.0, 0.0), (0.2, 0.0), (-0.2, 0.0), (0.0, 0.2)):
            with self.subTest(nearest_velocity=velocity):
                world, actor, nearest, richest, sensed = self.scenario(velocity)
                self.assertNotEqual(nearest.uid, richest.uid)
                default = world._target(actor, sensed, "RAID")
                target = chitin.predictive_target(world, actor, sensed, "RAID", default)
                scores, _, _ = chitin.predictive_scores(
                    world, actor, sensed, world._utility(actor, sensed)
                )
                world._choose(actor, sensed)
                self.assertEqual(actor.action, "RAID")
                world._move(actor)
                observations.append(
                    (target, scores[6], actor.target, (actor.x, actor.y))
                )
        reference = observations[0]
        self.assertEqual(reference[0], (12.0, 10.0))
        for observation in observations[1:]:
            self.assertEqual(observation, reference)

    def test_distinct_moving_raid_contact_supplies_its_own_velocity(self):
        velocity = (0.0, 0.2)
        world, actor, _, richest, sensed = self.scenario(raid_velocity=velocity)
        default = world._target(actor, sensed, "RAID")
        actual = chitin.predictive_target(world, actor, sensed, "RAID", default)
        expected = self.expected_lead(actor, richest, default, velocity)
        self.assertAlmostEqual(actual[0], expected[0])
        self.assertAlmostEqual(actual[1], expected[1])
        self.assertGreater(actual[1], default[1])

    def test_same_contact_keeps_existing_positive_interception(self):
        velocity = (0.2, 0.0)
        world, actor, nearest, _, sensed = self.scenario(velocity, same_identity=True)
        default = world._target(actor, sensed, "RAID")
        actual = chitin.predictive_target(world, actor, sensed, "RAID", default)
        expected = self.expected_lead(actor, nearest, default, velocity)
        self.assertAlmostEqual(actual[0], expected[0])
        self.assertAlmostEqual(actual[1], expected[1])
        self.assertGreater(actual[0], default[0])

    def test_distant_frozen_raid_goal_is_not_replaced_by_contact_tracking(self):
        world, actor, _, _, sensed = self.scenario((0.2, 0.0), (0.0, 0.2))
        default = (80.0, 50.0)
        self.assertEqual(
            chitin.predictive_target(world, actor, sensed, "RAID", default), default
        )

    def test_absent_or_null_raid_contact_falls_back_to_nearest(self):
        velocity = (0.2, 0.0)
        world, actor, nearest, _, sensed = self.scenario(velocity)
        default = (nearest.x, nearest.y)
        expected = self.expected_lead(actor, nearest, default, velocity)
        for include_null in (False, True):
            with self.subTest(explicit_null=include_null):
                observation = dict(sensed)
                observation.pop("raid_target")
                if include_null:
                    observation["raid_target"] = None
                actual = chitin.predictive_target(
                    world, actor, observation, "RAID", default
                )
                self.assertAlmostEqual(actual[0], expected[0])
                self.assertAlmostEqual(actual[1], expected[1])

    def test_attack_and_flank_still_track_nearest_contact(self):
        velocity = (0.0, 0.2)
        world, actor, nearest, _, sensed = self.scenario(velocity, (-0.2, 0.0))
        for action in ("ATTACK", "FLANK"):
            with self.subTest(action=action):
                default = world._target(actor, sensed, action)
                actual = chitin.predictive_target(world, actor, sensed, action, default)
                expected = self.expected_lead(actor, nearest, default, velocity)
                self.assertAlmostEqual(actual[0], expected[0])
                self.assertAlmostEqual(actual[1], expected[1])

    def test_no_observed_contact_preserves_default_goal(self):
        world, actor, _, _, _ = self.scenario()
        default = (20.0, 20.0)
        self.assertEqual(
            chitin.predictive_target(world, actor, {}, "RAID", default), default
        )


if __name__ == "__main__":
    unittest.main()
