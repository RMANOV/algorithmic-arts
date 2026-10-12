"""Roundoff-sized torus distance differences must not privilege an opponent.

    python3 -B -m unittest discover -s tests -p test_self_replicator_symmetric_ties.py -v

These fixed geometric fixtures exercise actual enemy selection. The 1e-12
absolute tie window is intentional at zero as well as positive distances;
separation outside that window remains a unique nearest opponent.
"""

import unittest

import self_replicator as sr


def sensing_fixture(origin, enemy_positions, seed=17):
    world = sr.World(sr.Config(seed=seed, founders=1, resources=0))
    agent = sr.Agent(50, 0, *origin, 18., sr.Genome(risk=.2))
    enemies = [sr.Agent(uid, 1 + index % 2, *position, 6. + index * 24,
                        sr.Genome(risk=.8))
               for index, (uid, position) in enumerate(zip((8, 99, 111), enemy_positions))]
    buckets = {}
    for other in (agent, *enemies):
        buckets.setdefault((int(other.x), int(other.y)), []).append(other)
    return world, agent, buckets


def selected_ids(world, agent, buckets, count=64):
    return [world._sense(agent, buckets)[0].uid for _ in range(count)]


class SymmetricTorusTieTests(unittest.TestCase):
    def assert_seeded_symmetric_choices(self, origin, positions):
        first, agent, buckets = sensing_fixture(origin, positions)
        second, replay_agent, replay_buckets = sensing_fixture(origin, positions)
        main_state = first.rng.getstate()
        sequence = selected_ids(first, agent, buckets)
        self.assertEqual(sequence, selected_ids(second, replay_agent, replay_buckets),
                         "The same seed and physical geometry must replay tie choices")
        self.assertEqual(first.rng.getstate(), main_state,
                         "Near-tie sensing must not consume the action RNG")
        self.assertEqual(set(sequence), {8, 99},
                         "Both geometrically tied opponents must be eligible")

    def test_horizontal_wrapped_symmetry_selects_both_opponents(self):
        # Intended distances are exactly .2 in either direction; modulo-based
        # float arithmetic in model 1.1 differs by about 3.55e-15.
        self.assert_seeded_symmetric_choices(
            (.1, 4.2), ((23.9, 4.2), (.3, 4.2)))

    def test_vertical_wrapped_symmetry_selects_both_opponents(self):
        # Intended vertical distances are exactly .4 on a height-16 torus.
        self.assert_seeded_symmetric_choices(
            (4.2, .2), ((4.2, 15.8), (4.2, .6)))

    def test_diagonal_wrapped_symmetry_selects_both_opponents(self):
        # Both directions have squared distance .2**2 + .2**2 = .08.
        self.assert_seeded_symmetric_choices(
            (.1, .1), ((23.9, 15.9), (.3, .3)))

    def test_resolved_one_e_minus_eight_difference_remains_unique(self):
        world, agent, buckets = sensing_fixture(
            (.1, 4.2), ((23.9, 4.2), (.30000001, 4.2)))
        tie_state, action_state = world.tie_rng.getstate(), world.rng.getstate()
        self.assertEqual(set(selected_ids(world, agent, buckets)), {8})
        self.assertEqual(world.tie_rng.getstate(), tie_state,
                         "A resolved distance difference is not a random tie")
        self.assertEqual(world.rng.getstate(), action_state)

    def test_zero_distance_and_separation_inside_absolute_window_are_tied(self):
        self.assert_seeded_symmetric_choices(
            (4., 4.), ((4., 4.), (4.0000000000005, 4.)))

    def test_zero_distance_and_separation_outside_absolute_window_remain_unique(self):
        world, agent, buckets = sensing_fixture(
            (4., 4.), ((4., 4.), (4.000000000002, 4.)))
        before = world.tie_rng.getstate()
        self.assertEqual(set(selected_ids(world, agent, buckets)), {8})
        self.assertEqual(world.tie_rng.getstate(), before)

    def test_tie_window_is_anchored_to_global_minimum_not_chained(self):
        # Candidate gaps from the minimum are approximately 0, .75e-12 and
        # 1.5e-12. The middle candidate cannot pull the last into the tie.
        world, agent, buckets = sensing_fixture(
            (4., 4.), ((4.2, 4.), (4.20000000000075, 4.), (4.2000000000015, 4.)))
        self.assertEqual(set(selected_ids(world, agent, buckets)), {8, 99},
                         "Only candidates within the absolute window of the minimum are tied")


if __name__ == "__main__":
    unittest.main()
