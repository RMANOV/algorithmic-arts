"""Behavioral regressions for spatial sensing, fair ties and numeric inputs.

    python -m unittest discover -s tests -p test_self_replicator_regressions.py -v

All probes use the standard library and bounded, headless model runs.
"""

import json
import math
import random
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import self_replicator as sr


def buckets_for(agents):
    buckets = {}
    for agent in agents:
        buckets.setdefault((int(agent.x), int(agent.y)), []).append(agent)
    return buckets


def wrapped_displacement(origin, target, size):
    """Independent geometry oracle for these normalized, nearby inputs."""
    raw = target - origin
    return min((raw - size, raw, raw + size), key=abs)


def torus_distance(first, second):
    return math.hypot(wrapped_displacement(first.x, second.x, sr.COLS),
                      wrapped_displacement(first.y, second.y, sr.ROWS))


def physical_state(world):
    """Ignore identifier labels while retaining all physical agent state."""
    agents = []
    for agent in world.agents:
        state = asdict(agent)
        state.pop("uid")
        state.pop("parent")
        state.pop("trace")
        agents.append(state)
    agents.sort(key=lambda state: (state["lineage"], state["generation"],
                                   state["x"], state["y"], state["energy"]))
    return {"agents": agents, "food": world.food.copy(), "snapshot": world.snapshot(),
            "actions": dict(world.actions)}


class SpatialSensingTests(unittest.TestCase):
    def test_neighbors_include_cell_offset_three_in_each_torus_direction(self):
        world = sr.World(sr.Config(founders=1))
        cases = (("right", (.99, 4.2), (3.01, 4.2)),
                 ("left", (3.01, 4.2), (.99, 4.2)),
                 ("down", (4.2, .99), (4.2, 3.01)),
                 ("wrapped_right", (23.99, 4.2), (2.01, 4.2)),
                 ("wrapped_left", (.01, 4.2), (21.99, 4.2)))
        for label, first, second in cases:
            with self.subTest(direction=label):
                a = sr.Agent(0, 0, *first, 18., sr.Genome())
                enemy = sr.Agent(1, 1, *second, 18., sr.Genome())
                found = world._neighbors(a, buckets_for([a, enemy]))
                self.assertEqual([other for _, other in found], [enemy])
                self.assertAlmostEqual(found[0][0], 2.02, places=12)

    def test_neighbor_index_matches_independent_all_pairs_oracle(self):
        world = sr.World(sr.Config(founders=1))
        rng = random.Random(12345)
        agents = [sr.Agent(i, i % 3, rng.random() * sr.COLS, rng.random() * sr.ROWS,
                           0. if i % 17 == 0 else 18., sr.Genome())
                  for i in range(150)]
        buckets = buckets_for(agents)
        for a in agents:
            with self.subTest(agent=a.uid):
                expected = {other.uid for other in agents
                            if other.lineage != a.lineage and other.energy > 0
                            and torus_distance(a, other) < 2.2}
                actual = world._neighbors(a, buckets)
                self.assertEqual({other.uid for _, other in actual}, expected)
                self.assertEqual(len(actual), len(expected), "Wrapped buckets duplicated an enemy")
                for distance, other in actual:
                    self.assertAlmostEqual(distance, torus_distance(a, other), places=12)

    def test_sensing_matches_full_torus_pressure_at_unique_nearest_and_edges(self):
        cases = (
            ((12.1, 8.3), ((12.4, 8.45), (13.2, 8.9), (11.9, 9.4))),
            ((.1, 5.2), ((23.85, 5.4), (1.2, 6.1), (23.6, 4.0))),
            ((7.2, .1), ((7.4, 15.85), (8.1, 1.2), (6.0, 15.6))),
            ((23.8, 15.9), ((.25, .1), (22.9, 14.6), (.6, 15.2))),
            ((.01, 4.2), ((21.99, 4.2),)),
        )
        for position, enemy_positions in cases:
            with self.subTest(position=position):
                world = sr.World(sr.Config(founders=1, competition=.8, resources=0))
                a = sr.Agent(0, 0, *position, 22., sr.Genome())
                enemies = [sr.Agent(i + 1, 1, *point, 9. + i * 13, sr.Genome())
                           for i, point in enumerate(enemy_positions)]
                world.food = [(i % 17) / 17 for i in range(sr.COLS * sr.ROWS)]
                sensed = world._sense(a, buckets_for([a, *enemies]))
                eligible = [other for other in enemies if torus_distance(a, other) < 2.2]
                nearest = min(eligible, key=lambda other: torus_distance(a, other))
                nearest_distance = torus_distance(a, nearest)
                self.assertEqual(sum(abs(torus_distance(a, other) - nearest_distance) < 1e-12
                                     for other in eligible), 1)
                strength = (a.energy + 2) / (nearest.energy + 2)
                danger = min(1, world.cfg.competition * (1 - nearest_distance / 2.2)
                             * min(1.5, 1 / strength))
                self.assertIs(sensed[0], nearest)
                self.assertAlmostEqual(sensed[1], danger, places=12)
                self.assertAlmostEqual(sensed[2], strength, places=12)
                options = [(a.x + dx, a.y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]

                def pressure(point):
                    return math.fsum(max(0, 1.5 - math.hypot(
                        wrapped_displacement(point[0], other.x, sr.COLS),
                        wrapped_displacement(point[1], other.y, sr.ROWS))) for other in eligible)

                minimum = min(pressure(point) for point in options)
                self.assertIn(sensed[4], options)
                self.assertAlmostEqual(pressure(sensed[4]), minimum, places=12)
                self.assertEqual(sensed[3], minimum < pressure((a.x, a.y)) - .05)
                best = max(options, key=lambda point: world.food[
                    int(point[1] % sr.ROWS) * sr.COLS + int(point[0] % sr.COLS)])
                self.assertEqual(sensed[5], best)
                self.assertEqual(sensed[6], world.food[
                    int(best[1] % sr.ROWS) * sr.COLS + int(best[0] % sr.COLS)])


class TieAndReplayTests(unittest.TestCase):
    @staticmethod
    def tied_fixture():
        a = sr.Agent(50, 0, 4.5, 4.5, 18., sr.Genome(risk=.2))
        low_uid = sr.Agent(8, 1, 4.5, 4.5, 6., sr.Genome(risk=.8))
        high_uid = sr.Agent(99, 2, 4.5, 4.5, 54., sr.Genome(risk=.5))
        return a, buckets_for([a, low_uid, high_uid])

    def test_equal_distance_enemy_selection_is_not_always_smallest_uid(self):
        choices = Counter()
        for seed in range(64):
            world = sr.World(sr.Config(seed=seed, founders=1, resources=0))
            a, buckets = self.tied_fixture()
            choices[world._sense(a, buckets)[0].uid] += 1
        self.assertEqual(set(choices), {8, 99})
        # Broad fixed-seed bounds catch systematic preference without a flaky
        # requirement for an exact random sequence or an exactly even split.
        self.assertTrue(all(8 <= count <= 56 for count in choices.values()), choices)

    def test_nearest_ties_do_not_consume_main_action_rng(self):
        world = sr.World(sr.Config(seed=7, founders=1, resources=0))
        a, buckets = self.tied_fixture()
        before = world.rng.getstate()
        for _ in range(16):
            world._sense(a, buckets)
        self.assertEqual(world.rng.getstate(), before)

    def test_zero_or_unique_nearest_sensing_does_not_advance_future_tie_choices(self):
        first, second = (sr.World(sr.Config(seed=19, founders=1, resources=0)) for _ in range(2))
        a, tied = self.tied_fixture()
        unique_enemy = sr.Agent(8, 1, 4.6, 4.5, 6., sr.Genome())
        unique = buckets_for([a, unique_enemy])
        for _ in range(7):
            self.assertIs(first._sense(a, unique)[0], unique_enemy)
            self.assertIsNone(first._sense(a, {})[0])
        self.assertEqual([first._sense(a, tied)[0].uid for _ in range(24)],
                         [second._sense(a, tied)[0].uid for _ in range(24)])

    def test_uid_renumbering_leaves_physical_trajectories_unchanged(self):
        for seed in (7, 19, 42):
            with self.subTest(seed=seed):
                first, renumbered = (sr.World(sr.Config(seed=seed, founders=12)) for _ in range(2))
                for agent in renumbered.agents:
                    agent.uid = 3 * (agent.uid // 3) + (agent.uid % 3 + 1) % 3
                self.assertEqual(physical_state(first), physical_state(renumbered))
                for tick in range(60):
                    first.step()
                    renumbered.step()
                    self.assertEqual(physical_state(first), physical_state(renumbered),
                                     f"Identifier labels changed physical state at tick {tick + 1}")

    def test_fixed_seed_replays_match_after_stochastic_ties_and_steps(self):
        for seed in (0, 7, 2**32 - 1):
            with self.subTest(seed=seed):
                first, second = (sr.World(sr.Config(seed=seed, founders=2, mutation=1)) for _ in range(2))
                a, buckets = self.tied_fixture()
                self.assertEqual([first._sense(a, buckets)[0].uid for _ in range(24)],
                                 [second._sense(a, buckets)[0].uid for _ in range(24)])
                for _ in range(60):
                    first.step()
                    second.step()
                self.assertEqual(first.export(), second.export())
                self.assertEqual([asdict(agent) for agent in first.agents],
                                 [asdict(agent) for agent in second.agents])
                self.assertEqual(first.rng.getstate(), second.rng.getstate())

    def test_rendering_preserves_both_rngs_and_future_physical_replay(self):
        first, second = (sr.World(sr.Config(seed=7, founders=2, mutation=1)) for _ in range(2))
        for _ in range(30):
            first.step()
            second.step()
        before = first.rng.getstate(), first.tie_rng.getstate()
        ink = sr.Ink()
        view = sr.ObservatoryView(ink)
        uid = first.agents[0].uid if first.agents else None
        for width, height in ((868, 650), (1188, 800)):
            ink.begin()
            view.world(first, width, height, uid)
            for index in range(len(sr.CONCEPTS)):
                ink.begin()
                view.concepts(first, width, height, index, uid)
            ink.begin()
            view.compare(None, "", width, height)
        self.assertEqual((first.rng.getstate(), first.tie_rng.getstate()), before)
        for _ in range(30):
            first.step()
            second.step()
        self.assertEqual(physical_state(first), physical_state(second))
        self.assertEqual(first.export(), second.export())
        self.assertEqual(first.rng.getstate(), second.rng.getstate())
        self.assertEqual(first.tie_rng.getstate(), second.tie_rng.getstate())


class NumericConfigTests(unittest.TestCase):
    def test_arbitrary_size_out_of_range_integers_raise_value_error(self):
        for field in ("resources", "regrowth", "replication_cost", "mutation",
                      "competition", "seed", "founders"):
            with self.subTest(field=field):
                try:
                    sr.Config(**{field: 10**400})
                except Exception as error:
                    self.assertIsInstance(error, ValueError)
                else:
                    self.fail(f"An out-of-range integer was accepted for {field}")

    def test_boolean_tokens_are_rejected_for_every_numeric_field(self):
        for field in ("resources", "regrowth", "replication_cost", "mutation",
                      "competition", "seed", "founders"):
            for value in (False, True):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        sr.Config(**{field: value})

    def test_cli_reports_invalid_numeric_config_without_a_traceback(self):
        for data in ({"founders": 10**400}, {"resources": True}):
            with self.subTest(data=data):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "invalid.json"
                    path.write_text(json.dumps(data), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, "-B", str(Path(sr.__file__).resolve()), "--headless",
                         "--trials", "1", "--steps", "1", "--config", str(path)],
                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
