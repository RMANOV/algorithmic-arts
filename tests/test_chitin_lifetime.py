"""Independent lifetime oracles for the post-metabolism forecast phase."""
import importlib.util
import math
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'CHITIN' / 'battle_evolution.py'
spec = importlib.util.spec_from_file_location('chitin_lifetime_test', SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class LifetimeTests(unittest.TestCase):
    def agent(self, health=1., energy=0., trophic='hunter'):
        return m.Crab(1, 0, 30., 30., 0., health=health, energy=energy,
                      metal=0., trophic=trophic)

    def project(self, agent, action='MINE', enemy=None, **overrides):
        args = dict(a=agent, enemy=enemy, action=action,
                    food_path={30: 1., 90: 1., 180: 1.},
                    distance=0., speed=.29 if agent.trophic == 'hunter' else .23,
                    contact=1e9, reaction=0., own_rate=0., enemy_rate=0., ore_available=15.)
        args.update(overrides)
        return m._forecast_lifetime(**args)

    def fixed_miner_world(self, health, energy):
        w = m.BattleWorld(seed=88001, auto=False, max_agents=6)
        a = w.agents[0]
        a.x = a.y = 30.
        a.health, a.energy, a.metal, a.trophic = health, energy, 0., 'hunter'
        a.action, a.target, a.next_decision = 'MINE', (30., 30.), 10000
        w.agents, w._alive = [a], {a.uid: a}
        w.nodes = [m.Node(30., 30., 100., 100.)]
        w.hazards, w.command, w.forecaster, w.mode = [], None, None, 'Scarcity'
        w.metal_initial = w.metal_total()
        w._rebuild_grid()
        return w, a

    def test_lifetime_matches_exact_world_steps_at_all_long_horizons(self):
        # Independent production dynamics: no model methods are stubbed.
        for health, energy in ((1., 0.), (1., .32), (70., 80.)):
            with self.subTest(health=health, energy=energy):
                w, a = self.fixed_miner_world(health, energy)
                result = self.project(a, ore_available=100.)
                # Forecast phase is after current metabolism, before action.
                w._move(a)
                w._mine(a)
                w._build(a)
                for tick in range(1, 181):
                    w.step()
                    if tick not in result['points']:
                        continue
                    actual = {
                        'ore': w.stats['mined_metal'],
                        'spent': w.stats['energy_spent'],
                        'health': max(0., a.health) if a.uid in w._alive else 0.,
                        'energy': a.energy if a.uid in w._alive else 0.,
                    }
                    for key, value in actual.items():
                        self.assertAlmostEqual(result['points'][tick][key], value,
                                               msg=f'{tick=} {key=}')

    def test_original_prestep_witness_matches_real_world_death(self):
        w, a = self.fixed_miner_world(1., 0.)
        # Production's first forecast sees .78 health after metabolism.
        observed = self.agent()
        w._metabolize(observed)
        result = self.project(observed, ore_available=100.)
        for _ in range(30):
            w.step()
        self.assertNotIn(a.uid, w._alive)
        self.assertAlmostEqual(w.stats['mined_metal'], 2.2)
        self.assertAlmostEqual(result['points'][30]['ore'], w.stats['mined_metal'])
        self.assertEqual(w.stats['energy_spent'], 0.)

    def test_death_preserves_only_current_and_predeath_harvest(self):
        # Snapshot is after current metabolism: mine now, then four future
        # surviving turns; the fifth future metabolism kills before mining.
        result = self.project(self.agent())
        for point in result['points'].values():
            self.assertAlmostEqual(point['ore'], 2.75)
            self.assertEqual(point['spent'], 0.)
            self.assertEqual(point['health'], 0.)
            self.assertEqual(point['energy'], 0.)

    def test_prestep_witness_first_observation_is_after_metabolism(self):
        a = self.agent()
        w = m.BattleWorld(seed=42, auto=False)
        w._metabolize(a)
        self.assertAlmostEqual(a.health, .78)
        result = self.project(a)
        self.assertAlmostEqual(result['points'][30]['ore'], 2.2)

    def test_healthy_control_retains_finite_ore_and_paid_costs(self):
        result = self.project(self.agent(70., 80.))
        for horizon, point in result['points'].items():
            self.assertEqual(point['ore'], 15.)
            self.assertAlmostEqual(point['spent'], .16*horizon)
            self.assertAlmostEqual(point['energy'], 80.-.16*horizon)
            self.assertEqual(point['health'], 70.)

    def test_late_death_does_not_collect_or_spend_afterward(self):
        result = self.project(self.agent(1., .32))
        # Two future metabolic payments exhaust .32, then starvation kills on
        # future tick6: current action plus ticks1..5 mine six times.
        for point in result['points'].values():
            self.assertAlmostEqual(point['ore'], 3.3)
            self.assertAlmostEqual(point['spent'], .32)
            self.assertEqual(point['health'], 0.)

    def test_dead_forager_does_not_resurrect_when_future_food_improves(self):
        result = self.project(self.agent(1., 0., 'forager'),
                              food_path={30: 0., 90: .6, 180: .8})
        self.assertTrue(all(p['energy'] == p['health'] == 0. for p in result['points'].values()))
        self.assertTrue(all(p['ore'] == 2.75 for p in result['points'].values()))

    def test_empty_hunter_cannot_pay_for_combat_or_generate_predation(self):
        enemy = self.agent(70., 80.)
        result = self.project(self.agent(70., 0.), action='ATTACK', enemy=enemy,
                              contact=0., own_rate=1., enemy_rate=0.)
        for p in result['points'].values():
            self.assertEqual(p['dealt'], 0.)
            self.assertEqual(p['stolen'], 0.)
            self.assertEqual(p['spent'], 0.)

    def test_forager_can_recover_first_strike_energy_from_food(self):
        enemy = self.agent(70., 80.)
        result = self.project(self.agent(70., 0., 'forager'), action='ATTACK', enemy=enemy,
                              contact=0., own_rate=.5, enemy_rate=0.)
        self.assertGreater(result['points'][30]['dealt'], 0.)
        self.assertGreater(result['points'][30]['spent'], 0.)
        self.assertGreaterEqual(result['points'][30]['energy'], 0.)

    def test_short_validation_is_before_action_long_point_after_action(self):
        result = self.project(self.agent(70., 80.))
        self.assertAlmostEqual(result['validation'][1]['ore'], .55)
        self.assertAlmostEqual(result['validation'][8]['ore'], 8*.55)
        self.assertAlmostEqual(result['validation'][1]['energy'], 79.84)
        self.assertEqual(result['points'][30]['ore'], 15.)

    def test_build_once_and_child_transfer_is_not_dissipated(self):
        result = self.project(self.agent(70., 80.), action='BUILD', ore_available=0.)
        p = result['validation'][1]
        self.assertAlmostEqual(p['energy'], (80.-12)*.55-.16)
        self.assertAlmostEqual(p['spent'], 12.+.16)
        self.assertEqual(p['construction'], 12.)
        self.assertEqual(result['points'][180]['construction'], 12.)

    def test_public_forecast_exposes_shared_short_points_without_rng_draw(self):
        w = m.BattleWorld(seed=42, auto=False)
        a = next(a for a in w.agents if w.factions[a.faction].method == 'Lookahead')
        s = w._sense(a)
        before = w.rng.getstate(), w.tie_rng.getstate()
        scores, _, forecast = m.predictive_scores(w, a, s, w._utility(a, s))
        self.assertEqual(before, (w.rng.getstate(), w.tie_rng.getstate()))
        self.assertTrue(all(math.isfinite(x) for x in scores))
        self.assertEqual(set(forecast['validation_candidates']), set(forecast['candidates']))
        for points in forecast['validation_candidates'].values():
            self.assertEqual([p['ticks'] for p in points], [1, 8, 9, 10, 11, 12])


if __name__ == '__main__':
    unittest.main()
