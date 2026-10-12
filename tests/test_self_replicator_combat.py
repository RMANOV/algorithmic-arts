"""Bounded combat regressions: one encounter draw per unordered pair/tick.

    python -m unittest discover -s tests -p test_self_replicator_combat.py -v
"""

import math
import unittest

import self_replicator as sr


class SequenceRng:
    """A finite, explicit combat draw sequence; extra draws are test failures."""

    def __init__(self, *values):
        self.values = values
        self.calls = 0

    def random(self):
        if self.calls >= len(self.values):
            raise AssertionError("Combat consumed more random draws than the supplied encounter sequence")
        value = self.values[self.calls]
        self.calls += 1
        return value


def combat_state(world):
    return {"energy": [agent.energy for agent in world.agents],
            "injury": [agent.injury for agent in world.agents],
            "heat": world.heat, "events": list(world.events), "last": world.last.copy()}


class CombatEncounterTests(unittest.TestCase):
    def fixture(self, *draws, competition=1):
        world = sr.World(sr.Config(founders=1, resources=0, competition=competition))
        a, b, c = world.agents
        # Exercise the in-range torus path, rather than relying on co-location.
        a.x, a.y = .1, 5.
        b.x, b.y = sr.COLS - .1, 5.
        c.x, c.y = .3, 5.
        world.rng = SequenceRng(*draws)
        return world, a, b, c

    def test_failed_encounter_cannot_be_rerolled_by_reversed_pair(self):
        # The first draw rejects combat; the next draw would accept it. A reverse
        # turn must leave that next draw unused and must not injure either agent.
        world, a, b, _ = self.fixture(.9, 0., 0., 0., 0.)
        pairs = set()
        before = combat_state(world)
        world._fight(a, b, pairs)
        self.assertEqual(combat_state(world), before)
        world._fight(b, a, pairs)
        self.assertEqual(combat_state(world), before)
        self.assertEqual(world.rng.calls, 1)
        self.assertEqual(pairs, {tuple(sorted((a.uid, b.uid)))})

    def test_failed_encounter_cannot_be_rerolled_in_same_direction(self):
        world, a, b, _ = self.fixture(.9, 0., 0., 0., 0.)
        pairs = set()
        before = combat_state(world)
        world._fight(a, b, pairs)
        world._fight(a, b, pairs)
        self.assertEqual(combat_state(world), before)
        self.assertEqual(world.rng.calls, 1)

    def test_out_of_range_does_not_use_pair_or_rng_before_later_close_encounter(self):
        world, a, b, _ = self.fixture(0., 0., .25, .75)
        b.x = 2.
        pairs = set()
        before = combat_state(world)
        world._fight(a, b, pairs)
        self.assertEqual(pairs, set())
        self.assertEqual(world.rng.calls, 0)
        self.assertEqual(combat_state(world), before)
        b.x = .5
        world._fight(a, b, pairs)
        self.assertEqual(pairs, {tuple(sorted((a.uid, b.uid)))})
        self.assertEqual(world.rng.calls, 4)
        self.assertEqual(len(world.events), 1)
        self.assertEqual(world.events[-1]["kind"], "fight")
        self.assertGreater(world.heat, before["heat"])

    def test_next_tick_with_fresh_pairs_allows_another_encounter(self):
        world, a, b, _ = self.fixture(.9, 0., 0., 0., 0.)
        world.tick = 1
        first_tick_pairs = set()
        world._fight(a, b, first_tick_pairs)
        self.assertEqual(len(world.events), 0)
        world.tick = 2
        next_tick_pairs = set()
        world._fight(b, a, next_tick_pairs)
        self.assertEqual(world.rng.calls, 5)
        self.assertEqual(next_tick_pairs, {tuple(sorted((a.uid, b.uid)))})
        self.assertEqual(len(world.events), 1)
        self.assertEqual(world.events[-1]["tick"], 2)
        self.assertGreater(world.heat, 0)

    def test_failed_pair_does_not_block_distinct_pair_in_same_tick(self):
        world, a, b, c = self.fixture(.9, 0., 0., .1, .2)
        pairs = set()
        world._fight(a, b, pairs)
        world._fight(a, c, pairs)
        self.assertEqual(world.rng.calls, 5)
        self.assertEqual(pairs, {tuple(sorted((a.uid, b.uid))), tuple(sorted((a.uid, c.uid)))})
        self.assertEqual(b.energy, 18.)
        self.assertEqual(b.injury, 0.)
        self.assertEqual(len(world.events), 1)
        self.assertEqual({world.events[-1]["uid"], world.events[-1]["other"]}, {a.uid, c.uid})
        self.assertGreater(a.injury, 0)
        self.assertGreater(c.injury, 0)

    def test_successful_fight_preserves_energy_and_caps_transfer_and_injury(self):
        for competition, loser_energy, transfer in ((.6, 18., 1.8),
                                                    (1., 1.1, .09),
                                                    (1., .4, 0.)):
            with self.subTest(competition=competition, loser_energy=loser_energy):
                world, a, b, _ = self.fixture(0., 0., 0., 0., competition=competition)
                b.energy = loser_energy
                before = math.fsum(world.food) + math.fsum(agent.energy for agent in world.agents) + world.heat
                pairs = set()
                world._fight(a, b, pairs)
                after = math.fsum(world.food) + math.fsum(agent.energy for agent in world.agents) + world.heat
                self.assertAlmostEqual(after, before, places=12)
                event = world.events[-1]
                self.assertEqual(event["winner"], a.uid)
                self.assertEqual(event["loser"], b.uid)
                self.assertAlmostEqual(event["transfer"], transfer, places=12)
                self.assertLessEqual(event["transfer"], 3 * competition)
                self.assertLessEqual(event["transfer"], .3 * max(0., loser_energy - .8) + 1e-12)
                self.assertTrue(all(agent.energy >= 0 for agent in world.agents))
                self.assertLessEqual(b.injury, loser_energy)
                self.assertAlmostEqual(world.heat, a.injury + b.injury, places=12)
                successful_state = combat_state(world)
                world._fight(b, a, pairs)
                self.assertEqual(combat_state(world), successful_state)
                self.assertEqual(world.rng.calls, 4)


if __name__ == "__main__":
    unittest.main()
