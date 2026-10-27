#!/usr/bin/env python3
"""Crab battle ecology. Stdlib only; the model never reads or writes files.

The theatre is fictional. Policies compete under shared finite-metal ecology,
not a claim about real-world intelligence or guaranteed learning superiority.
"""

from __future__ import annotations
import math
import random
from collections import Counter, deque
from dataclasses import dataclass, field

WORLD_W, WORLD_H = 100.0, 62.0
FACTION_COLORS = ("#46e6ff", "#ffb65c", "#b59aff", "#75f2a4", "#ff739d", "#6c9eff")
METHODS = ("Reflex", "Utility", "UCB", "Q-learning", "Opponent", "Lookahead")
ACTIONS = ("MINE", "BUILD", "ATTACK", "RETREAT", "GUARD", "FLANK", "RAID", "ESCORT")
MODES = ("Nugget rush", "Scarcity", "Moving seams", "Siege", "Tempest", "Arms race")
HAZARD_KINDS = ("ice", "flash", "worm", "mountain", "river", "alien", "relic")
MODEL_VERSION = "CHITIN 2.0.1 — Lifetime and forecast validation"
BIRTH_MERIT = 3.5
FOOD_CAPACITY = 240.0
BODY_METAL = 6.0


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


@dataclass
class Node:
    x: float
    y: float
    amount: float
    capacity: float
    kind: int = 0
    phase: float = 0.0


@dataclass
class Crab:
    uid: int
    faction: int
    x: float
    y: float
    heading: float
    energy: float = 80.0
    health: float = 70.0
    metal: float = 1.0
    generation: int = 0
    age: int = 0
    action: str = "MINE"
    target: tuple | None = None
    trace: dict = field(default_factory=dict)
    trail: deque = field(default_factory=lambda: deque(maxlen=16))
    genes: list = field(default_factory=lambda: [1.0] * 8)
    next_decision: int = 0
    state: str = "0/1/0"
    chosen: int = 0
    pending_reward: float = 0.0
    last_reward: float = 0.0
    parent: int | None = None
    child_paid: bool = False
    cooldown: int = 0
    armor: float = 1.0
    speed: float = 1.0
    damage: float = 1.0
    pending_birth: int | None = None
    decision_id: int = 0
    trophic: str = "forager"
    merit: float = 0.0
    merit_earned: float = 0.0
    births: int = 0
    surviving_children: int = 0
    last_birth: int = -100000
    hunger_ticks: int = 0
    forecast: dict = field(default_factory=dict)


@dataclass
class Faction:
    id: int
    name: str
    color: str
    method: str
    score: float = 0.0
    reward: float = 0.0
    births: int = 0
    kills: int = 0
    losses: int = 0
    decisions: int = 0
    updates: int = 0
    policy: dict = field(default_factory=dict)
    opponent: list = field(default_factory=lambda: [1.0] * 8)
    decisions_by_action: dict = field(default_factory=dict)
    best_genes: list = field(default_factory=lambda: [1.0] * 8)
    best_fitness: float = -1e9
    observed_decisions: dict = field(default_factory=dict)


class BattleWorld:
    """Seeded sequential ecology with per-method, bounded contextual learners.

    ``auto=False`` suppresses timed director changes and automatic new episodes.
    Metal is conserved *within an episode*: ore + cargo + bodies + reserve.
    New episodes explicitly provision a new, separately accounted arena.
    """

    def __init__(
        self, seed=42, max_agents=60, episode_ticks=1500, auto=True, learning=True
    ):
        for name, value, lo, hi in (
            ("seed", seed, 0, 2**32 - 1),
            ("max_agents", max_agents, 6, 360),
            ("episode_ticks", episode_ticks, 120, 100000),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lo <= value <= hi
            ):
                raise ValueError(f"{name} must be an integer in [{lo}, {hi}]")
        if not isinstance(auto, bool) or not isinstance(learning, bool):
            raise ValueError("auto and learning must be booleans")
        self.seed = seed
        self.max_agents = max_agents
        self.episode_ticks = episode_ticks
        self.auto = auto
        self.learning = learning
        self.rng = random.Random(seed)
        self.tie_rng = random.Random(seed ^ 0xA513A913)
        # Rendering must never consume this RNG. Tie decisions are sampled only
        # after candidates are compared against a single global extremum.
        self.tick = 0
        self.episode = 0
        self.episode_tick = 0
        self.level = 1
        self.mode = MODES[0]
        self.next_shift = 0
        self.uid_counter = 0
        self.agents = []
        self.nodes = []
        self.effects = deque(maxlen=360)
        self.events = deque(maxlen=8)
        self.history = deque(maxlen=600)
        self.timeline = deque(maxlen=128)
        self.episodes = deque(maxlen=40)
        self.stats = Counter()
        self.factions = []
        self.reserve = 0.0
        self.metal_initial = 0.0
        self.last_ledger_error = 0.0
        self._grid = {}
        self._pairs = set()
        self._alive = {}
        self.hazard = (50.0, 31.0, 0.0)
        self.hazards = []
        self.hazard_id = 0
        self.next_hazard = 75
        self.birth_transitions = {}
        self.forecasts = deque(maxlen=240)
        self.nutrient = FOOD_CAPACITY
        self.ecology = {}
        self._crisis = False
        for i, name in enumerate(
            ("AURORA", "EMBER", "PRISM", "VERDANT", "CORAL", "AZURE")
        ):
            self.factions.append(Faction(i, name, FACTION_COLORS[i], METHODS[i]))
        self.command = CommandNetwork(self) if "CommandNetwork" in globals() else None
        self.forecaster = (
            ForecastLedger(self) if "ForecastLedger" in globals() else None
        )
        self.advance_episode()

    def _event(self, text, faction=None):
        self.events.append(
            {
                "tick": self.tick,
                "text": text,
                "color": FACTION_COLORS[faction] if faction is not None else "#b6c8df",
            }
        )

    def _effect(self, kind, a, tx=None, ty=None):
        self.effects.append(
            {
                "kind": kind,
                "x": a.x,
                "y": a.y,
                "tx": a.x if tx is None else tx,
                "ty": a.y if ty is None else ty,
                "tick": self.tick,
                "faction": a.faction,
            }
        )

    def _sample_best(self, seq, key, maximize=False):
        if not seq:
            return None
        values = [key(a) for a in seq]
        best = (max if maximize else min)(values)
        tied = [a for a, v in zip(seq, values) if abs(v - best) <= 1e-10]
        return self.tie_rng.choice(tied)

    def _new_crab(
        self, faction, x, y, genes=None, generation=0, parent=None, trophic="forager"
    ):
        self.uid_counter += 1
        genes = list(genes or [1.0] * 8)
        a = Crab(
            self.uid_counter,
            faction,
            clamp(x, 1, WORLD_W - 1),
            clamp(y, 1, WORLD_H - 1),
            self.rng.random() * math.tau,
            genes=genes,
            generation=generation,
            parent=parent,
            trophic=trophic,
        )
        a.speed = clamp(0.7 + 0.3 * genes[0], 0.7, 1.25)
        a.armor = clamp(0.72 + 0.28 * genes[4], 0.72, 1.25)
        a.damage = clamp(0.7 + 0.3 * genes[2], 0.7, 1.3)
        a.next_decision = self.tick + self.rng.randrange(5)
        a.trail.append((a.x, a.y))
        self.agents.append(a)
        self._alive[a.uid] = a
        return a

    def advance_episode(self):
        if self.episode:
            self.stats["birth_transitions_censored"] += len(self.birth_transitions)
            self.episodes.append(self.snapshot())
        self.episode += 1
        self.episode_tick = 0
        self.level = min(6, max(self.level, self.episode))
        self.agents = []
        self.nodes = []
        self._alive = {}
        self._grid = {}
        self.effects.clear()
        self._pairs.clear()
        self.hazards = []
        self.birth_transitions = {}
        self.next_hazard = self.tick + 90
        # Method-to-colour assignments rotate; learners belong to the method.
        previous = {f.method: f.policy for f in self.factions}
        methods = list(METHODS)
        if self.episode > 1:
            self.rng.shuffle(methods)
        founders = min(4, self.max_agents // 6)
        for f, method in zip(self.factions, methods):
            # Counters describe this epoch's assigned method. Prior epochs are
            # already frozen in episodes; lineage genes may persist separately.
            f.score = 0.0
            f.reward = 0.0
            f.births = 0
            f.kills = 0
            f.losses = 0
            f.decisions = 0
            f.updates = 0
            f.decisions_by_action = {}
            f.method = method
            f.policy = previous.get(method, {})
            f.opponent = [1.0] * 8
            f.observed_decisions = {}
            theta = f.id * math.tau / 6 + 0.18
            home = (50 + 26 * math.cos(theta), 31 + 18 * math.sin(theta))
            for n in range(founders):
                g = list(f.best_genes) if self.episode > 1 and n < 3 else [1.0] * 8
                self._new_crab(
                    f.id,
                    home[0] + self.rng.uniform(-4, 4),
                    home[1] + self.rng.uniform(-3, 3),
                    g,
                    trophic="hunter" if n == 0 else "forager",
                )
        # Most metal is in prominent deposits; a reserve feeds occasional showers
        # by TRANSFER, never by spawning unaccounted resources.
        budget = 1050.0
        for i in range(72):
            angle = self.rng.random() * math.tau
            radius = self.rng.random() ** 0.7
            x = 50 + 42 * radius * math.cos(angle)
            y = 31 + 25 * radius * math.sin(angle)
            amount = budget / 72
            self.nodes.append(
                Node(x, y, amount, amount, i % 3, self.rng.random() * math.tau)
            )
        self.reserve = 180.0
        self.nutrient = FOOD_CAPACITY
        self._crisis = False
        if self.command:
            self.command.reset()
        if self.forecaster:
            self.forecaster.reset()
        self.metal_initial = self.metal_total()
        self.mode = MODES[(self.episode - 1) % len(MODES)]
        self.next_shift = self.tick + self.rng.randint(280, 440)
        self.timeline.append(
            {
                "tick": self.tick,
                "episode": self.episode,
                "mode": self.mode,
                "level": self.level,
                "metal_initial": self.metal_initial,
            }
        )
        self._event(f"EPOCH {self.episode} · {self.mode} · complexity {self.level}")
        self.stats["episodes"] += 1
        self._rebuild_grid()
        self.spawn_hazard("mountain")
        self.spawn_hazard("river")
        self.spawn_hazard(HAZARD_KINDS[(self.episode - 1) % len(HAZARD_KINDS)])
        self._refresh_ecology(0.0)

    def set_mode(self, name):
        if name not in MODES:
            raise ValueError("Unknown resource regime")
        self.mode = name
        # A different regime is a new opponent-evidence context. Q/UCB use
        # explicit mode/level keys; predictor frequency caches start unknown.
        for f in self.factions:
            f.opponent = [1.0] * 8
            f.observed_decisions = {}
        self.next_shift = self.tick + self.rng.randint(280, 440)
        self.timeline.append(
            {
                "tick": self.tick,
                "episode": self.episode,
                "mode": name,
                "level": self.level,
            }
        )
        self._event(f"REGIME SHIFT · {name}")
        self.stats["mode_shifts"] += 1
        # Redistribution moves ore; existing cargo and learned values survive.
        if name in ("Siege", "Scarcity"):
            for n in self.nodes:
                n.x = clamp(50 + (n.x - 50) * 0.58, 4, 96)
                n.y = clamp(31 + (n.y - 31) * 0.58, 4, 58)
        if name == "Tempest":
            self.spawn_hazard("flash")
            self.spawn_hazard("ice")
        elif name == "Arms race":
            self.spawn_hazard("alien")
        if name == "Nugget rush":
            for n in self.nodes:
                n.x = 8 + self.rng.random() * 84
                n.y = 6 + self.rng.random() * 50

    def metal_total(self):
        return (
            self.reserve
            + sum(n.amount for n in self.nodes)
            + sum(BODY_METAL + a.metal for a in self.agents)
        )

    def _rebuild_grid(self):
        self._grid = {}
        for a in self.agents:
            self._grid.setdefault((int(a.x // 8), int(a.y // 8)), []).append(a)

    def _near(self, a, radius=16):
        reach = math.ceil(radius / 8)
        bx, by = int(a.x // 8), int(a.y // 8)
        out = []
        for x in range(bx - reach, bx + reach + 1):
            for y in range(by - reach, by + reach + 1):
                for other in self._grid.get((x, y), ()):
                    if (
                        other.uid != a.uid
                        and other.health > 0
                        and dist(a, other) < radius
                    ):
                        out.append(other)
        return out

    def _sense(self, a):
        neighbors = self._near(a, 22 if a.trophic == "hunter" else 18)
        enemies = [b for b in neighbors if b.faction != a.faction]
        allies = [b for b in neighbors if b.faction == a.faction]
        enemy = self._sample_best(
            enemies,
            lambda b: (
                dist(a, b)
                * (0.72 if a.trophic == "hunter" and b.trophic == "forager" else 1)
            ),
        )
        raid_target = self._sample_best(
            enemies, lambda b: b.metal / (1 + dist(a, b)), True
        )
        ally = self._sample_best(allies, lambda b: dist(a, b))
        food = self._sample_best(
            [n for n in self.nodes if n.amount > 0.05],
            lambda n: dist(a, n) / (1 + min(n.amount, 20) * 0.025),
        )
        pressure = sum(max(0, 1 - dist(a, b) / 12) for b in enemies)
        support = sum(max(0, 1 - dist(a, b) / 12) for b in allies)
        state = (
            int(a.health < 28) * 6
            + int(pressure > 1) * 3
            + int(a.metal >= BODY_METAL) * 2
            + int(a.energy < 35)
        )
        state = f"{MODES.index(self.mode)}/{self.level}/{a.trophic}/{min(11, state)}"
        hazard = self._hazard_threat(a)
        return {
            "hazard": hazard,
            "enemy": enemy,
            "raid_target": raid_target,
            "ally": ally,
            "food": food,
            "enemies": enemies,
            "allies": allies,
            "pressure": pressure,
            "support": support,
            "state": state,
        }

    def available_actions(self):
        # Complexity is an opportunity set, not a scripted claim of superiority.
        return ACTIONS[: min(8, 4 + max(0, self.level - 1))]

    def eligible_indices(self, a, s):
        """Hard action contracts, shared by selection and next-state TD credit.

        RETREAT is also a stationary WAIT when neither threat nor enemy exists,
        so even an exhausted arena always has an executable baseline action.
        """
        enemy = s.get("enemy")
        has_enemy = enemy is not None and enemy.health > 0
        food = s.get("food")
        ally = s.get("ally")
        feasible = (
            food is not None and food.amount > 0.05 and a.metal < 15,
            self.birth_eligible(a),
            has_enemy,
            True,
            True,
            has_enemy,
            has_enemy and bool(s.get("enemies")),
            ally is not None and ally.health > 0,
        )
        return tuple(i for i in range(len(self.available_actions())) if feasible[i])

    def _utility(self, a, s):
        e = s["enemy"]
        food = s["food"]
        d = dist(a, e) if e else 100
        danger = s["pressure"] - s["support"] * 0.6
        mine = (1.5 + max(0, 6 - a.metal) * 0.14) / (
            1 + (dist(a, food) if food else 120) * 0.03
        )
        mine *= 1 if food else 0
        build = 3.15 if self.birth_eligible(a) else -8
        hunt = (1.25 + max(0, 70 - a.energy) * 0.025) if a.trophic == "hunter" else 0.3
        attack = (
            (
                1.65
                + hunt
                + (a.health - 40) * 0.025
                + 0.3 * s["support"]
                - 0.32 * s["pressure"]
            )
            if e
            else -5
        )
        retreat = max(-1, (40 - a.health) * 0.10 + danger * 0.65) if e else -0.8
        guard = 0.48 + max(0, danger) * 0.22 + (1 - a.energy / 90) * 0.3
        flank = 1.0 + 0.22 * s["support"] + 0.15 * min(d, 12) if e else -3
        raid = 0.8 + min(2, (e.metal if e else 0) * 0.13) - danger * 0.22 if e else -3
        escort = 0.9 + max(0, (s["ally"].metal - 3) * 0.10) if s["ally"] else -3
        raw = [mine, build, attack, retreat, guard, flank, raid, escort]
        scores = [v * a.genes[i] if v > 0 else v for i, v in enumerate(raw)]
        return self.command.bias(a, s, scores) if self.command else scores

    def _learner(self, f, state):
        key = str(state)
        if key not in f.policy:
            f.policy[key] = {
                "q": [0.0] * 8,
                "n": [0] * 8,
                "mean": [0.0] * 8,
                "visits": 0,
            }
        return f.policy[key]

    def _update(self, a, s, terminal=False):
        f = self.factions[a.faction]
        reward = clamp(a.pending_reward, -4, 4)
        a.last_reward = reward
        f.reward += reward
        f.score += reward
        if a.trace:
            self.forecasts.append(
                {
                    "tick": self.tick,
                    "uid": a.uid,
                    "method": f.method,
                    "decision_id": a.decision_id,
                    "mode": self.mode,
                    "context": a.state,
                    "action": ACTIONS[a.chosen],
                    "predicted_score": a.trace.get("scores", {}).get(ACTIONS[a.chosen]),
                    "realized_reward": reward,
                    "deferred_birth": a.pending_birth,
                }
            )
        next_eligible = () if terminal else self.eligible_indices(a, s)
        if a.pending_birth is not None and a.pending_birth in self.birth_transitions:
            child_id = a.pending_birth
            record = self.birth_transitions[child_id]
            record.update(
                reward=record["reward"] + reward,
                next_state=s["state"],
                next_eligible=next_eligible,
                terminal=terminal,
                ready=True,
            )
            a.pending_birth = None
            self._finish_birth(child_id)
        elif self.learning and f.method in ("UCB", "Q-learning") and a.trace:
            self._credit(
                f, a.state, a.chosen, reward, s["state"], terminal, next_eligible
            )
        a.pending_reward = 0.0

    def _credit(
        self, f, state, index, reward, next_state, terminal=False, next_eligible=()
    ):
        p = self._learner(f, state)
        i = index
        p["visits"] += 1
        p["n"][i] += 1
        n = p["n"][i]
        p["mean"][i] += (reward - p["mean"][i]) / min(n, 35)
        nextq = self._learner(f, next_state)["q"]
        future = max((nextq[j] for j in next_eligible), default=0.0)
        target = reward + (0 if terminal else 0.83 * future)
        p["q"][i] = clamp(p["q"][i] + 0.18 * (target - p["q"][i]), -20, 20)
        f.updates += 1
        self.stats["learning_updates"] += 1

    def _resolve_birth(self, child, survived):
        record = self.birth_transitions.get(child.uid)
        if not record or record["outcome"] is not None:
            return
        # An early child death can precede the parent's next turn. Preserve the
        # pending transition until that turn captures its actual next state.
        record["outcome"] = survived
        self._finish_birth(child.uid)

    def _finish_birth(self, child_id):
        record = self.birth_transitions.get(child_id)
        if not record or not record["ready"] or record["outcome"] is None:
            return
        self.birth_transitions.pop(child_id)
        f = self.factions[record["faction"]]
        survived = record["outcome"]
        outcome = 0.65 if survived else -0.35
        parent = self._alive.get(record["parent"])
        if survived and parent is not None:
            parent.surviving_children += 1
        f.reward += outcome
        f.score += outcome
        reward = clamp(record["reward"] + outcome, -4, 4)
        if self.learning and record["method"] in ("UCB", "Q-learning"):
            self._credit(
                f,
                record["state"],
                1,
                reward,
                record["next_state"],
                record["terminal"],
                record["next_eligible"],
            )
        self.forecasts.append(
            {
                "tick": self.tick,
                "uid": record["parent"],
                "decision_id": record["decision_id"],
                "method": record["method"],
                "context": record["state"],
                "action": "BUILD",
                "predicted_score": record["predicted"],
                "realized_reward": reward,
                "offspring_survived": survived,
            }
        )
        self.stats["birth_transitions_resolved"] += 1

    def _lookahead(self, a, s, utility):
        """Bounded deterministic three-step rollouts, with a confidence gate.

        Each candidate propagates own/nearest opponent position and estimates
        exposure and reachable ore. No future RNG or true future state is read.
        """
        if "predictive_scores" in globals():
            spent = min(a.energy, 0.03)
            a.energy -= spent
            a.pending_reward -= spent * 0.03
            self.stats["energy_spent"] += spent
            self.stats["planning_energy"] += spent
            scores, reason, a.forecast = predictive_scores(self, a, s, utility)
            return scores, reason
        enemy = s["enemy"]
        scores = list(utility)
        f = self.factions[a.faction]
        observed = sum(f.opponent) - 8
        concentration = max(f.opponent) / sum(f.opponent)
        reliable = observed >= 16 and concentration > 0.25
        if not reliable:
            return scores, "uncertain opponent → robust utility fallback"
        eligible = self.eligible_indices(a, s)
        for i in eligible:
            if scores[i] < -4:
                continue
            x, y = a.x, a.y
            ex = enemy.x if enemy else 0
            ey = enemy.y if enemy else 0
            target = self._target(a, s, ACTIONS[i])
            value = 0.0
            for horizon in range(1, 4):
                if target:
                    dx, dy = target[0] - x, target[1] - y
                    norm = math.hypot(dx, dy)
                    if norm > 0.001:
                        x += dx / norm * 0.85
                        y += dy / norm * 0.85
                if enemy:
                    ex += math.cos(enemy.heading) * 0.40
                    ey += math.sin(enemy.heading) * 0.40
                    proximity = math.hypot(x - ex, y - ey)
                    exposure = max(0, 5 - proximity) / 5
                    value -= exposure * (1 - a.health / 100) * 0.32
                    if i in (2, 5, 6):
                        value += exposure * 0.20 * s["support"]
                food = s["food"]
                if food and i == 0 and math.hypot(x - food.x, y - food.y) < 2:
                    value += min(food.amount, 1.0) * 0.32
                value -= 0.018 * horizon  # planning and locomotion are not free rewards
            scores[i] += value
        self.stats["rollouts"] += len(eligible) * 3
        return scores, "3-step rollout · exposure + reachable ore − cost"

    def _opponent_bias(self, f, s, scores, stat):
        observed = sum(f.opponent) - 8
        concentration = max(f.opponent) / sum(f.opponent)
        if not (observed >= 16 and concentration > 0.25 and s["enemy"]):
            return None
        predicted = max(range(8), key=lambda i: f.opponent[i])
        if predicted in (0, 1):
            scores[2] += 0.65
            scores[6] += 0.8
        elif predicted == 2:
            scores[4] += 0.9
            scores[5] += 0.5
        elif predicted == 3:
            scores[6] += 0.7
        elif predicted in (4, 7):
            scores[5] += 0.9
        self.stats[stat] += 1
        return predicted

    def _choose(self, a, s):
        if self.forecaster:
            self.forecaster.before_decision(a)
        a.forecast = {}
        f = self.factions[a.faction]
        scores = self._utility(a, s)
        method = f.method
        eligible = self.eligible_indices(a, s)
        reason = "realized costs, resources and local force balance"
        # Alarm reflex is absolute and identical for all policies.
        if s["hazard"] is not None and s["hazard"][1] > 0.65:
            index = 3
            reason = "environment avoidance · " + s["hazard"][0]["kind"]
        elif a.health < 16 and s["enemy"] is not None:
            index = 3
            reason = "survival override · low integrity"
        elif method == "Reflex":
            if 1 in eligible:
                index = 1
                reason = "resource threshold → replicate"
            elif s["enemy"] and (a.trophic == "hunter" or dist(a, s["enemy"]) < 6):
                index = 2 if a.health > s["enemy"].health * 0.88 else 3
                reason = "local strength threshold"
            elif 0 in eligible:
                index = 0
                reason = "ore gradient → harvest"
            else:
                index = 3
                reason = "no reachable resource or opponent → wait"
        else:
            if method in ("UCB", "Q-learning") and self.learning:
                p = self._learner(f, s["state"])
                if method == "UCB":
                    for i in eligible:
                        scores[i] = (
                            scores[i] * 0.34
                            + p["mean"][i]
                            + 0.75
                            * math.sqrt(math.log(p["visits"] + 2) / (p["n"][i] + 1))
                        )
                    reason = "context UCB · reward + exploration bonus"
                else:
                    for i in eligible:
                        scores[i] = scores[i] * 0.30 + p["q"][i]
                    reason = "context Q · delayed realized reward"
            elif method == "Opponent":
                predicted = self._opponent_bias(f, s, scores, "opponent_predictions")
                if predicted is not None:
                    reason = f"opponent frequency model → {ACTIONS[predicted]}"
                else:
                    reason = "uncertain opponent → diversified utility"
            elif method == "Lookahead":
                scores, reason = self._lookahead(a, s, scores)
            # Planning is a real cost. Recheck physical gates after it, including
            # the energy threshold for a birth at the edge of affordability.
            eligible = self.eligible_indices(a, s)
            if (
                method in ("UCB", "Q-learning")
                and self.learning
                and self.rng.random() < 0.10
            ):
                index = self.rng.choice(eligible)
                reason += " · explore"
            else:
                index = self._sample_best(eligible, lambda i: scores[i], True)
        a.state = s["state"]
        a.chosen = index
        a.action = ACTIONS[index]
        a.target = self._target(a, s, a.action)
        if method == "Lookahead" and "predictive_target" in globals():
            a.target = predictive_target(self, a, s, a.action, a.target)
        if index == 3 and not s.get("enemy") and not s.get("hazard"):
            reason += " · stationary wait"
        a.trace = {
            "scores": {ACTIONS[i]: round(scores[i], 3) for i in eligible},
            "eligible": [ACTIONS[i] for i in eligible],
            "reason": reason,
            "reward": round(a.last_reward, 4),
            "method": method,
            "context": a.state,
            "hazard_knowledge": "unknown relic outcome"
            if any(
                h["kind"] == "relic" and a.faction not in h["knowledge"]
                for h in self.hazards
            )
            else "observed local hazards",
            "uncertainty": round(1 - max(f.opponent) / sum(f.opponent), 3),
        }
        if self.command:
            a.trace["command"] = self.command.status(a)
        if method == "Lookahead" and a.forecast:
            a.trace["forecast"] = dict(a.forecast)
        a.next_decision = self.tick + 8 + self.rng.randrange(5)
        f.decisions += 1
        self.stats["decisions"] += 1
        a.decision_id = self.stats["decisions"]
        f.decisions_by_action[a.action] = f.decisions_by_action.get(a.action, 0) + 1
        if self.forecaster:
            self.forecaster.note_decision(a)
            if method == "Lookahead" and a.forecast:
                self.forecaster.record(a, a.forecast)
                self.forecaster.record_validation(a, a.forecast)
        for e in s["enemies"]:
            # Many teammates seeing one decision is one observation, not many
            # independent confirmations of predictability.
            if e.decision_id and f.observed_decisions.get(e.uid) != e.decision_id:
                f.opponent[ACTIONS.index(e.action)] += 1
                f.observed_decisions[e.uid] = e.decision_id
                self.stats["unique_opponent_observations"] += 1
        if len(f.observed_decisions) > self.max_agents * 2:
            f.observed_decisions = {
                uid: serial
                for uid, serial in f.observed_decisions.items()
                if uid in self._alive
            }
        # Bounded leaky statistics continue adapting after a regime shift.
        if sum(f.opponent) > 240:
            f.opponent = [1 + (v - 1) * 0.65 for v in f.opponent]

    def _target(self, a, s, action):
        target = self._local_target(a, s, action)
        return self.command.target(a, s, action, target) if self.command else target

    def _local_target(self, a, s, action):
        e = s["enemy"]
        food = s["food"]
        ally = s["ally"]
        if action == "MINE":
            return (food.x, food.y) if food else (50.0, 31.0)
        if action == "BUILD":
            return (a.x, a.y)
        if action == "RETREAT":
            if s.get("hazard") and s["hazard"][1] > 0.65:
                h = s["hazard"][0]
                dx, dy = a.x - h["x"], a.y - h["y"]
                norm = math.hypot(dx, dy)
                if norm < 0.01:
                    dx, dy = math.cos(a.heading), math.sin(a.heading)
                    norm = 1
                return (
                    clamp(a.x + dx / norm * 12, 1, 99),
                    clamp(a.y + dy / norm * 12, 1, 61),
                )
            if not e:
                return (a.x, a.y)
            dx, dy = a.x - e.x, a.y - e.y
            norm = max(0.01, math.hypot(dx, dy))
            return (
                clamp(a.x + dx / norm * 10, 2, 98),
                clamp(a.y + dy / norm * 10, 2, 60),
            )
        if action == "GUARD":
            if ally:
                return ((a.x + ally.x) * 0.5, (a.y + ally.y) * 0.5)
            return (a.x, a.y)
        if action == "ESCORT":
            return (ally.x, ally.y) if ally else (a.x, a.y)
        if not e:
            return (food.x, food.y) if food else (50.0, 31.0)
        if action == "FLANK":
            angle = math.atan2(e.y - a.y, e.x - a.x)
            side = 1 if a.faction % 2 else -1
            return (
                clamp(e.x + math.cos(angle + side * 1.3) * 3, 1, 99),
                clamp(e.y + math.sin(angle + side * 1.3) * 3, 1, 61),
            )
        if action == "RAID":
            # Sample a tied contact once while observing. Hypothetical planning
            # and subsequent execution then share the same observed choice.
            richest = s.get("raid_target")
            if richest is None:
                richest = min(
                    s.get("enemies", ()),
                    key=lambda b: (-b.metal / (1 + dist(a, b)), b.uid),
                    default=None,
                )
            return (richest.x, richest.y) if richest else (a.x, a.y)
        return (e.x, e.y)

    def _move(self, a):
        if not a.target or a.action == "BUILD":
            return
        dx, dy = a.target[0] - a.x, a.target[1] - a.y
        d = math.hypot(dx, dy)
        # Local separation keeps shared ore/escort targets legible. Exact
        # overlaps get opposite pair directions without consuming either RNG.
        vx, vy = (dx / d, dy / d) if d >= 0.2 else (0.0, 0.0)
        clearance = 0.0
        for other in self._near(a, 0.9):
            ox, oy = a.x - other.x, a.y - other.y
            gap = math.hypot(ox, oy)
            if gap < 1e-9:
                pair = (min(a.uid, other.uid), max(a.uid, other.uid))
                angle = ((pair[0] * 73856093) ^ (pair[1] * 19349663)) % 6283 / 1000
                sign = 1 if a.uid < other.uid else -1
                ox, oy = math.cos(angle) * sign, math.sin(angle) * sign
                norm = 1.0
            else:
                norm = gap
            push = 3.0 * (1 - gap / 0.9)
            vx += ox / norm * push
            vy += oy / norm * push
            clearance = max(clearance, 0.9 - gap)
        direction = math.hypot(vx, vy)
        if direction < 1e-9 or (d < 0.2 and not clearance):
            return
        speed = (
            (0.29 if a.trophic == "hunter" else 0.23)
            * a.speed
            * (1.35 if a.action in ("RETREAT", "RAID") else 1)
        )
        if a.action == "GUARD":
            speed *= 0.5
        if a.energy < 20:
            speed *= 0.65
        for h in self.hazards:
            if h["warning"]:
                continue
            hd = math.hypot(a.x - h["x"], a.y - h["y"])
            if hd < h["radius"] and h["kind"] == "ice":
                speed *= 0.34
                self.stats["ice_slow_ticks"] += 1
            if hd < h["radius"] and h["kind"] == "river":
                speed *= 0.7 if abs(a.y - h["y"]) < 1 else 0.42
                self.stats["river_crossing_ticks"] += 1
        amount = min(max(d, clearance), speed)
        oldcell = (int(a.x // 8), int(a.y // 8))
        a.x = clamp(a.x + vx / direction * amount, 0.5, 99.5)
        a.y = clamp(a.y + vy / direction * amount, 0.5, 61.5)
        for h in self.hazards:
            if h["warning"]:
                continue
            hd = math.hypot(a.x - h["x"], a.y - h["y"])
            if h["kind"] == "mountain" and hd < h["radius"] + 1:
                angle = math.atan2(a.y - h["y"], a.x - h["x"]) + 0.028
                a.x = clamp(h["x"] + math.cos(angle) * (h["radius"] + 1), 0.5, 99.5)
                a.y = clamp(h["y"] + math.sin(angle) * (h["radius"] + 1), 0.5, 61.5)
                self.stats["mountain_detours"] += 1
            if h["kind"] == "river" and hd < h["radius"]:
                a.x = clamp(a.x + math.cos(h["heading"]) * 0.065, 0.5, 99.5)
                a.y = clamp(a.y + math.sin(h["heading"]) * 0.065, 0.5, 61.5)
        newcell = (int(a.x // 8), int(a.y // 8))
        if newcell != oldcell:
            bucket = self._grid.get(oldcell, [])
            if a in bucket:
                bucket.remove(a)
            self._grid.setdefault(newcell, []).append(a)
        a.heading = math.atan2(vy, vx)
        spent = min(a.energy, 0.055 * amount)
        a.energy -= spent
        a.pending_reward -= spent * 0.03
        self.stats["energy_spent"] += spent

    def _mine(self, a):
        # Every method may opportunistically gather ore, but dedicated mining
        # is faster, giving tactics an economic opportunity cost.
        rate = 0.55 if a.action == "MINE" else 0.10
        for n in self.nodes:
            if (
                n.amount > 0
                and math.hypot(n.x - a.x, n.y - a.y) < 1.35
                and a.metal < 15
            ):
                amount = min(n.amount, rate, 15 - a.metal)
                n.amount -= amount
                a.metal += amount
                a.pending_reward += amount * 0.09
                self._earn_merit(a, amount * 0.60)
                self.stats["mined_metal"] += amount
                if self.tick % 3 == 0:
                    self._effect("mine", a, n.x, n.y)
                break

    def _build(self, a):
        if a.action != "BUILD":
            return
        if not self.birth_eligible(a):
            self.stats["blocked_births"] += 1
            return
        a.merit -= BIRTH_MERIT
        a.last_birth = self.tick
        a.births += 1
        self.stats["merit_spent"] += BIRTH_MERIT
        # The metal becomes the child's body. Neither ore nor body is deleted.
        a.metal -= BODY_METAL
        a.pending_reward -= 12 * 0.03
        self.stats["energy_spent"] += 12
        share = (a.energy - 12) * 0.45
        a.energy = (a.energy - 12) * 0.55
        genes = list(a.genes)
        for i in range(8):
            if self.rng.random() < 0.20:
                genes[i] = clamp(genes[i] + self.rng.gauss(0, 0.12), 0.45, 1.8)
                self.stats["mutations"] += 1
        child = self._new_crab(
            a.faction,
            a.x + self.rng.uniform(-1.4, 1.4),
            a.y + self.rng.uniform(-1.4, 1.4),
            genes,
            a.generation + 1,
            a.uid,
            trophic=a.trophic,
        )
        child.energy = share
        child.metal = 0.0
        child.health = 55
        child.next_decision = self.tick + 1
        self.stats["births_" + child.trophic] += 1
        self.birth_transitions[child.uid] = {
            "faction": a.faction,
            "parent": a.uid,
            "decision_id": a.decision_id,
            "method": self.factions[a.faction].method,
            "state": a.state,
            "reward": 0.0,
            "ready": False,
            "outcome": None,
            "predicted": a.trace.get("scores", {}).get("BUILD"),
        }
        a.pending_birth = child.uid
        a.next_decision = self.tick + 1
        f = self.factions[a.faction]
        f.births += 1
        self.stats["births"] += 1
        self._effect("birth", a, child.x, child.y)
        # Reward waits for the child to survive 45 ticks, rather than rewarding
        # a costly birth immediately or treating the split as parental failure.
        if self.stats["births"] % 9 == 0:
            self._event(
                f"{f.name} · generation {child.generation} · inherited mutation",
                a.faction,
            )

    def _fight(self, a, b):
        pair = tuple(sorted((a.uid, b.uid)))
        if (
            a.faction == b.faction
            or pair in self._pairs
            or a.cooldown > 0
            or b.health <= 0
            or a.health <= 0
            or a.energy < 0.7
        ):
            return
        self._pairs.add(pair)
        self.stats["encounter_attempts"] += 1
        if self.rng.random() > 0.78:
            return
        a.cooldown = 4
        attack = (
            (4.8 if a.trophic == "hunter" else 3.6)
            * a.damage
            * self.rng.uniform(0.8, 1.2)
        )
        shield = 1.55 if b.action in ("GUARD", "ESCORT") else 1
        # Credit only integrity actually removed, never nominal overkill.
        damage = min(b.health, attack / (b.armor * shield))
        b.health -= damage
        spent = min(a.energy, 0.7)
        a.energy -= spent
        a.pending_reward -= spent * 0.03
        self.stats["energy_spent"] += spent
        a.pending_reward += damage * 0.065
        b.pending_reward -= damage * 0.10
        self._earn_merit(a, damage * 0.045)
        self.stats["damage"] += damage
        self.stats["combats"] += 1
        if a.trophic == "hunter":
            # The victim loses the stolen energy; 20% is dissipated. Prey cannot
            # feed a predator indefinitely, and dead victims cannot be milked.
            stolen = min(b.energy, damage * 0.9, max(0, (100 - a.energy) / 0.8))
            b.energy -= stolen
            a.energy += stolen * 0.8
            a.pending_reward += stolen * 0.025
            b.pending_reward -= stolen * 0.035
            self._earn_merit(a, stolen * 0.035)
            self.stats["predation_energy"] += stolen * 0.8
            self.stats["predation_loss"] += stolen * 0.2
            self.stats["predation_hits"] += 1
        self._effect("strike", a, b.x, b.y)
        if b.health <= 0:
            self.factions[a.faction].kills += 1
            self.stats["kills"] += 1
            self.stats["kills_" + a.trophic] += 1
            self._earn_merit(a, 1.0)
            a.pending_reward += 0.5
            salvage = min(b.metal, 6.0, max(0, 15 - a.metal))
            b.metal -= salvage
            a.metal += salvage
            self.stats["kill_salvage"] += salvage

    def _die(self, a):
        if a.uid not in self._alive:
            return
        if self.forecaster:
            self.forecaster.observe_death(a)
        self._update(a, {"state": a.state}, True)
        if not a.child_paid:
            self._resolve_birth(a, False)
        # Scrap is recoverable; nearest ore node has no capacity clipping.
        n = min(self.nodes, key=lambda n: math.hypot(a.x - n.x, a.y - n.y))
        n.amount += BODY_METAL + a.metal
        n.capacity = max(n.capacity, n.amount)
        self._effect("death", a)
        f = self.factions[a.faction]
        f.losses += 1
        self.stats["deaths"] += 1
        del self._alive[a.uid]
        self.agents.remove(a)

    def spawn_hazard(self, kind=None):
        kind = kind or self.rng.choice(HAZARD_KINDS)
        if kind not in HAZARD_KINDS:
            raise ValueError("Unknown environmental visitor")
        # One visitor per kind; expired memories vanish with their context.
        self.hazards = [h for h in self.hazards if h["kind"] != kind]
        self.hazard_id += 1
        radius = {
            "ice": 6.5,
            "flash": 7.5,
            "worm": 3.3,
            "mountain": 4.5,
            "river": 10.0,
            "alien": 3.8,
            "relic": 4.0,
        }[kind]
        h = {
            "id": self.hazard_id,
            "kind": kind,
            "x": self.rng.uniform(12, 88),
            "y": self.rng.uniform(9, 53),
            "radius": radius,
            "age": 0,
            "ttl": self.rng.randint(300, 520) if kind != "flash" else 100,
            "warning": True,
            "heading": self.rng.random() * math.tau,
            "phase": self.rng.random() * math.tau,
            "knowledge": {},
            "touches": {},
            "_polarity": self.rng.choice((-1, 1)),
        }
        self.hazards.append(h)
        self.timeline.append(
            {"tick": self.tick, "episode": self.episode, "hazard": kind, "id": h["id"]}
        )
        self._event(
            "ENVIRONMENT · "
            + kind.upper()
            + (" · outcome unknown" if kind == "relic" else " · incoming")
        )
        self.stats["hazards_spawned"] += 1
        self.stats["hazard_" + kind] += 1
        return h

    def _hazard_threat(self, a):
        best = None
        best_danger = 0
        for h in self.hazards:
            if h["kind"] in ("mountain", "river", "ice"):
                continue
            d = math.hypot(a.x - h["x"], a.y - h["y"])
            radius = h["radius"] + 3
            if d >= radius:
                continue
            if h["kind"] == "flash" and h["age"] > 64:
                continue
            if h["kind"] == "relic":
                known = h["knowledge"].get(a.faction)
                # An unfamiliar artifact is UNKNOWN, not presumed hostile.
                if known is None or known > 0:
                    continue
            danger = (radius - d) / radius * 2
            if danger > best_danger:
                best, best_danger = h, danger
        return (best, best_danger) if best else None

    def _hazard_step(self):
        if self.auto and self.tick >= self.next_hazard:
            self.spawn_hazard()
            self.next_hazard = self.tick + self.rng.randint(110, 190)
        live = []
        for h in self.hazards:
            h["age"] += 1
            if h["age"] > h["ttl"]:
                continue
            h["warning"] = h["age"] < 35
            kind = h["kind"]
            if kind == "flash":
                h["warning"] = h["age"] < 56
                if h["age"] == 56:
                    self._event("LOCAL FLASH · discharge")
                    self.stats["flash_pulses"] += 1
            if kind in ("worm", "alien") and not h["warning"]:
                if self.agents and h["age"] % 18 == 0:
                    if kind == "alien":
                        target = max(
                            self.agents,
                            key=lambda a: (
                                a.metal / (1 + math.hypot(a.x - h["x"], a.y - h["y"]))
                            ),
                        )
                    else:
                        target = min(
                            self.agents,
                            key=lambda a: math.hypot(a.x - h["x"], a.y - h["y"]),
                        )
                    desired = math.atan2(target.y - h["y"], target.x - h["x"])
                    turn = (desired - h["heading"] + math.pi) % math.tau - math.pi
                    h["heading"] += clamp(turn, -0.3, 0.3) + self.rng.uniform(
                        -0.08, 0.08
                    )
                speed = 0.16 if kind == "worm" else 0.12
                h["x"] += math.cos(h["heading"]) * speed
                h["y"] += math.sin(h["heading"]) * speed
                if h["x"] < 5 or h["x"] > 95:
                    h["heading"] = math.pi - h["heading"]
                if h["y"] < 5 or h["y"] > 57:
                    h["heading"] = -h["heading"]
                h["x"] = clamp(h["x"], 5, 95)
                h["y"] = clamp(h["y"], 5, 57)
                self.stats[kind + "_movement_ticks"] += 1
            live.append(h)
        self.hazards = live

    def _hazard_contact(self, a):
        for h in self.hazards:
            d = math.hypot(a.x - h["x"], a.y - h["y"])
            if d >= h["radius"] or h["warning"]:
                continue
            kind = h["kind"]
            damage = 0.0
            if kind == "flash" and 56 <= h["age"] <= 62:
                damage = 0.9
                self.stats["flash_damage_ticks"] += 1
            elif kind == "worm":
                damage = 0.34
                self.stats["worm_contacts"] += 1
            elif kind == "alien" and self.tick % 6 == 0:
                damage = 1.1
                self.stats["alien_contacts"] += 1
            elif kind == "relic":
                last = h["touches"].get(a.uid, -1000)
                if self.tick - last < 50:
                    continue
                h["touches"][a.uid] = self.tick
                if h["_polarity"] > 0:
                    gain = min(8, 100 - a.energy)
                    a.energy += gain
                    a.health = min(70, a.health + 2)
                    a.pending_reward += gain * 0.035
                    outcome = gain * 0.035
                else:
                    damage = 5.0
                    outcome = -0.5
                previous = h["knowledge"].get(a.faction)
                h["knowledge"][a.faction] = (
                    outcome if previous is None else 0.6 * previous + 0.4 * outcome
                )
                self.stats["relic_observations"] += 1
                if previous is None:
                    self._event(
                        self.factions[a.faction].name
                        + " · relic observed "
                        + ("beneficial" if outcome >= 0 else "hazardous"),
                        a.faction,
                    )
            if damage:
                a.health -= damage
                a.pending_reward -= damage * 0.1
                self.stats["environment_damage"] += damage
                if self.tick % 5 == 0:
                    self._effect("hazard", a, h["x"], h["y"])

    def _earn_merit(self, a, amount):
        amount = max(0.0, amount)
        a.merit = min(14.0, a.merit + amount)
        a.merit_earned += amount
        self.stats["merit_earned"] += amount

    def birth_eligible(self, a):
        return (
            a.age >= 110
            and a.health >= 42
            and a.energy >= 66
            and a.metal >= BODY_METAL
            and a.merit >= BIRTH_MERIT
            and self.tick - a.last_birth >= 220
            and a.pending_birth is None
            and len(self.agents) < self.max_agents
        )

    def _refresh_ecology(self, growth):
        prey = sum(a.trophic == "forager" for a in self.agents)
        hunters = len(self.agents) - prey
        drought = self.mode in ("Scarcity", "Siege")
        rate = 0.022 if drought else 0.080
        inoculum = 0.04 if drought else 0.08
        maximum = rate * FOOD_CAPACITY / 4 + inoculum
        demand = prey * 0.10 + hunters * 0.16
        hungry = sum(a.energy < 15 for a in self.agents)
        # A crisis is observed depletion or actual starvation, not a clock phase.
        crisis = (
            self.nutrient < FOOD_CAPACITY * 0.18
            and demand > maximum * 0.8
            or hungry > max(2, len(self.agents) * 0.25)
        )
        self.ecology = {
            "food": round(self.nutrient, 6),
            "food_capacity": FOOD_CAPACITY,
            "food_ratio": round(self.nutrient / FOOD_CAPACITY, 6),
            "growth": round(growth, 6),
            "demand": round(demand, 6),
            "pressure": round(demand / max(maximum, 0.001), 6),
            "crisis": bool(crisis),
            "prey": prey,
            "hunters": hunters,
            "hungry": hungry,
            "carrying_capacity": round(maximum / 0.12, 2),
        }
        if crisis and not self._crisis:
            self.stats["malthusian_crises"] += 1
            self._event("MALTHUSIAN CRISIS · food / energy overshoot")
        if self._crisis and not crisis:
            self.stats["ecological_recoveries"] += 1
            self._event("ECOLOGICAL RECOVERY · demand falls below supply")
        if crisis:
            self.stats["crisis_ticks"] += 1
        self._crisis = crisis

    def _ecology_step(self):
        drought = self.mode in ("Scarcity", "Siege")
        rate = 0.022 if drought else 0.080
        inoculum = 0.04 if drought else 0.08
        growth = min(
            FOOD_CAPACITY - self.nutrient,
            rate * self.nutrient * (1 - self.nutrient / FOOD_CAPACITY) + inoculum,
        )
        self.nutrient += growth
        self.stats["nutrient_growth"] += growth
        return growth

    def _metabolize(self, a):
        if a.trophic == "forager":
            # A saturating functional response leaves a biological refuge:
            # depleted stock can regrow after consumer numbers collapse.
            access = self.nutrient / (self.nutrient + 18.0)
            intake = min(
                self.nutrient,
                (0.22 if a.action in ("MINE", "GUARD") else 0.17) * access,
                max(0, 100 - a.energy),
            )
            self.nutrient -= intake
            a.energy += intake
            self.stats["nutrient_consumed"] += intake
        cost = 0.16 if a.trophic == "hunter" else 0.10
        spent = min(a.energy, cost)
        a.energy -= spent
        a.pending_reward -= spent * 0.03
        self.stats["energy_spent"] += spent
        if a.energy < 0.05:
            a.hunger_ticks += 1
            a.health -= 0.22
            a.pending_reward -= 0.022
            self.stats["starvation_ticks"] += 1
            if a.health <= 0:
                self.stats["starvation_deaths"] += 1

    def _environment(self):
        if self.mode == "Moving seams":
            for n in self.nodes:
                n.x = clamp(n.x + math.cos(self.tick * 0.008 + n.phase) * 0.022, 4, 96)
                n.y = clamp(n.y + math.sin(self.tick * 0.006 + n.phase) * 0.020, 4, 58)
        # All damaging environmental fields live in hazards, so the renderer
        # and decision sensors see exactly the same geometry.
        self.hazard = (0.0, 0.0, 0.0)
        # Ore shower draws from a finite reserve. Closed Scarcity/Siege do not.
        if (
            self.mode in ("Nugget rush", "Arms race")
            and self.tick % 70 == 0
            and self.reserve > 0
        ):
            amount = min(self.reserve, 28.0)
            self.reserve -= amount
            n = self.rng.choice(self.nodes)
            n.amount += amount
            n.capacity = max(n.capacity, n.amount)
            self.stats["reserve_transfers"] += amount
            self.effects.append(
                {
                    "kind": "meteor",
                    "x": n.x,
                    "y": n.y,
                    "tx": n.x,
                    "ty": n.y,
                    "tick": self.tick,
                    "faction": n.kind % 6,
                }
            )

    def step(self):
        self.tick += 1
        self.episode_tick += 1
        self._pairs.clear()
        self._environment()
        self._hazard_step()
        self._rebuild_grid()
        growth = self._ecology_step()
        if self.command:
            self.command.step()
        turns = list(self.agents)
        self.rng.shuffle(turns)
        for a in turns:
            if a.uid not in self._alive:
                continue
            if a.health <= 0:
                self._die(a)
                continue
            a.age += 1
            a.cooldown = max(0, a.cooldown - 1)
            self._metabolize(a)
            if a.action in ("GUARD", "MINE") and a.energy > 15:
                repair = min(0.045, 70 - a.health)
                if repair > 0:
                    a.health += repair
                    a.energy -= repair * 0.3
                    a.pending_reward -= repair * 0.3 * 0.03
                    self.stats["energy_spent"] += repair * 0.3
            if a.age > 1700:
                a.health -= 0.12
            hx, hy, hr = self.hazard
            if hr and math.hypot(a.x - hx, a.y - hy) < hr:
                a.health -= 0.11
                a.pending_reward -= 0.011
                self.stats["hazard_hits"] += 1
            self._hazard_contact(a)
            if a.health <= 0:
                self._die(a)
                continue
            if self.tick >= a.next_decision:
                sensed = self._sense(a)
                self._update(a, sensed)
                self._choose(a, sensed)
            self._move(a)
            self._mine(a)
            self._build(a)
            if a.action in ("ATTACK", "FLANK", "RAID", "GUARD", "ESCORT"):
                enemies = [b for b in self._near(a, 2.0) if b.faction != a.faction]
                enemy = self._sample_best(
                    enemies,
                    lambda b: (
                        dist(a, b)
                        * (
                            0.72
                            if a.trophic == "hunter" and b.trophic == "forager"
                            else 1
                        )
                    ),
                )
                if enemy:
                    self._fight(a, enemy)
            # Delayed offspring feedback is awarded to the parent's actual
            # reproductive decision only if the parent is still present.
            if a.parent is not None and a.age >= 45 and not a.child_paid:
                a.child_paid = True
                self._resolve_birth(a, True)
                self.stats["surviving_offspring"] += 1
            if self.tick % 3 == 0:
                a.trail.append((a.x, a.y))
            fitness = (
                a.merit_earned + a.surviving_children * 1.5 - a.hunger_ticks * 0.02
            )
            f = self.factions[a.faction]
            if fitness > f.best_fitness:
                f.best_fitness = fitness
                f.best_genes = list(a.genes)
            if a.health <= 0:
                self._die(a)
        # The end-of-tick sweep removes agents killed after their own turn.
        for a in list(self.agents):
            if a.health <= 0:
                self._die(a)
        if self.forecaster:
            self.forecaster.step()
        self._refresh_ecology(growth)
        self.last_ledger_error = self.metal_total() - self.metal_initial
        if abs(self.last_ledger_error) > 1e-7:
            raise AssertionError(f"metal ledger drift {self.last_ledger_error}")
        if self.tick % 10 == 0:
            self.history.append(
                {
                    "tick": self.tick,
                    "episode": self.episode,
                    "populations": [
                        sum(a.faction == i for a in self.agents) for i in range(6)
                    ],
                    "scores": [round(f.score, 3) for f in self.factions],
                    "ecology": dict(self.ecology),
                }
            )
        while self.effects and self.tick - self.effects[0]["tick"] > 36:
            self.effects.popleft()
        if self.auto:
            if self.tick >= self.next_shift:
                self.level = min(6, self.level + 1)
                self.set_mode(self.rng.choice([m for m in MODES if m != self.mode]))
            factions_alive = len({a.faction for a in self.agents})
            if (
                self.episode_tick >= self.episode_ticks
                or not self.agents
                or (factions_alive <= 1 and self.episode_tick > 150)
            ):
                self.advance_episode()

    def snapshot(self):
        populations = [sum(a.faction == i for a in self.agents) for i in range(6)]
        return {
            "version": MODEL_VERSION,
            "seed": self.seed,
            "tick": self.tick,
            "episode": self.episode,
            "episode_tick": self.episode_tick,
            "level": self.level,
            "pending_births": len(self.birth_transitions),
            "mode": self.mode,
            "next_shift": self.next_shift,
            "population": len(self.agents),
            "populations": populations,
            "metal": round(self.metal_total(), 9),
            "metal_initial": self.metal_initial,
            "ledger_error": self.last_ledger_error,
            "reserve": self.reserve,
            "stats": dict(self.stats),
            "ecology": dict(self.ecology),
            "command": self.command.snapshot() if self.command else {},
            "prediction": self.forecaster.snapshot() if self.forecaster else {},
            "hazards": [
                {k: v for k, v in h.items() if k not in ("_polarity", "touches")}
                for h in self.hazards
            ],
            "factions": [
                {
                    "id": f.id,
                    "name": f.name,
                    "method": f.method,
                    "score": f.score,
                    "reward": f.reward,
                    "births": f.births,
                    "kills": f.kills,
                    "losses": f.losses,
                    "decisions": f.decisions,
                    "updates": f.updates,
                    "actions": dict(f.decisions_by_action),
                }
                for f in self.factions
            ],
        }

    def export(self):
        return {
            "model": MODEL_VERSION,
            "config": {
                "seed": self.seed,
                "max_agents": self.max_agents,
                "episode_ticks": self.episode_ticks,
                "auto": self.auto,
                "learning": self.learning,
            },
            "snapshot": self.snapshot(),
            "learners": {f.method: f.policy for f in self.factions},
            "forecasts": list(self.forecasts),
            "timeline": list(self.timeline),
            "episodes": list(self.episodes),
            "history": list(self.history),
            "metadata": {
                "replay": "Replay from seed and same config. Manual set_mode calls are recorded in timeline.",
                "scope": "Shared fictional ecology; no guaranteed learning superiority; bounded histories.",
                "curriculum": "Time-driven complexity unlocks, not measured evidence of improvement.",
                "mutation_status": "New hereditary variants are candidates; none is presumed validated.",
                "confidence": "Learners scoped by mode and level. Unknown relic effects remain unknown until observed.",
                "censoring": "Pending offspring transitions at episode cutoff are counted, not labeled failures.",
                "metal": "Ore + carried metal + 6 per living body + reserve is conserved within each episode.",
                "learning": "Context Q/UCB update from realized harvest, damage, actual dissipated energy costs and delayed offspring reward. Parent-child energy transfer is not a cost.",
                "counters": "Faction counters reset at each episode/method reassignment; episodes retain prior summaries; stats is global cumulative.",
                "evolution": "Inherited action weights mutate at birth; acquired learners are method-level cultural memory.",
                "ecology": "Agent-based Lotka-Volterra-inspired trophic coupling, not the exact ODE. Foragers draw a bounded shared renewable nutrient stock; hunters transfer victim energy with loss. Crises are measured shortages, not scripted kill cycles.",
                "merit": "Birth requires 3.5 spent personal merit from actual ore/combat, maturity, energy, health, metal and recovery. Children inherit no merit; command rank cannot waive this gate.",
            },
        }


def self_check():
    """Model contract checks; callers should also run multi-seed soak tests."""
    results = {}
    a = BattleWorld(seed=31, max_agents=60, episode_ticks=240)
    b = BattleWorld(seed=31, max_agents=60, episode_ticks=240)
    for _ in range(520):
        a.step()
        b.step()
    assert a.export() == b.export(), "same seed replay differs"
    results["deterministic_replay"] = True
    assert a.episode >= 3 and a.stats["learning_updates"] > 0
    results["automatic_rollover_and_learning"] = True
    assert len(a.agents) <= 60 and abs(a.last_ledger_error) < 1e-7
    results["population_cap_and_metal_conservation"] = True
    assert len(a.effects) <= 360 and len(a.history) <= 600 and len(a.timeline) <= 128
    results["bounded_history"] = True
    c = BattleWorld(seed=9, max_agents=24, auto=False, learning=False)
    c.set_mode("Scarcity")
    initial = c.metal_total()
    for _ in range(220):
        c.step()
    assert (
        c.episode == 1
        and c.stats["learning_updates"] == 0
        and abs(c.metal_total() - initial) < 1e-7
    )
    results["closed_resource_and_learning_ablation"] = True
    d = BattleWorld(seed=6, max_agents=6, auto=False)
    x, y = d.agents[:2]
    x.x = x.y = 10
    y.x = 10.8
    y.y = 10
    d._pairs.clear()
    d._fight(x, y)
    state = d.rng.getstate()
    d._fight(y, x)
    assert d.rng.getstate() == state and d.stats["encounter_attempts"] == 1
    results["one_pair_attempt_per_tick"] = True
    # Strict sensing around a bucket boundary includes distant bucket +2.
    x.x, x.y = 7.9, 10
    y.x, y.y = 23.8, 10
    d._rebuild_grid()
    assert y in d._near(x, 16)
    y.x = 23.900001
    d._rebuild_grid()
    assert y not in d._near(x, 16)
    results["complete_strict_spatial_query"] = True
    old = d.metal_total()
    x.metal += 8
    d.reserve -= 8
    x.age = 120
    x.action = "BUILD"
    x.merit = BIRTH_MERIT
    d.max_agents = 7
    d._build(x)
    assert len(d.agents) == 7 and abs(d.metal_total() - old) < 1e-7
    results["birth_metal_transfer"] = True
    child = d.agents[-1]
    child.health = 0
    old = d.metal_total()
    d._die(child)
    assert abs(d.metal_total() - old) < 1e-7
    results["death_scrap_transfer"] = True
    e = BattleWorld(seed=2, max_agents=13, auto=False)
    parent = next(a for a in e.agents if a.faction == 2)
    parent.action = "BUILD"
    parent.chosen = 1
    parent.age = 120
    parent.merit = BIRTH_MERIT
    parent.metal = 8
    parent.trace = {"scores": {"BUILD": 2.9}}
    e.reserve -= 7
    e._build(parent)
    child = e.agents[-1]
    assert child.parent == parent.uid and e.stats["births"] == 1
    birth_state = parent.state
    e._update(parent, {"state": parent.state})
    parent.chosen = 2
    parent.action = "ATTACK"
    e._resolve_birth(child, True)
    p = e._learner(e.factions[2], birth_state)
    assert p["n"][1] == 1 and p["n"][2] == 0
    e._resolve_birth(child, True)
    assert p["n"][1] == 1
    results["delayed_birth_attribution_exactly_once"] = True
    # A failed child can be resolved before the parent's next decision.
    early = BattleWorld(seed=2, max_agents=13, auto=False)
    parent = next(a for a in early.agents if a.faction == 3)
    parent.action = "BUILD"
    parent.chosen = 1
    parent.age = 120
    parent.merit = BIRTH_MERIT
    parent.metal += 7
    early.reserve -= 7
    parent.trace = {"scores": {"BUILD": 2.9}}
    birth_state = parent.state
    early._build(parent)
    child = early.agents[-1]
    early._resolve_birth(child, False)
    early._update(parent, early._sense(parent))
    f = early.factions[parent.faction]
    assert early._learner(f, birth_state)["n"][1] == 1
    assert abs(f.score + 0.71) < 1e-12
    results["early_offspring_loss_credit_and_score"] = True
    # Illegal high Q values cannot manufacture a valid target or bootstrap.
    parent.metal = 0
    parent.trace = {"scores": {"MINE": 1}}
    parent.chosen = 0
    parent.state = "0/1/0"
    sensed = early._sense(parent)
    sensed.update(
        enemy=None, enemies=[], ally=None, allies=[], state="0/1/1", hazard=None
    )
    p = early._learner(f, sensed["state"])
    p["q"][1] = 20
    p["q"][2] = 20
    early._update(parent, sensed)
    assert early._learner(f, "0/1/0")["q"][0] == 0
    early._choose(parent, sensed)
    assert parent.action not in ("BUILD", "ATTACK", "FLANK", "RAID", "ESCORT")
    results["legal_action_selection_and_td_bootstrap"] = True
    hworld = BattleWorld(seed=8, max_agents=12, auto=False)
    probe = hworld.agents[0]
    for kind in HAZARD_KINDS:
        h = hworld.spawn_hazard(kind)
        h["x"] = probe.x
        h["y"] = probe.y
        h["warning"] = False
        h["age"] = 57
        before = probe.health
        hworld.tick = 60
        if kind in ("flash", "worm", "alien"):
            hworld._hazard_contact(probe)
            assert probe.health < before
        elif kind == "relic":
            h["_polarity"] = -1
            assert probe.faction not in h["knowledge"]
            hworld._hazard_contact(probe)
            assert h["knowledge"][probe.faction] < 0
        elif kind in ("ice", "river", "mountain"):
            probe.target = (probe.x + 2, probe.y)
            probe.action = "MINE"
            hworld._move(probe)
    assert (
        hworld.stats["ice_slow_ticks"]
        and hworld.stats["river_crossing_ticks"]
        and hworld.stats["mountain_detours"]
    )
    results["seven_environment_mechanics"] = True
    previous = a.level
    a.advance_episode()
    assert a.level >= previous
    results["monotonic_complexity_curriculum"] = True
    costworld = BattleWorld(seed=21, max_agents=12, auto=False)
    c = costworld.agents[0]
    c.target = (c.x + 3, c.y)
    c.pending_reward = 0
    old = c.energy
    costworld._move(c)
    assert c.energy < old and abs(c.pending_reward + (old - c.energy) * 0.03) < 1e-10
    costworld.factions[0].score = 19
    costworld.factions[0].kills = 7
    costworld.advance_episode()
    assert all(
        f.score == 0 and f.kills == 0 and f.updates == 0 for f in costworld.factions
    )
    assert costworld.episodes[-1]["factions"][0]["score"] == 19
    results["actual_energy_cost_reward"] = True
    results["epoch_method_counters_do_not_mix"] = True
    observed = BattleWorld(seed=12, max_agents=6, auto=False)
    observer, other = observed.agents[:2]
    other.decision_id = 12345
    sensed = observed._sense(observer)
    sensed["enemies"] = [other]
    observed._choose(observer, sensed)
    count = observed.stats["unique_opponent_observations"]
    observed._choose(observer, sensed)
    assert observed.stats["unique_opponent_observations"] == count
    other.decision_id += 1
    observed._choose(observer, sensed)
    assert observed.stats["unique_opponent_observations"] == count + 1
    results["opponent_observation_deduplication"] = True
    return results


"""Bounded local command network; ranks grant coordination, never fertility.

Orders are finite-lived observations, not omniscient tracking. All public read
methods are pure so the renderer cannot change model state or consume its RNG.
"""
import math


class CommandNetwork:
    BROADCAST_TICKS = 24
    DIRECT_RANGE = 22.0
    RELAY_RANGE = 12.0
    SIGHT_RANGE = 16.0
    ORDER_TTL = 70

    def __init__(self, world):
        self.world = world
        self.reset()

    def reset(self):
        self.leaders = {}
        self.members = {}
        self.orders = {}
        self.next_broadcast = self.world.tick

    @staticmethod
    def _distance(a, b):
        return math.hypot(a.x - b.x, a.y - b.y)

    @staticmethod
    def _rank_score(a):
        # Acquired contribution is not inherited and is not spent when a birth
        # occurs. Method names, generation, and elapsed age confer no privilege.
        contribution = max(0.0, getattr(a, "merit_earned", 0.0))
        offspring = max(0, getattr(a, "surviving_children", 0))
        return contribution + 1.5 * offspring + max(0.0, a.health) * 0.012

    def _alive(self, uid):
        a = self.world._alive.get(uid)
        return a if a is not None and a.health > 0 else None

    def _order(self, leader, local):
        """Observe once and freeze a modest, fallible short-term forecast."""
        world = self.world
        enemies = sorted(
            (
                a
                for a in world._near(leader, self.SIGHT_RANGE)
                if a.faction != leader.faction
            ),
            key=lambda a: a.uid,
        )
        support = [a for a in local if self._distance(leader, a) <= self.DIRECT_RANGE]
        avg_energy = sum(a.energy for a in support) / max(1, len(support))
        own_force = sum(max(0.0, a.health) * getattr(a, "damage", 1.0) for a in support)
        enemy_force = sum(
            max(0.0, a.health) * getattr(a, "damage", 1.0) for a in enemies
        )
        # Project near-term exhaustion from observed reserve, rather than wait
        # for starvation. A rally retreats away from the visible threat.
        retreat = enemies and (enemy_force > own_force * 1.25 or avg_energy < 24)
        if retreat:
            ex = sum(a.x for a in enemies) / len(enemies)
            ey = sum(a.y for a in enemies) / len(enemies)
            dx, dy = leader.x - ex, leader.y - ey
            norm = max(0.01, math.hypot(dx, dy))
            kind = "REGROUP"
            target = (leader.x + dx / norm * 8, leader.y + dy / norm * 8)
            reason = "local force disadvantage or forecast energy exhaustion"
        elif enemies:
            # A low-integrity, well supplied victim is economical to intercept.
            prey = min(
                enemies,
                key=lambda a: (
                    self._distance(leader, a) + a.health * 0.07 - a.metal * 0.35,
                    a.uid,
                ),
            )
            horizon = min(16.0, self._distance(leader, prey) / 0.46)
            speed = 0.23 * getattr(prey, "speed", 1.0)
            if prey.action in ("BUILD", "GUARD"):
                speed *= 0.25
            target = (
                prey.x + math.cos(prey.heading) * speed * horizon,
                prey.y + math.sin(prey.heading) * speed * horizon,
            )
            kind = "RAID" if prey.metal >= 4 else "HUNT"
            reason = "observed vulnerable contact; frozen heading extrapolation"
        else:
            # This commander's ore map is local, even though independent agents
            # can retain their ordinary world exploration heuristic.
            nodes = [
                n
                for n in world.nodes
                if n.amount > 0.05 and math.hypot(n.x - leader.x, n.y - leader.y) <= 26
            ]
            if nodes:
                node = min(
                    nodes,
                    key=lambda n: (
                        math.hypot(n.x - leader.x, n.y - leader.y)
                        / (1 + min(20, n.amount) * 0.05),
                        n.x,
                        n.y,
                    ),
                )
                target = (node.x, node.y)
                kind = "FORAGE"
                reason = "rebuild reserves before the next encounter"
            else:
                target = (leader.x, leader.y)
                kind = "REGROUP"
                reason = "no observed target; consolidate without invented intelligence"
        target = (max(1.0, min(99.0, target[0])), max(1.0, min(61.0, target[1])))
        return {
            "kind": kind,
            "target": target,
            "source_uid": leader.uid,
            "issued_tick": world.tick,
            "expires": world.tick + self.ORDER_TTL,
            "reason": reason,
        }

    def step(self):
        world = self.world
        if world.tick < self.next_broadcast:
            return
        self.next_broadcast = world.tick + self.BROADCAST_TICKS
        alive = sorted((a for a in world.agents if a.health > 0), key=lambda a: a.uid)
        living = {a.uid for a in alive}
        # Historical UIDs and orders are removed on every bounded refresh.
        previous = self.members
        self.members = {}
        self.orders = {
            uid: order
            for uid, order in self.orders.items()
            if uid in living
            and order["expires"] > world.tick
            and self._alive(order["source_uid"]) is not None
        }
        old_leaders = self.leaders
        self.leaders = {}
        for faction in range(len(world.factions)):
            members = [a for a in alive if a.faction == faction]
            if not members:
                continue
            ranked = sorted(members, key=lambda a: (-self._rank_score(a), a.uid))
            leader = ranked[0]
            incumbent = self._alive(old_leaders.get(faction))
            if incumbent is not None and self._rank_score(
                incumbent
            ) * 1.2 >= self._rank_score(leader):
                leader = incumbent
            self.leaders[faction] = leader.uid
            if old_leaders.get(faction) != leader.uid:
                world.stats["command_successions"] += 1
                if old_leaders.get(faction) is not None:
                    world._event(
                        f"{world.factions[faction].name} · command succession", faction
                    )
            others = [a for a in ranked if a.uid != leader.uid]
            direct = [
                a for a in others if self._distance(leader, a) <= self.DIRECT_RANGE
            ]
            # One lieutenant per small squad, maximum three relays per faction.
            relay_count = min(3, len(others) // 3)
            relays = direct[:relay_count]
            relay_ids = {a.uid for a in relays}
            issued = self._order(leader, members)
            self.members[leader.uid] = {
                "rank": "commander",
                "leader_uid": None,
                "commander_uid": leader.uid,
                "route": (),
            }
            self.orders[leader.uid] = issued
            for a in others:
                candidates = [
                    r
                    for r in relays
                    if r.uid != a.uid and self._distance(r, a) <= self.RELAY_RANGE
                ]
                # Prefer a squad leader locally, while keeping commander→relay
                # direct. A member can never become its own relay or form cycles.
                relay = (
                    min(candidates, key=lambda r: (self._distance(r, a), r.uid))
                    if candidates
                    else None
                )
                if a.uid in relay_ids:
                    parent, route = leader, (leader.uid,)
                elif relay is not None:
                    parent, route = relay, (leader.uid, relay.uid)
                else:
                    parent, route = leader, (leader.uid,)
                self.members[a.uid] = {
                    "rank": "lieutenant" if a.uid in relay_ids else "member",
                    "leader_uid": parent.uid,
                    "commander_uid": leader.uid,
                    "route": route,
                }
                if self._route_connected(a, self.members[a.uid]):
                    self.orders[a.uid] = dict(issued)
                    world.stats["command_messages"] += 1
                else:
                    # A disconnected unit can finish its last finite mission,
                    # but does not learn this broadcast or the new commander's plan.
                    old = previous.get(a.uid)
                    if old is None or old["commander_uid"] != leader.uid:
                        self.orders.pop(a.uid, None)
        world.stats["command_broadcasts"] += 1

    def _route_connected(self, a, member):
        leader = self._alive(member["commander_uid"])
        if leader is None or leader.faction != a.faction:
            return False
        route = member["route"]
        if not route:
            return leader.uid == a.uid
        if len(route) == 1:
            return self._distance(a, leader) <= self.DIRECT_RANGE
        relay = self._alive(route[1])
        return (
            relay is not None
            and relay.faction == a.faction
            and self._distance(leader, relay) <= self.DIRECT_RANGE
            and self._distance(relay, a) <= self.RELAY_RANGE
        )

    def status(self, a):
        member = self.members.get(a.uid)
        if member is None or self._alive(a.uid) is None:
            return {
                "rank": "member",
                "leader_uid": None,
                "commander_uid": None,
                "order": None,
                "target": None,
                "link": False,
                "ttl": 0,
                "source_uid": None,
                "issued_tick": None,
                "reason": "autonomous",
            }
        order = self.orders.get(a.uid)
        leader = self._alive(member["commander_uid"])
        if (
            order is None
            or order["expires"] <= self.world.tick
            or leader is None
            or order["source_uid"] != member["commander_uid"]
        ):
            order = None
        # A killed relay stops further communication. A surviving commander's
        # already received order remains usable only until its original TTL.
        return {
            "rank": member["rank"],
            "leader_uid": member["leader_uid"],
            "commander_uid": member["commander_uid"],
            "order": order["kind"] if order else None,
            "target": order["target"] if order else None,
            "link": self._route_connected(a, member),
            "ttl": max(0, order["expires"] - self.world.tick) if order else 0,
            "source_uid": order["source_uid"] if order else None,
            "issued_tick": order["issued_tick"] if order else None,
            "reason": order["reason"] if order else "no current command",
        }

    @staticmethod
    def _survival(a, sensed):
        threat = sensed.get("hazard")
        return bool(
            (threat is not None and threat[1] > 0.65)
            or (a.health < 16 and sensed.get("enemy") is not None)
        )

    def bias(self, a, sensed, scores):
        values = list(scores)
        if self._survival(a, sensed):
            return values
        status = self.status(a)
        kind = status["order"]
        if kind is None:
            return values
        # Soft advice respects hard action eligibility and learned preferences.
        # Neither rank nor a broadcast can create reproduction merit.
        strength = 0.45 + 0.55 * min(1.0, status["ttl"] / self.ORDER_TTL)
        if kind in ("HUNT", "RAID"):
            if sensed.get("enemy") is not None:
                values[2] += 0.7 * strength
                values[5] += 0.9 * strength
                values[6] += (1.1 if kind == "RAID" else 0.55) * strength
            else:
                values[4] += 0.85 * strength
                values[7] += 1.0 * strength
        elif kind == "FORAGE":
            values[0] += 0.8 * strength
            values[7] += 0.25 * strength
        elif kind == "REGROUP":
            values[4] += 0.95 * strength
            values[7] += 0.85 * strength
            if sensed.get("enemy") is not None:
                values[3] += 1.0 * strength
        return values

    def target(self, a, sensed, action, default):
        if action in ("BUILD", "RETREAT") or self._survival(a, sensed):
            return default
        status = self.status(a)
        kind, point = status["order"], status["target"]
        if point is None:
            return default
        if kind == "FORAGE" and action == "MINE":
            return point
        if kind == "REGROUP" and action in ("GUARD", "ESCORT"):
            return self._formation(a, point, 2.0)
        if kind in ("HUNT", "RAID") and sensed.get("enemy") is None:
            if action in ("GUARD", "ESCORT") or (
                action == "MINE" and getattr(a, "trophic", "") == "hunter"
            ):
                return self._formation(a, point, 2.6)
        return default

    @staticmethod
    def _formation(a, point, radius):
        # Stable open arcs prevent all squad members piling on one point. No RNG,
        # future world position, or hidden enemy information is consumed.
        angle = (a.uid * 2.399963229728653) % math.tau
        return (
            max(1.0, min(99.0, point[0] + math.cos(angle) * radius)),
            max(1.0, min(61.0, point[1] + math.sin(angle) * radius)),
        )

    def snapshot(self):
        statuses = [self.status(a) for a in self.world.agents if a.health > 0]
        return {
            "leaders": {str(k): v for k, v in self.leaders.items() if self._alive(v)},
            "commanders": sum(s["rank"] == "commander" for s in statuses),
            "lieutenants": sum(s["rank"] == "lieutenant" for s in statuses),
            "linked": sum(s["link"] for s in statuses),
            "orders": {
                kind: sum(s["order"] == kind for s in statuses)
                for kind in ("HUNT", "RAID", "FORAGE", "REGROUP")
            },
            "broadcast_ticks": self.BROADCAST_TICKS,
            "ttl_ticks": self.ORDER_TTL,
            "direct_range": self.DIRECT_RANGE,
            "relay_range": self.RELAY_RANGE,
        }


# Bounded receding-horizon heuristics. No future world state or random draw.
FORECAST_HORIZONS = (30, 90, 180)


def _announced_flash_risk(world, a, target):
    """Known pulse timing and straight-line travel, not future hazard RNG."""
    if not target:
        return 0.0
    dx, dy = target[0] - a.x, target[1] - a.y
    distance = math.hypot(dx, dy)
    speed = (0.29 if getattr(a, "trophic", "forager") == "hunter" else 0.23) * a.speed
    if a.energy < 20:
        speed *= 0.65
    risk = 0.0
    for h in world.hazards:
        if h["kind"] != "flash" or h["age"] > 62:
            continue
        start = max(0.0, 56 - h["age"])
        end = 62 - h["age"]
        for when in (start, (start + end) * 0.5, end):
            fraction = min(1.0, when * speed / max(distance, 0.001))
            x, y = a.x + dx * fraction, a.y + dy * fraction
            if math.hypot(x - h["x"], y - h["y"]) < h["radius"]:
                risk = max(risk, 0.9 * (end - start + 1))
                break
    return risk


def predictive_target(world, a, sensed, action, default):
    """Lead an observed opponent, with uncertainty-limited interception.

    Only the latest visible position/heading enters this estimate. A frozen
    command coordinate is never converted into a remotely tracked organism.
    """
    if action == "MINE" and _announced_flash_risk(world, a, default) > 0:
        # Inspect only eight nearby known deposits: bounded, proactive avoidance.
        alternatives = sorted(
            (n for n in world.nodes if n.amount > 0.05),
            key=lambda n: (
                math.hypot(n.x - a.x, n.y - a.y) / (1 + min(n.amount, 20) * 0.025),
                n.x,
                n.y,
            ),
        )[:8]
        for node in alternatives:
            candidate = (node.x, node.y)
            if _announced_flash_risk(world, a, candidate) == 0:
                return candidate
    enemy = sensed.get("enemy")
    if action == "RAID":
        enemy = sensed.get("raid_target") or enemy
    if enemy is None or action not in ("ATTACK", "FLANK", "RAID"):
        return default
    if (
        action == "RAID"
        and default
        and math.hypot(default[0] - enemy.x, default[1] - enemy.y) > 3
    ):
        return default  # Preserve a frozen goal distinct from the observed contact.
    distance = math.hypot(a.x - enemy.x, a.y - enemy.y)
    if distance < 2.5 or enemy.action == "BUILD":
        return default
    # A bounded lead is robust to turns and the next local replan. No perfect
    # interception oracle: a stationary or turning adversary can fool it.
    trail = tuple(enemy.trail)
    # Trails are visible measured positions sampled every three model ticks.
    # No private intended destination is read, even to guess whether it moves.
    if len(trail) < 2:
        vx = vy = 0.0
    else:
        vx = (trail[-1][0] - trail[-2][0]) / 3.0
        vy = (trail[-1][1] - trail[-2][1]) / 3.0
        measured_speed = math.hypot(vx, vy)
        if measured_speed > 0.55:
            vx *= 0.55 / measured_speed
            vy *= 0.55 / measured_speed
    lead = min(
        18.0,
        distance
        / max(
            0.15,
            (0.29 if getattr(a, "trophic", "forager") == "hunter" else 0.23) * a.speed,
        )
        * 0.28,
    )
    offset_x, offset_y = (
        (default[0] - enemy.x, default[1] - enemy.y) if default else (0.0, 0.0)
    )
    return (
        clamp(enemy.x + vx * lead + offset_x, 1, 99),
        clamp(enemy.y + vy * lead + offset_y, 1, 61),
    )


def _forecast_encounter(
    a,
    enemy,
    own_rate,
    enemy_rate,
    duration,
    reaction,
    own_energy,
    enemy_energy,
    own_gain,
    enemy_gain,
    hunter,
    enemy_hunter,
):
    """At most15 mean-strike intervals; energy is a ledger, never free credit.

    Four-tick intervals approximate reaction/strike frequency, not future RNG.
    Alternate initiative prevents one side always receiving the first move.
    """
    health = [a.health, enemy.health]
    energy = [max(0.0, own_energy), max(0.0, enemy_energy)]
    gains = (own_gain, enemy_gain)
    rates = (own_rate, enemy_rate)
    hunters = (hunter, enemy_hunter)
    damage = [0.0, 0.0]
    costs = [0.0, 0.0]
    stolen = [0.0, 0.0]
    t = 0.0
    turn = 0
    while t < duration and health[0] > 0 and health[1] > 0:
        dt = min(4.0, duration - t)
        for who in (0, 1) if turn % 2 == 0 else (1, 0):
            other = 1 - who
            if health[who] <= 0 or health[other] <= 0:
                break
            if rates[who] <= 0 or energy[who] < 0.7 or (who == 1 and t < reaction):
                continue
            spent = 0.7 * 0.22 * dt
            # The first-bite threshold is strict even though mean cost/damage
            # represent a fractional expected successful strike in this interval.
            energy[who] -= spent
            costs[who] += spent
            hit = min(health[other], rates[who] * dt)
            health[other] -= hit
            damage[who] += hit
            if hunters[who]:
                take = min(
                    energy[other], hit * 0.9, max(0.0, (100 - energy[who]) / 0.8)
                )
                energy[other] -= take
                energy[who] += take * 0.8
                stolen[who] += take
        for who in (0, 1):
            if health[who] > 0:
                energy[who] = clamp(energy[who] + gains[who] * dt, 0.0, 100.0)
        t += dt
        turn += 1
    return (
        damage[0],
        damage[1],
        costs[0],
        stolen[0],
        stolen[1],
        health[1] <= 0,
        health[0] <= 0,
    )


def _forecast_lifetime(
    a,
    enemy,
    action,
    food_path,
    distance,
    speed,
    contact,
    reaction,
    own_rate,
    enemy_rate,
    ore_available=0.0,
):
    """One bounded candidate trajectory, starting after current metabolism.

    The current action runs first. Short validation points are taken after a
    future tick's metabolism/repair but before its action; displayed long points
    are taken after that action. This is a deterministic local approximation,
    not World.step: terrain, other agents and future replanning are not simulated.
    Expected combat stays capped at 60 contact ticks. Death stops every yield
    and expenditure, without discarding benefits already obtained while alive.
    """
    horizons = (30, 90, 180)
    short = (1, 8, 9, 10, 11, 12)
    # An opponent beyond every projected contact cannot affect this candidate.
    # Do not simulate its maintenance or healing on all 180 ticks.
    enemy = enemy if enemy is not None and contact <= horizons[-1] else None
    health = [max(0.0, a.health), max(0.0, enemy.health) if enemy else 0.0]
    energy = [max(0.0, a.energy), max(0.0, enemy.energy) if enemy else 0.0]
    hunters = (a.trophic == "hunter", bool(enemy and enemy.trophic == "hunter"))
    actions = (action, enemy.action if enemy else "RETREAT")
    basal_costs = tuple(0.16 if hunter else 0.10 for hunter in hunters)
    intake_rates = tuple(
        0.22 if item in ("MINE", "GUARD") else 0.17 for item in actions
    )
    can_repair = tuple(item in ("MINE", "GUARD") for item in actions)
    rates = (own_rate, enemy_rate)
    totals = dict(
        ore=0.0,
        spent=0.0,
        dealt=0.0,
        received=0.0,
        stolen=0.0,
        enemy_stolen=0.0,
        kill=0.0,
        hunger_damage=0.0,
        construction=0.0,
    )
    remaining = max(0.0, distance)
    base_speed = speed / (0.65 if a.energy < 20 else 1.0)
    ore_limit = max(0.0, min(ore_available, 15.0 - a.metal))
    # Preserve the original integrated food estimates while sharing one path
    # across every horizon, instead of restarting a dead candidate at each one.
    access = (
        clamp(food_path[30], 0.0, 1.0),
        clamp((90 * food_path[90] - 30 * food_path[30]) / 60, 0.0, 1.0),
        clamp((180 * food_path[180] - 90 * food_path[90]) / 90, 0.0, 1.0),
    )
    points, validation = {}, {}

    def spend(who, requested):
        paid = min(energy[who], max(0.0, requested))
        energy[who] -= paid
        if who == 0:
            totals["spent"] += paid
        return paid

    def state():
        return {
            **totals,
            "energy": energy[0] if health[0] > 0 else 0.0,
            "health": max(0.0, health[0]),
        }

    def metabolism(who, tick):
        if health[who] <= 0:
            return
        if not hunters[who]:
            food = access[0 if tick <= 30 else 1 if tick <= 90 else 2]
            intake = intake_rates[who] * food
            energy[who] += min(max(0.0, 100.0 - energy[who]), intake)
        paid = min(energy[who], basal_costs[who])
        energy[who] -= paid
        if who == 0:
            totals["spent"] += paid
        if energy[who] < 0.05:
            health[who] -= 0.22
            if who == 0:
                totals["hunger_damage"] += 0.22
        if 0 < health[who] < 70 and can_repair[who] and energy[who] > 15:
            repair = min(0.045, 70.0 - health[who])
            health[who] += repair
            spend(who, repair * 0.3)

    def strike(who):
        other = 1 - who
        if (
            health[who] <= 0
            or health[other] <= 0
            or rates[who] <= 0
            or energy[who] < 0.7
        ):
            return
        spend(who, 0.7 * 0.22)
        hit = min(health[other], rates[who])
        health[other] -= hit
        totals["dealt" if who == 0 else "received"] += hit
        if hunters[who]:
            taken = min(energy[other], hit * 0.9, max(0.0, (100.0 - energy[who]) / 0.8))
            energy[other] -= taken
            energy[who] += taken * 0.8
            totals["stolen" if who == 0 else "enemy_stolen"] += taken
        if who == 0 and health[other] <= 0:
            totals["kill"] = 1.0

    for tick in range(181):
        if tick:
            metabolism(0, tick)
            if health[1] > 0:
                metabolism(1, tick)
        if tick in short:
            validation[tick] = state()
        if health[0] > 0:
            if action == "BUILD" and tick == 0:
                paid = spend(0, 12.0)
                totals["construction"] = paid
                energy[0] *= 0.55  # The other 45% is transferred, not dissipated.
            elif action != "BUILD" and remaining >= 0.2:
                moved = min(remaining, base_speed * (0.65 if energy[0] < 20 else 1.0))
                remaining -= moved
                spend(0, moved * 0.055)
            if action == "MINE" and remaining < 1.35:
                totals["ore"] += min(0.55, max(0.0, ore_limit - totals["ore"]))
            if enemy and contact <= tick < contact + 60:
                for who in (0, 1) if tick % 2 == 0 else (1, 0):
                    if who == 0 or tick - contact >= reaction:
                        strike(who)
        if tick in horizons:
            points[tick] = state()
        if health[0] <= 0:
            # No future metabolism, mining, transfers or repairs after death.
            for horizon in horizons:
                points.setdefault(horizon, state())
            for horizon in short:
                validation.setdefault(horizon, state())
            break
    return {"points": points, "validation": validation}


def predictive_scores(world, a, sensed, utility):
    """Bounded receding-horizon correction to the robust local utility.

    Project the known food law and a finite encounter, stopping exposure when
    either side is expected to die. Long projections remain conditional on
    present population and observed opponents, not privileged future state.
    """
    ecology = getattr(world, "ecology", {})
    hunter = getattr(a, "trophic", "forager") == "hunter"
    basal = 0.16 if hunter else 0.10
    stock = max(0.0, float(ecology.get("food", 240.0)))
    capacity = max(1.0, float(ecology.get("food_capacity", 240.0)))
    prey_count = max(0.0, float(ecology.get("prey", 18.0)))
    drought = world.mode in ("Scarcity", "Siege")
    growth_rate, inoculum = (0.022, 0.04) if drought else (0.080, 0.08)
    # Ecology demand includes predator metabolism, not plant consumption.
    # Predict plants from foragers only, with one saturating response. The
    # coarse integration is shared by every candidate (18 steps, never a tree).
    food_path = {}
    access_total = 0.0
    reserve_ticks = 9999.0
    for t in range(10, 181, 10):
        access = stock / (stock + 18.0)
        renewal = growth_rate * stock * (1 - stock / capacity) + inoculum
        stock = clamp(
            stock + 10 * (renewal - prey_count * 0.195 * access), 0.0, capacity
        )
        access_total += (access + stock / (stock + 18.0)) * 0.5 * 10
        if stock / (stock + 18.0) * 0.195 < 0.10 and reserve_ticks == 9999.0:
            reserve_ticks = float(t)
        if t in FORECAST_HORIZONS:
            food_path[t] = access_total / t
    nearest = sensed.get("enemy")
    support = max(0.0, sensed.get("support", 0.0))
    pressure = max(0.0, sensed.get("pressure", 0.0))
    eligible = world.eligible_indices(a, sensed)
    scores = list(utility)
    candidates = {}
    validation_candidates = {}
    ledger = getattr(world, "forecaster", None)
    observations = ledger.validation_count if ledger else 0
    error = ledger.validation_error_sum / observations if observations else None
    # Sparse evidence earns little authority. Observed forecast error reduces
    # future influence continuously; no free reward is granted for predictions.
    trust = 0.25 if observations < 6 else clamp(1.0 / (1.0 + error / 12.0), 0.12, 0.75)
    attack_actions = ("ATTACK", "FLANK", "RAID")
    for index in eligible:
        action = ACTIONS[index]
        enemy = sensed.get("raid_target", nearest) if action == "RAID" else nearest
        if enemy is None:
            enemy = nearest
        target = predictive_target(
            world, a, sensed, action, world._target(a, sensed, action)
        )
        distance = math.hypot(target[0] - a.x, target[1] - a.y) if target else 0.0
        speed = (
            (0.29 if hunter else 0.23)
            * a.speed
            * (1.35 if action in ("RETREAT", "RAID") else 1)
        )
        if action == "GUARD":
            speed *= 0.5
        if a.energy < 20:
            speed *= 0.65
        enemy_distance = math.hypot(a.x - enemy.x, a.y - enemy.y) if enemy else 1000.0
        chasing = action in attack_actions
        defensive = action in ("GUARD", "ESCORT")
        chased = bool(enemy and enemy.action in attack_actions)
        enemy_speed = (
            (
                (0.29 if getattr(enemy, "trophic", "forager") == "hunter" else 0.23)
                * enemy.speed
            )
            if enemy
            else 0.0
        )
        # A local controller revisits the contact before the long horizon.
        contact = (
            max(0.0, enemy_distance - 1.7)
            / max(0.08, speed + (enemy_speed * 0.5 if chased else 0.0))
            if chasing
            else 1e9
        )
        if enemy_distance < 2:
            contact = 0.0
        elif chased:
            closing = enemy_speed - (speed * 0.8 if action == "RETREAT" else 0.0)
            if closing > 0.04:
                contact = min(contact, max(0.0, enemy_distance - 1.7) / closing)
        # Immediate observable weakness/encirclement has firmer evidence than
        # a 180-tick open-loop story. The local utility still stays the anchor.
        local_evidence = bool(
            enemy
            and enemy_distance < 6
            and (
                enemy.health < 18
                or pressure > support + 1.5
                or (hunter and 0.7 < a.energy < 20)
            )
        )
        authority = max(trust, 0.7 if local_evidence else 0.0)
        own_rate = enemy_rate = 0.0
        reaction = 0.0
        if enemy:
            own_rate = (
                0.22
                * (4.8 if hunter else 3.6)
                * a.damage
                / (enemy.armor * (1.55 if enemy.action in ("GUARD", "ESCORT") else 1.0))
                if chasing or defensive
                else 0.0
            )
            reaction = (
                0.0 if enemy.action in attack_actions + ("GUARD", "ESCORT") else 5.0
            )
            enemy_rate = (
                0.22
                * (4.8 if enemy.trophic == "hunter" else 3.6)
                * enemy.damage
                / a.armor
            )
            enemy_rate *= (1 + min(2.0, pressure) * 0.18) / (1 + support * 0.35)
            if defensive:
                enemy_rate /= 1.55
            if action == "FLANK":
                enemy_rate *= 0.85
            if action == "RETREAT":
                enemy_rate *= 0.20
        ore_available = 0.0
        if action == "MINE" and target and world.nodes:
            node = min(
                world.nodes, key=lambda n: math.hypot(n.x - target[0], n.y - target[1])
            )
            if math.hypot(node.x - target[0], node.y - target[1]) <= 1.35:
                ore_available = node.amount
        trajectory = _forecast_lifetime(
            a,
            enemy,
            action,
            food_path,
            distance,
            speed,
            contact,
            reaction,
            own_rate,
            enemy_rate,
            ore_available,
        )
        validation_candidates[action] = [
            {
                "ticks": horizon,
                "energy": round(point["energy"], 3),
                "health": round(point["health"], 3),
            }
            for horizon, point in sorted(trajectory["validation"].items())
        ]
        points = []
        value = 0.0
        for horizon, weight in zip(FORECAST_HORIZONS, (0.50, 0.32, 0.18)):
            point = trajectory["points"][horizon]
            projected_energy, projected_health = point["energy"], point["health"]
            # Same currency as observed feedback; transferred child energy is
            # not dissipated energy. Every cumulative amount stops at death.
            point_value = (
                point["ore"] * 0.09
                + point["dealt"] * 0.065
                + point["stolen"] * 0.025
                + point["kill"] * 0.5
                - point["received"] * 0.10
                - point["spent"] * 0.03
                - point["hunger_damage"] * 0.10
            )
            if action == "BUILD":
                intake = (0.17 * food_path[horizon]) if not hunter else 0.0
                child_energy = (a.energy - 12) * 0.45 + (intake - basal) * 45
                viable = (
                    child_energy > 0.7
                    and projected_health >= 30
                    and (hunter or food_path[90] > 0.35)
                )
                point_value += 1.1 if viable else -2.5
            if projected_health < 15:
                point_value -= (15 - projected_health) * 0.12
            # Distant forecasts get weaker authority, not false certainty.
            confidence = authority / (1.0 + horizon / 100.0)
            value += weight * point_value * (0.55 + 0.45 * confidence)
            points.append(
                {
                    "ticks": horizon,
                    "energy": round(projected_energy, 3),
                    "health": round(projected_health, 3),
                    "confidence": round(confidence, 3),
                }
            )
        scores[index] = utility[index] + clamp(value * 0.45 * authority, -2.8, 2.8)
        candidates[action] = points
    world.stats["forecast_rollouts"] += len(eligible) * len(FORECAST_HORIZONS)
    return (
        scores,
        "30/90/180-tick forecast · short-transition evidence / finite combat / viable heirs",
        {
            "horizons": list(FORECAST_HORIZONS),
            "candidates": candidates,
            "validation_candidates": validation_candidates,
            "food_runway_ticks": round(min(9999.0, reserve_ticks), 1),
            "calibration": {
                "observations": observations,
                "mean_error": None if error is None else round(error, 3),
                "trust": round(trust, 3),
                "basis": "fixed_action_until_next_decision",
            },
            "assumption": "conditional current action and population; replanning can invalidate it",
        },
    )


class ForecastLedger:
    """Keep long descriptive outcomes separate from held-action validation.

    Short points end immediately before the next decision/planning cost. Long
    points remain observable after interventions, but never set confidence.
    Each lane retains at most one pending record per organism and 120 outcomes.
    """

    def __init__(self, world):
        self.world = world
        self.pending = {}
        self.outcomes = deque(maxlen=120)
        self.count = 0
        self.error_sum = 0.0
        self.terminal = 0
        self.validation_pending = {}
        self.validation_outcomes = deque(maxlen=120)
        self.validation_count = 0
        self.validation_error_sum = 0.0
        self.validation_censored = 0
        self.validation_censor_reasons = Counter()
        self.validation_interventions = Counter()

    def _context(self, a):
        return (self.world.mode, self.world.level, a.trophic, self.world.episode)

    def _record_base(self, a):
        return {
            "tick": self.world.tick,
            "action": a.action,
            "decision_id": a.decision_id,
            "target": tuple(a.target) if a.target is not None else None,
            "context": self._context(a),
            "interventions": set(),
        }

    def _mark_interventions(self, record, a):
        if a.decision_id != record["decision_id"]:
            record["interventions"].add("replanned")
        if a.action != record["action"]:
            record["interventions"].add("action_changed")
        target = tuple(a.target) if a.target is not None else None
        if target != record["target"]:
            record["interventions"].add("target_changed")
        if self._context(a) != record["context"]:
            record["interventions"].add("context_changed")

    def _metadata(self, uid, record, point):
        return {
            "uid": uid,
            "made_at": record["tick"],
            "observed_at": self.world.tick,
            "decision_id": record["decision_id"],
            "action": record["action"],
            "horizon": point["ticks"],
            "context": list(record["context"]),
            "interventions": sorted(record["interventions"]),
        }

    @staticmethod
    def _errors(point, a, dead):
        health = 0.0 if dead else a.health
        energy_error = None if dead else abs(point["energy"] - a.energy)
        health_error = abs(point["health"] - health)
        error = health_error if dead else (energy_error + health_error) * 0.5
        return error, energy_error, health_error

    def _censor_validation(self, uid, reason, dead=False):
        record = self.validation_pending.pop(uid, None)
        if record is None:
            return
        self.validation_censored += 1
        self.validation_censor_reasons[reason] += 1
        self.validation_interventions.update(record["interventions"])
        self.world.stats["forecast_validations_censored"] += 1
        self.validation_outcomes.append(
            {
                **self._metadata(uid, record, record["point"]),
                "status": "censored",
                "reason": reason,
                "early_death": dead,
                "energy_error": None,
                "health_error": None,
            }
        )

    def _finish_validation(self, uid, a=None, dead=False):
        record = self.validation_pending.get(uid)
        if record is None:
            return
        if a is not None:
            self._mark_interventions(record, a)
        elapsed = self.world.tick - record["tick"]
        horizon = record["point"]["ticks"]
        if record["interventions"]:
            self._censor_validation(uid, "intervention", dead)
            return
        if elapsed > horizon or (not dead and elapsed != horizon):
            self._censor_validation(
                uid, "early_decision" if elapsed < horizon else "late_observation", dead
            )
            return
        self.validation_pending.pop(uid)
        error, energy_error, health_error = self._errors(record["point"], a, dead)
        self.validation_count += 1
        self.validation_error_sum += error
        self.world.stats["forecast_validations_evaluated"] += 1
        self.validation_outcomes.append(
            {
                **self._metadata(uid, record, record["point"]),
                "status": "evaluated",
                "early_death": dead,
                "actual_energy": None if dead else a.energy,
                "actual_health": 0.0 if dead else a.health,
                "energy_error": None
                if energy_error is None
                else round(energy_error, 3),
                "health_error": round(health_error, 3),
            }
        )

    def before_decision(self, a):
        # Called before _choose spends planning energy or replaces the action.
        self._finish_validation(a.uid, a)

    def observe_death(self, a):
        # Death is absorbing at the promised short horizon. Keep adverse cases.
        record = self.pending.get(a.uid)
        if record is not None:
            self._mark_interventions(record, a)
        self._finish_validation(a.uid, a, dead=True)

    def note_decision(self, a):
        record = self.pending.get(a.uid)
        if record is not None:
            self._mark_interventions(record, a)

    def reset(self):
        self.world.stats["forecasts_censored"] += sum(
            len(r["points"]) for r in self.pending.values()
        )
        for uid, record in self.pending.items():
            for point in record["points"]:
                self.outcomes.append(
                    {
                        **self._metadata(uid, record, point),
                        "status": "censored",
                        "reason": "epoch_reset",
                        "early_death": False,
                        "energy_error": None,
                        "health_error": None,
                    }
                )
        self.pending.clear()
        for uid in tuple(self.validation_pending):
            self._censor_validation(uid, "epoch_reset")

    def record(self, a, forecast):
        if a.uid in self.pending or not isinstance(forecast, dict):
            return
        points = forecast.get("candidates", {}).get(a.action)
        if not points:
            return
        self.pending[a.uid] = {
            **self._record_base(a),
            "points": [dict(p) for p in points],
        }
        self.world.stats["forecasts_registered"] += 1

    def record_validation(self, a, forecast):
        if not isinstance(forecast, dict):
            return
        points = forecast.get("validation_candidates", {}).get(a.action, ())
        horizon = 1 if a.action == "BUILD" else a.next_decision - self.world.tick
        point = next((p for p in points if p["ticks"] == horizon), None)
        if point is None:
            return
        if a.uid in self.validation_pending:
            self._censor_validation(a.uid, "replaced_before_observation")
        self.validation_pending[a.uid] = {**self._record_base(a), "point": dict(point)}
        self.world.stats["forecast_validations_registered"] += 1

    def step(self):
        for uid, record in tuple(self.validation_pending.items()):
            a = self.world._alive.get(uid)
            if a is None or a.health <= 0:
                self._finish_validation(uid, a, dead=True)
            else:
                self._mark_interventions(record, a)
                if self.world.tick >= record["tick"] + record["point"]["ticks"]:
                    # Never compare a post-action state with a pre-action point.
                    self._censor_validation(uid, "missed_decision_boundary")
        for uid, record in tuple(self.pending.items()):
            a = self.world._alive.get(uid)
            dead = a is None or a.health <= 0
            if a is not None:
                self._mark_interventions(record, a)
            due = [
                p
                for p in record["points"]
                if dead or self.world.tick >= record["tick"] + p["ticks"]
            ]
            for p in due:
                error, energy_error, health_error = self._errors(p, a, dead)
                self.count += 1
                self.error_sum += error
                self.terminal += int(dead)
                self.outcomes.append(
                    {
                        **self._metadata(uid, record, p),
                        "status": "evaluated",
                        "early_death": dead,
                        "health_error": round(health_error, 3),
                        "energy_error": None if dead else round(energy_error, 3),
                    }
                )
                record["points"].remove(p)
                self.world.stats["forecasts_evaluated"] += 1
            if not record["points"]:
                self.pending.pop(uid, None)

    def snapshot(self):
        return {
            "pending_agents": len(self.pending),
            "evaluated": self.count,
            "mean_absolute_state_error": None
            if not self.count
            else round(self.error_sum / self.count, 3),
            "early_death_observations": self.terminal,
            "horizons": list(FORECAST_HORIZONS),
            "validation_pending_agents": len(self.validation_pending),
            "validation_evaluated": self.validation_count,
            "validation_censored": self.validation_censored,
            "validation_censor_reasons": dict(self.validation_censor_reasons),
            "validation_interventions": dict(self.validation_interventions),
            "validation_mean_state_error": None
            if not self.validation_count
            else round(self.validation_error_sum / self.validation_count, 3),
            "validation_outcomes": list(self.validation_outcomes),
            "outcomes": list(self.outcomes),
            "boundary": "Long outcomes are descriptive after flagged interventions; confidence uses only fixed-action short segments before the next decision. Death remains adverse evidence.",
        }


import argparse
import json
import sys
import time
from pathlib import Path

# Rendering and interaction: derived from Self-Replicator Observatory's pooled Ink.
# The renderer never consumes the simulation random stream.
import math
import time
from collections import Counter
from functools import lru_cache

VBG = "#050910"
VPANEL = "#09121d"
VLINE = "#203345"
VTEXT = "#e5eff7"
VMUTED = "#7792a6"
VFONT = "DejaVu Sans Mono"


def vclamp(x, lo, hi):
    return min(hi, max(lo, x))


def tint(color, intensity=1.0, base=VBG):
    """Quantized, bounded color cache: no per-leg RGB parsing every frame."""
    return _tint_cached(color, round(vclamp(intensity, 0.0, 1.0) * 64), base)


@lru_cache(maxsize=4096)
def _tint_cached(color, level, base):
    color = color if isinstance(color, str) and len(color) == 7 else "#9abbd0"
    intensity = level / 64
    a = tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(base[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(y + (x - y) * intensity):02x}" for x, y in zip(a, b))


class Ink:
    """Pooled Canvas primitives; can record exact drawing commands headlessly."""

    def __init__(self, canvas=None):
        self.canvas, self.pool, self.used, self.commands = canvas, {}, Counter(), []
        self.layer = "terrain"
        self.command_count = 0
        self.layers = (
            "terrain",
            "hazards",
            "nodes",
            "trails",
            "command",
            "crabs",
            "effects",
            "focus",
            "header",
            "hud",
            "notice",
        )

    def begin(self):
        self.used.clear()
        self.commands.clear()
        self.command_count = 0

    def draw(self, kind, coords, **style):
        coords = tuple(coords)
        self.command_count += 1
        if self.canvas is None:
            self.commands.append((kind, coords, style.copy()))
            return
        key = (self.layer, kind)
        index = self.used[key]
        self.used[key] += 1
        pool = self.pool.setdefault(key, [])
        style = dict(style, state="normal", tags=(self.layer,))
        if index == len(pool):
            item = getattr(self.canvas, "create_" + kind)(*coords, **style)
            pool.append([item, coords, style])
        else:
            item = pool[index]
            if item[1] != coords:
                self.canvas.coords(item[0], *coords)
                item[1] = coords
            if item[2] != style:
                changes = {
                    key: value
                    for key, value in style.items()
                    if item[2].get(key) != value
                }
                args = tuple(
                    value
                    for key, value in changes.items()
                    for value in ("-" + key, value)
                )
                self.canvas.itemconfigure(item[0], **changes)
                item[2] = style

    def end(self):
        if self.canvas:
            for key, pool in self.pool.items():
                for entry in pool[self.used[key] :]:
                    if entry[2].get("state") != "hidden":
                        self.canvas.itemconfigure(entry[0], state="hidden")
                        entry[2] = dict(entry[2], state="hidden")
            for layer in self.layers:
                self.canvas.tag_raise(layer)

    def line(self, *coords, color=VLINE, width=1, dash=(), arrow=False):
        if len(coords) >= 4:
            self.draw(
                "line",
                coords,
                fill=color,
                width=width,
                dash=dash,
                arrow="last" if arrow else "none",
            )

    def rect(self, x, y, w, h, fill="", outline=VLINE, width=1):
        self.draw(
            "rectangle", (x, y, x + w, y + h), fill=fill, outline=outline, width=width
        )

    def circle(self, x, y, r, color=VLINE, fill="", width=1):
        self.draw(
            "oval", (x - r, y - r, x + r, y + r), outline=color, fill=fill, width=width
        )

    def poly(self, points, color=VLINE, fill="", width=1, smooth=False):
        self.draw(
            "polygon", points, outline=color, fill=fill, width=width, smooth=smooth
        )

    def text(self, x, y, text, size=12, color=VTEXT, anchor="nw", width=0, bold=False):
        self.draw(
            "text",
            (x, y),
            text=str(text),
            fill=color,
            anchor=anchor,
            font=(VFONT, -size, "bold" if bold else "normal"),
            width=width,
            justify="left",
        )

    def bar(self, x, y, w, value, color, height=3):
        self.rect(x, y, w, height, fill=VLINE, outline="")
        self.rect(x, y, w * vclamp(value, 0, 1), height, fill=color, outline="")


class BattleView:
    """A visible decision ecology, not a decorative animation of hidden outcomes."""

    def __init__(self, ink):
        self.ink = ink
        self.hitboxes = {}
        self.geometry = None
        self.selected_uid = None
        self.lens = "ECOSYSTEM"
        self.command_status = {}

    def point(self, x, y):
        ox, oy, scale = self.geometry
        return ox + x * scale, oy + y * scale

    def draw(self, world, w, h, focus_uid=None, overlay=True, visual_tick=None):
        ink = self.ink
        ink.begin()
        ink.layer = "terrain"
        self.hitboxes.clear()
        w, h = max(400, w), max(300, h)
        t = world.tick if visual_tick is None else visual_tick
        scale = min((w - 64) / WORLD_W, (h - 220) / WORLD_H)
        self.geometry = ((w - WORLD_W * scale) / 2, 122, scale)
        # Slow visual lenses explain different real model layers without mutating it.
        self.lens = (
            "ECOSYSTEM",
            "COMMAND / CONTROL",
            "TACTICAL INTENT",
            "FEEDBACK",
            "GENEALOGY",
        )[int(t // 300) % 5]
        command = getattr(world, "command", None)
        self.command_status = (
            {a.uid: command.status(a) for a in world.agents}
            if command is not None
            else {}
        )
        ink.rect(0, 0, w, h, fill=VBG, outline="")
        self._terrain(world, t)
        ink.layer = "hazards"
        for hazard in getattr(world, "hazards", ()):
            self._hazard(hazard, t)
        ink.layer = "nodes"
        for node in world.nodes:
            self._node(node, t)
        selected = next((a for a in world.agents if a.uid == focus_uid), None)
        if selected is None and world.agents:
            # A stable rotating observation, independent of model RNG.
            ordered = sorted(world.agents, key=lambda a: a.uid)
            selected = ordered[(int(t // 210) * 13) % len(ordered)]
        self.selected_uid = selected.uid if selected else None
        ink.layer = "trails"
        for a in world.agents:
            self._trail(a, selected is a)
        ink.layer = "command"
        self._command_links(world, selected, t)
        ink.layer = "crabs"
        for a in world.agents:
            self._crab(a, world, t, selected is a)
        ink.layer = "effects"
        self._effects(world, t)
        ink.layer = "focus"
        if selected is not None:
            self._focus(selected, world, t)
        ink.layer = "header"
        self._header(world, w, overlay)
        self._ecology_strip(world, w)
        ink.layer = "hud"
        if overlay:
            self._ribbons(world, w, h)
            # Observation card is compact and alternates out in pure ecology lens.
            if selected is not None and (
                focus_uid is not None or self.lens != "ECOSYSTEM"
            ):
                self._decision_card(selected, world, w, h)
            self._events(world, w, h)
        else:
            ink.text(
                24,
                h - 22,
                "H  telemetry     F  fullscreen     SPACE  pause",
                10,
                VMUTED,
            )
        ink.end()
        return {
            "world_box": (*self.geometry[:2], WORLD_W * scale, WORLD_H * scale),
            "selected_uid": self.selected_uid,
            "lens": self.lens,
            "primitives": ink.command_count,
            "hitboxes": dict(self.hitboxes),
        }

    def _terrain(self, world, t):
        i = self.ink
        ox, oy, s = self.geometry
        ww, hh = WORLD_W * s, WORLD_H * s
        i.rect(ox - 13, oy - 13, ww + 26, hh + 26, fill="#07111b", outline="#102334")
        i.rect(ox, oy, ww, hh, fill="#0a1016", outline="#294051")
        # Quiet contour field, deterministic trigonometric geometry rather than assets.
        for row in range(13):
            coords = []
            for col in range(25):
                wx = col * WORLD_W / 24
                wy = row * WORLD_H / 12
                wave = 0.65 * math.sin(wx * 0.14 + row * 0.65) + 0.35 * math.sin(
                    wx * 0.41 - row
                )
                px, py = self.point(wx, vclamp(wy + wave, 0, WORLD_H))
                coords.extend((px, py))
            i.line(*coords, color="#13202a")
        for n in range(70):
            x = (n * 37.731 + world.seed * 0.137) % WORLD_W
            y = (n * n * 3.178 + world.seed * 0.041) % WORLD_H
            px, py = self.point(x, y)
            i.line(px, py, px + 1.8, py, color="#263341")
        for x, y, dx, dy in (
            (ox, oy, 1, 1),
            (ox + ww, oy, -1, 1),
            (ox, oy + hh, 1, -1),
            (ox + ww, oy + hh, -1, -1),
        ):
            i.line(x, y + dy * 15, x, y, x + dx * 15, y, color="#688698", width=1)
        i.text(
            ox + ww - 9,
            oy + hh - 16,
            "METAL / MATTER / MEMORY",
            9,
            "#4f6575",
            anchor="ne",
        )

    def _node(self, node, t):
        if node.amount <= 0.001:
            return
        i = self.ink
        x, y = self.point(node.x, node.y)
        scale = self.geometry[2]
        fraction = vclamp(node.amount / max(0.01, node.capacity), 0, 1)
        r = (1.5 + math.sqrt(fraction) * 2.8) * max(0.8, scale / 10)
        color = "#9dafc0" if getattr(node, "kind", "") == "salvage" else "#d5bf7d"
        if fraction > 0.45:
            i.circle(x, y, r + 5, tint(color, 0.12))
        points = []
        for j in range(6):
            a = j * math.pi / 3 + 0.2
            points.extend((x + math.cos(a) * r, y + math.sin(a) * r))
        i.poly(points, color=tint(color, 0.5 + 0.45 * fraction), fill=tint(color, 0.18))
        i.line(
            x - r * 0.4, y + r * 0.2, x + r * 0.25, y - r * 0.45, color=tint(color, 0.9)
        )

    def _trail(self, a, selected):
        path = list(getattr(a, "trail", ()))[-8:]
        color = tint(FACTION_COLORS[a.faction], 0.42 if selected else 0.23)
        points = []
        previous = None
        for p in path:
            if previous and (
                abs(p[0] - previous[0]) > WORLD_W / 2
                or abs(p[1] - previous[1]) > WORLD_H / 2
            ):
                self.ink.line(*points, color=color, width=2 if selected else 1)
                points = []
            points.extend(self.point(*p))
            previous = p
        self.ink.line(*points, color=color, width=2 if selected else 1)

    def _command_links(self, world, selected, t):
        """Draw current radio routes, never guessed command membership lines."""
        if selected is None or not self.command_status:
            return
        i = self.ink
        alive = getattr(world, "_alive", {})
        selected_status = self.command_status.get(selected.uid, {})
        full = self.lens == "COMMAND / CONTROL"
        routes = []
        for a in world.agents:
            if a.faction != selected.faction:
                continue
            status = self.command_status.get(a.uid, {})
            leader = alive.get(status.get("leader_uid"))
            if not status.get("link") or leader is None or leader.uid == a.uid:
                continue
            if full or a is selected or leader is selected:
                routes.append((a, leader))
        # A deliberately small observational layer even at the maximum population.
        for a, leader in routes[:14]:
            x, y = self.point(a.x, a.y)
            lx, ly = self.point(leader.x, leader.y)
            color = FACTION_COLORS[a.faction]
            i.line(lx, ly, x, y, color=tint(color, 0.31), dash=(2, 5))
            phase = (t * 0.018 + a.uid * 0.17) % 1
            i.circle(
                lx + (x - lx) * phase,
                ly + (y - ly) * phase,
                1.6,
                color=tint(color, 0.8),
                fill=tint(color, 0.7),
            )
        target = selected_status.get("target")
        if full and target and selected_status.get("order"):
            x, y = self.point(*target)
            color = tint(
                FACTION_COLORS[selected.faction],
                0.65 if selected_status.get("link") else 0.25,
            )
            i.line(x - 5, y, x + 5, y, color=color)
            i.line(x, y - 5, x, y + 5, color=color)
            i.text(x + 8, y - 7, selected_status["order"], 8, color)

    def _crab(self, a, world, t, selected):
        i = self.ink
        x, y = self.point(a.x, a.y)
        s = self.geometry[2]
        color = FACTION_COLORS[a.faction]
        hunter = getattr(a, "trophic", "forager") == "hunter"
        r = max(5.0, min(11.0, s * 0.68 + getattr(a, "metal", 0) * 0.025)) * (
            1.10 if hunter else 1.0
        )
        heading = getattr(a, "heading", 0.0)
        co, si = math.cos(heading), math.sin(heading)

        def p(u, v):
            return x + (u * co - v * si) * r, y + (u * si + v * co) * r

        movement = math.sin(t * 0.35 + a.uid * 1.618) * 0.19
        if a.action in ("ATTACK", "FLANK", "RAID"):
            i.circle(x, y, r * 1.7, tint(color, 0.18), width=2)
        for side in (-1, 1):
            legs = []
            for leg in range(3):
                start = p((leg - 1) * 0.48, side * 0.65)
                knee = p((leg - 1) * 0.65 + movement * side, side * 1.25)
                foot = p((leg - 1) * 0.92 - 0.22 + movement * side, side * 1.65)
                # One polyline per side retains three jointed legs; return strokes
                # overlap exactly and the connecting roots sit underneath the shell.
                legs.extend((*start, *knee, *foot, *knee, *start))
            i.line(*legs, color=tint(color, 0.72), width=1.2)
            reach = (
                (1.9 if hunter else 1.5)
                if a.action in ("ATTACK", "MINE", "BUILD")
                else (1.55 if hunter else 1.25)
            )
            wrist = p(reach, side * 0.95)
            i.line(
                *p(0.45, side * 0.5),
                *wrist,
                *p(reach + 0.45, side * 0.72),
                *wrist,
                *p(reach + 0.35, side * 1.28),
                color=color,
                width=1.9 if hunter else 1.2,
            )
        body = []
        for u, v in (
            (-0.8, -0.42),
            (-0.45, -0.82),
            (0.55, -0.66),
            (0.9, 0),
            (0.55, 0.66),
            (-0.45, 0.82),
            (-0.8, 0.42),
        ):
            body.extend(p(u, v))
        i.poly(body, color=color, fill=tint(color, 0.3), width=1.3)
        if hunter:
            i.poly(
                (*p(-0.7, -0.32), *p(-1.25, 0), *p(-0.7, 0.32)),
                color=tint(color, 0.85),
                fill=tint(color, 0.4),
            )
        i.line(*p(-0.48, 0), *p(0.5, 0), color=tint(color, 0.85))
        i.line(*p(0.7, -0.34), *p(0.7, 0.34), color="#d5fbff", width=1.6)
        self.hitboxes[a.uid] = (x, y, r * 2.5)
        rank = self.command_status.get(a.uid, {}).get("rank", "member")
        if rank == "commander":
            # Three-point crown is a command role, not reproductive eligibility.
            cy = y - r * 2.2
            i.line(
                x - 5,
                cy + 3,
                x - 6,
                cy - 3,
                x - 2,
                cy,
                x,
                cy - 5,
                x + 2,
                cy,
                x + 6,
                cy - 3,
                x + 5,
                cy + 3,
                x - 5,
                cy + 3,
                color="#e6d6a8",
                width=1.4,
            )
        elif rank == "lieutenant":
            cy = y - r * 2.1
            i.line(
                x - 4,
                cy + 1,
                x,
                cy - 2,
                x + 4,
                cy + 1,
                color=tint(color, 0.9),
                width=1.2,
            )
            i.line(x - 4, cy + 4, x, cy + 1, x + 4, cy + 4, color=tint(color, 0.7))
        if self.lens == "TACTICAL INTENT" and a.target and (selected or a.uid % 5 == 0):
            tx, ty = self.point(*a.target)
            if abs(tx - x) < WORLD_W * s / 2 and abs(ty - y) < WORLD_H * s / 2:
                i.line(x, y, tx, ty, color=tint(color, 0.34), dash=(3, 6), arrow=True)
        if self.lens == "GENEALOGY" and getattr(a, "generation", 0) > 0:
            i.circle(x, y, r + 3 + min(a.generation, 8) * 0.25, color=tint(color, 0.35))

    def _focus(self, a, world, t):
        i = self.ink
        x, y = self.point(a.x, a.y)
        r = max(14.0, self.geometry[2] * 1.2)
        color = FACTION_COLORS[a.faction]
        for j in range(4):
            angle = t * 0.009 + j * math.pi / 2
            p = (x + math.cos(angle) * r, y + math.sin(angle) * r)
            q = (x + math.cos(angle + 0.35) * r, y + math.sin(angle + 0.35) * r)
            i.line(*p, *q, color=tint(color, 0.85), width=2)
        i.text(x + r + 4, y - r - 4, f"#{a.uid}  {a.action}", 9, color)

    def _hazard(self, z, t):
        i = self.ink
        x, y = self.point(z["x"], z["y"])
        r = float(z.get("radius", 4)) * self.geometry[2]
        age, ttl = z.get("age", 0), max(1, z.get("ttl", 100))
        kind = z.get("kind")
        if kind == "ice":
            points = []
            for n in range(12):
                a = n * math.pi / 6
                rr = r * (1 if n % 2 else 0.87)
                points.extend((x + math.cos(a) * rr, y + math.sin(a) * rr))
            i.poly(points, color="#497787", fill="#102c3a", width=1)
            for n in range(6):
                a = n * math.pi / 3
                xx, yy = x + math.cos(a) * r * 0.83, y + math.sin(a) * r * 0.83
                i.line(x, y, xx, yy, color="#366178")
                for d in (-0.3, 0.3):
                    i.line(
                        x + math.cos(a) * r * 0.5,
                        y + math.sin(a) * r * 0.5,
                        x + math.cos(a + d) * r * 0.67,
                        y + math.sin(a + d) * r * 0.67,
                        color="#558b9c",
                    )
            i.text(x, y + r + 5, "ICE / slow field", 9, "#7eb8c8", anchor="n")
        elif kind == "flash":
            warning = z.get("warning", False)
            # Telegraph intensity is local and bounded; never flash the full screen.
            discharging = 56 <= age <= 62
            color = "#d9a35b" if warning else "#c8b9f0"
            if age > 62:
                color = tint(color, 0.35)
            i.circle(x, y, r, tint(color, 0.6), width=1)
            i.circle(x, y, r * 0.87, tint(color, 0.2))
            for n in range(9):
                a = n * math.tau / 9 + t * 0.012
                coords = []
                for k in range(4):
                    aa = a + math.sin(k * 2 + n) * 0.1
                    rr = r * (0.2 + k * 0.24)
                    coords.extend((x + math.cos(aa) * rr, y + math.sin(aa) * rr))
                i.line(*coords, color=tint(color, 0.35 if warning else 0.8), width=1.2)
            i.text(
                x,
                y + r + 5,
                "CHARGE / avoid"
                if warning
                else ("ARC / discharge" if discharging else "RESIDUAL / safe"),
                9,
                color,
                anchor="n",
            )
        elif kind == "worm":
            heading = z.get("heading", 0.0)
            # The drawn body follows the real hazard's heading and footprint.
            co, si = math.cos(heading), math.sin(heading)
            for n in range(10, -1, -1):
                sway = math.sin(t * 0.055 - n * 0.58) * r * 0.17
                cx = x - co * n * r * 0.3 - si * sway
                cy = y - si * n * r * 0.3 + co * sway
                rr = r * (0.28 + 0.055 * n) if n < 4 else r * (0.56 - (n - 4) * 0.05)
                rr = max(r * 0.16, rr)
                i.circle(cx, cy, rr + 4, color="#44311e", fill="#1d1c17", width=2)
                i.circle(cx, cy, rr, color="#ae8854", fill="#302b20", width=1.5)
            i.circle(x, y, r * 0.47, color="#e0ba78", fill="#080b0f", width=2)
            for n in range(12):
                a = n * math.tau / 12 + t * 0.01
                i.line(
                    x + math.cos(a) * r * 0.42,
                    y + math.sin(a) * r * 0.42,
                    x + math.cos(a + 0.1) * r * 0.27,
                    y + math.sin(a + 0.1) * r * 0.27,
                    color="#c9a66e",
                )
            i.circle(x, y, r, color="#5b482b")
            i.line(
                x + co * r,
                y + si * r,
                x + co * r * 2.1,
                y + si * r * 2.1,
                color="#695631",
                dash=(3, 5),
                arrow=True,
            )
            i.text(x, y + r + 7, "SANDWORM / threat ring", 9, "#c6a66f", anchor="n")
        elif kind == "mountain":
            i.circle(x, y, r + self.geometry[2], color="#344655")
            # Craggy silhouettes with visible saddle routes, not solid UI rectangles.
            points = (
                x - r,
                y + r * 0.5,
                x - r * 0.65,
                y - r * 0.13,
                x - r * 0.41,
                y + r * 0.04,
                x - r * 0.12,
                y - r * 0.8,
                x + r * 0.16,
                y - r * 0.28,
                x + r * 0.36,
                y - r * 0.52,
                x + r * 0.77,
                y + r * 0.1,
                x + r,
                y + r * 0.5,
            )
            i.poly(points, color="#607a8d", fill="#182733", width=1.5)
            i.line(
                x - r * 0.12,
                y - r * 0.8,
                x - r * 0.29,
                y - r * 0.35,
                x - r * 0.12,
                y - r * 0.43,
                x + r * 0.02,
                y - r * 0.29,
                x + r * 0.07,
                y - r * 0.42,
                color="#b4d1db",
                width=1.4,
            )
            i.line(
                x - r * 0.12, y - r * 0.8, x + r * 0.05, y + r * 0.47, color="#3c5e74"
            )
            i.line(
                x + r * 0.36, y - r * 0.52, x + r * 0.51, y + r * 0.48, color="#425c6b"
            )
            for n in range(3):
                i.line(
                    x - r * 0.8 + n * 4,
                    y + r * (0.6 + n * 0.1),
                    x + r * 0.85 - n * 4,
                    y + r * (0.6 + n * 0.1),
                    color=tint("#71838a", 0.3 - n * 0.06),
                )
        elif kind == "river":
            # The model's current is a circular basin with a horizontal shallow ford.
            # Show that exact footprint instead of implying an impassable river wall.
            heading = z.get("heading", 0.0)
            i.circle(x, y, r, color="#285b70", fill="#102531", width=1.4)
            for n in range(5):
                rr = r * (0.2 + n * 0.16)
                coords = []
                for k in range(18):
                    angle = k * math.tau / 17 + t * 0.01 + n * 0.35
                    wave = rr + math.sin(angle * 3 + t * 0.018) * r * 0.04
                    coords.extend(
                        (x + math.cos(angle) * wave, y + math.sin(angle) * wave)
                    )
                i.line(*coords, color=tint("#5eaebc", 0.25 + n * 0.07))
            ford = self.geometry[2]
            i.line(
                x - r * 0.93,
                y - ford,
                x + r * 0.93,
                y - ford,
                color="#70a8ae",
                dash=(3, 6),
            )
            i.line(
                x - r * 0.93,
                y + ford,
                x + r * 0.93,
                y + ford,
                color="#70a8ae",
                dash=(3, 6),
            )
            i.line(
                x - math.cos(heading) * r * 0.35,
                y - math.sin(heading) * r * 0.35,
                x + math.cos(heading) * r * 0.35,
                y + math.sin(heading) * r * 0.35,
                color="#8cd9d7",
                arrow=True,
            )
        elif kind == "alien":
            heading = z.get("heading", 0.0)
            for n in range(5, 0, -1):
                xx = x - math.cos(heading) * n * r * 0.29
                yy = y - math.sin(heading) * n * r * 0.29
                i.circle(xx, yy, r * 0.4, tint("#aaffcb", 0.2 / n))
            for layer in range(3):
                pts = []
                for n in range(5):
                    angle = (
                        n * math.tau / 5 + t * 0.009 * (1 if layer % 2 else -1) + layer
                    )
                    rr = r * (0.35 + layer * 0.23)
                    pts.extend((x + math.cos(angle) * rr, y + math.sin(angle) * rr))
                i.poly(pts, color=tint("#b9ffcf", 0.9 - layer * 0.22), width=1.5)
            i.circle(x, y, r * 0.13, color="#e5ffe7", fill="#7ee9b2")
            i.circle(x, y, r, color="#244c3b")
        elif kind == "relic":
            # Impossible machine traces: a broken orbital scaffold around an inert core.
            i.circle(x, y, r * 0.65, color="#54426e")
            i.circle(x, y, r * 0.91, color="#2d283d")
            for n in range(8):
                angle = n * math.tau / 8 + z.get("phase", 0)
                inner, outer = r * 0.49, r * (0.82 if n % 2 else 1)
                i.line(
                    x + math.cos(angle) * inner,
                    y + math.sin(angle) * inner,
                    x + math.cos(angle) * outer,
                    y + math.sin(angle) * outer,
                    color="#9b80bf",
                    width=2,
                )
                i.circle(
                    x + math.cos(angle) * outer,
                    y + math.sin(angle) * outer,
                    2,
                    color="#c6a4ed",
                    fill="#675b81",
                )
            i.poly(
                (x, y - r * 0.26, x + r * 0.21, y, x, y + r * 0.26, x - r * 0.21, y),
                color="#dbb7fe",
                fill="#342540",
                width=1.3,
            )
            i.text(x, y + r + 5, "RELIC / unknown", 9, "#b499d0", anchor="n")
        if kind in ("ice", "flash", "worm", "alien", "relic"):
            i.bar(x - r * 0.5, y - r - 5, r, 1 - age / ttl, "#5b899e", 2)

    def _effects(self, world, t):
        i = self.ink
        for e in list(getattr(world, "effects", ()))[-85:]:
            age = world.tick - e.get("tick", world.tick)
            if age > 25 or age < 0:
                continue
            color = FACTION_COLORS[int(e.get("faction", 0)) % len(FACTION_COLORS)]
            x, y = self.point(e.get("x", 0), e.get("y", 0))
            strength = max(0.0, 1 - age / 25)
            kind = e.get("kind", "")
            if (
                kind in ("attack", "fight", "hit", "raid", "strike")
                and e.get("tx") is not None
            ):
                tx, ty = self.point(e["tx"], e["ty"])
                if abs(tx - x) < WORLD_W * self.geometry[2] / 2:
                    i.line(x, y, tx, ty, color=tint(color, 0.12 * strength), width=5)
                    i.line(x, y, tx, ty, color=tint(color, 0.9 * strength), width=1.3)
                    i.circle(tx, ty, 2 + age * 0.4, tint("#ffaf9c", strength * 0.7))
            elif kind in ("birth", "build", "mutation"):
                rr = 4 + age * 0.7
                points = []
                for n in range(6):
                    a = n * math.pi / 3 + age * 0.025
                    points.extend((x + math.cos(a) * rr, y + math.sin(a) * rr))
                i.poly(points, color=tint(color, strength * 0.8))
                i.circle(x, y, rr * 0.65, tint(color, strength * 0.4))
            elif kind in ("death", "salvage"):
                for n in range(5):
                    a = n * math.tau / 5
                    i.line(
                        x + math.cos(a) * age * 0.6,
                        y + math.sin(a) * age * 0.6,
                        x + math.cos(a) * (age * 0.6 + 3),
                        y + math.sin(a) * (age * 0.6 + 3),
                        color=tint(color, strength * 0.7),
                    )
            elif kind in ("mine", "harvest") and age < 8:
                i.circle(x, y, 2 + age * 0.7, tint("#d8cc99", strength * 0.45))

    def _header(self, world, w, overlay):
        i = self.ink
        i.text(27, 20, "C H I T I N", 25, "#ecf4fa", bold=True)
        i.text(28, 54, "THE ISLAND LEARNS", 10, "#7fa8bf")
        i.line(234, 20, 234, 63, color="#2b4254")
        i.text(253, 20, str(world.mode).upper(), 15, "#b8d3e3", bold=True)
        details = (
            f"EPOCH {world.episode:03d}   COMPLEXITY {world.level}/6   TICK {world.tick:,}"
            if w >= 1100
            else f"E{world.episode:03d}  L{world.level}/6  T{world.tick:,}"
        )
        i.text(253, 47, details, 10, VMUTED)
        pop = len(world.agents)
        i.text(w - 28, 18, f"{pop:03d}  ALIVE", 17, "#cce8eb", anchor="ne", bold=True)
        lens = f"{self.lens}   /   SEED {world.seed}" if w >= 1100 else self.lens
        i.text(w - 28, 44, lens, 10, VMUTED, anchor="ne")
        if overlay:
            i.text(
                w - 28,
                65,
                "SPACE pause · F full · H quiet · M mode · N epoch · E export",
                9,
                "#5b7a8e",
                anchor="ne",
            )

    def _ecology_strip(self, world, w):
        i = self.ink
        ecology = getattr(world, "ecology", {})
        if not ecology:
            return
        prey, hunters = ecology.get("prey", 0), ecology.get("hunters", 0)
        food = vclamp(ecology.get("food_ratio", 0.0), 0, 1)
        pressure = ecology.get("pressure", 0.0)
        crisis = bool(ecology.get("crisis"))
        i.rect(25, 81, w - 50, 26, fill="#0a151c", outline="#1b303a")
        i.text(36, 88, f"FORAGERS {prey:02d}", 10, "#80d8ba")
        i.text(143, 88, f"HUNTERS {hunters:02d}", 10, "#ffac82")
        i.text(245, 88, f"FOOD {food:.0%}", 10, "#d4cf91")
        i.bar(318, 91, 46, food, "#b3bf79", 4)
        i.text(
            381,
            88,
            f"LOAD {pressure:.1f}×",
            10,
            "#ff9e83" if pressure > 1 else "#9fbacb",
        )
        label = "FAMINE" if crisis else "ECOSYSTEM"
        i.text(482, 88, label, 10, "#ff806d" if crisis else "#779596", bold=crisis)
        # Actual populations, not an ornamental Lotka–Volterra sine wave.
        history = list(getattr(world, "history", ()))[-56:]
        rows = [
            row["ecology"] for row in history if isinstance(row.get("ecology"), dict)
        ]
        if len(rows) >= 2 and w >= 760:
            left, width = max(590, w - 190), min(145, w - 635)
            scale = max(
                1, max(max(row.get("prey", 0), row.get("hunters", 0)) for row in rows)
            )
            for name, color in (("prey", "#80d8ba"), ("hunters", "#ffac82")):
                coords = []
                for n, row in enumerate(rows):
                    coords.extend(
                        (
                            left + n * width / (len(rows) - 1),
                            102 - row.get(name, 0) * 16 / scale,
                        )
                    )
                i.line(*coords, color=color, width=1.2)

    def _ribbons(self, world, w, h):
        i = self.ink
        gap, left = 8, 25
        cw = (w - 50 - 5 * gap) / 6
        y = h - 76
        pops = Counter(a.faction for a in world.agents)
        history = list(getattr(world, "history", ()))[-45:]
        for f in world.factions:
            x = left + f.id * (cw + gap)
            color = f.color
            i.rect(x, y, cw, 58, fill=VPANEL, outline="#172b39")
            i.rect(x, y, 2, 58, fill=color, outline="")
            i.text(x + 10, y + 7, f.method.upper(), 10, color, bold=True)
            tally = (
                f"{pops[f.id]:02d} alive  ·  {f.kills} K  /  {f.births} B"
                if cw >= 170
                else f"{pops[f.id]:02d} · {f.kills}K / {f.births}B"
            )
            i.text(x + 10, y + 24, tally, 9, "#a6bac6")
            i.text(x + 10, y + 40, f"R {f.reward:+.1f}  ·  Δ {f.updates}", 9, VMUTED)
            if len(history) >= 2 and cw >= 160:
                vals = [row.get("populations", [0] * 6)[f.id] for row in history]
                peak = max(1, max(vals))
                pts = []
                for n, v in enumerate(vals):
                    pts.extend(
                        (x + cw - 48 + n * 39 / (len(vals) - 1), y + 53 - v / peak * 14)
                    )
                i.line(*pts, color=tint(color, 0.7))

    def _events(self, world, w, h):
        i = self.ink
        events = list(getattr(world, "events", ()))[-2:]
        if events:
            i.rect(24, h - 114, min(w - 48, 660), 32, fill=VBG, outline="")
        for n, e in enumerate(reversed(events)):
            text = e.get("text", "")
            if world.tick - e.get("tick", world.tick) < 240:
                i.text(
                    29,
                    h - 96 - n * 15,
                    "› " + str(text)[:100],
                    10,
                    e.get("color", VMUTED),
                )

    def _decision_card(self, a, world, w, h):
        i = self.ink
        compact = w < 1000 or h < 650
        cw = 228 if compact else 262
        x, y = w - cw - 29, 128
        color = FACTION_COLORS[a.faction]
        trace = getattr(a, "trace", {}) or {}
        scores = trace.get("scores", {})
        if not isinstance(scores, dict):
            scores = {}
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[
            : 3 if compact else 5
        ]
        ch = 253 + len(ranked) * 17
        i.rect(x, y, cw, ch, fill="#08111b", outline="#284253")
        i.rect(x, y, 3, ch, fill=color, outline="")
        i.text(x + 14, y + 12, "SURVIVE / COMMAND / INHERIT", 10, "#7196ad")
        i.text(
            x + 14,
            y + 33,
            f"#{a.uid} / {world.factions[a.faction].method}",
            13,
            color,
            bold=True,
        )
        status = self.command_status.get(a.uid, {})
        rank = str(status.get("rank", "member")).upper()
        trophic = str(getattr(a, "trophic", "forager")).upper()
        i.text(x + 14, y + 55, f"{trophic} · {rank}", 9, "#a6c4cc")
        i.text(
            x + 14,
            y + 72,
            f"{a.action} · E{a.energy:.0f} H{a.health:.0f} G{a.generation}",
            10,
            VTEXT,
        )
        merit = getattr(a, "merit", 0.0)
        threshold = globals().get("BIRTH_MERIT", 3.5)
        qualified = (
            bool(world.birth_eligible(a)) if hasattr(world, "birth_eligible") else False
        )
        i.text(
            x + 14,
            y + 91,
            f"MERIT {merit:.1f}/{threshold:g} · "
            + ("BIRTH READY" if qualified else "BIRTH LOCKED"),
            9,
            "#b3d6a2" if qualified else "#a6b7bf",
        )
        order = status.get("order") or "LOCAL INITIATIVE"
        i.text(x + 14, y + 111, "ORDER " + str(order), 10, color)
        link = "LINK OK" if status.get("link") else "LINK LOST"
        if rank == "COMMANDER":
            link = "COMMAND ORIGIN"
        ttl = max(0, int(status.get("ttl", 0)))
        i.text(x + 14, y + 128, f"{link} · expires in {ttl} ticks", 9, "#7d9eac")
        forecast = trace.get("forecast")
        # The actual candidate chosen by the policy, never a decorative prediction.
        projected = (
            forecast.get("candidates", {}).get(a.action, [])
            if isinstance(forecast, dict)
            else []
        )
        if projected:
            horizon = "/".join(str(row.get("ticks", "?")) for row in projected)
            last = projected[-1]
            i.text(x + 14, y + 149, f"PROJECTED @ {horizon} ticks", 9, "#c0b2dc")
            i.text(
                x + 14,
                y + 163,
                f"ENERGY {last.get('energy', 0):.0f} / INTEGRITY {last.get('health', 0):.0f} · estimate",
                9,
                "#c0b2dc",
            )
        else:
            i.text(
                x + 14,
                y + 149,
                "FORECAST · no long-horizon estimate",
                9,
                "#7d869b",
                width=cw - 28,
            )
        reason = str(trace.get("reason", "Observing the next decision"))
        i.text(x + 14, y + 187, reason[:82], 9, VMUTED, width=cw - 28)
        top = y + 226
        peak = max([abs(v) for _, v in ranked] + [0.1])
        for n, (name, value) in enumerate(ranked):
            yy = top + n * 17
            i.text(x + 14, yy, name, 9, color if name == a.action else VMUTED)
            i.bar(
                x + 92,
                yy + 4,
                cw - 154,
                max(0, value) / peak,
                color if name == a.action else "#46677c",
                4,
            )
            i.text(x + cw - 12, yy, f"{value:+.1f}", 9, "#aac3d1", anchor="ne")
        # Current score bars concern the next choice. Label observed feedback
        # with its own action/tick so it cannot be mistaken for that prediction.
        outcome = next(
            (
                row
                for row in reversed(getattr(world, "forecasts", ()))
                if row.get("uid") == a.uid
            ),
            None,
        )
        feedback = (
            f"OUTCOME {outcome['action']} {outcome['realized_reward']:+.2f} @ {outcome['tick']}"
            if outcome
            else "OUTCOME · awaiting observation"
        )
        i.text(x + 14, y + ch - 20, feedback, 9, "#bbd3dc")


class BattleApp:
    """Portable Tk screensaver with bounded real-time simulation and no file writes by default."""

    def __init__(
        self, seed=42, screensaver=False, max_agents=60, episode_ticks=1500, root=None
    ):
        import tkinter as tk

        self.tk = tk
        self.root = root or tk.Tk()
        self.root.title("CHITIN — The Island Learns | Algorithmic Arts")
        self.root.geometry("1280x800")
        self.root.minsize(800, 560)
        self.root.configure(bg=VBG)
        from tkinter import font as tkfont

        global VFONT
        families = set(tkfont.families(self.root))
        VFONT = next(
            (
                name
                for name in ("Consolas", "DejaVu Sans Mono", "Menlo", "Courier New")
                if name in families
            ),
            tkfont.nametofont("TkFixedFont").actual("family"),
        )
        self.canvas = tk.Canvas(self.root, bg=VBG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.ink, self.world = (
            Ink(self.canvas),
            BattleWorld(seed=seed, max_agents=max_agents, episode_ticks=episode_ticks),
        )
        self.view = BattleView(self.ink)
        self.running, self.overlay, self.focus_uid = True, True, None
        self.fullscreen, self.screensaver = bool(screensaver), bool(screensaver)
        self.speed, self.credit, self.closed, self.error = 18.0, 0.0, False, None
        self.root.report_callback_exception = self._callback_exception
        self.fps, self.last_frame_ms = 0.0, 0.0
        self.target_fps = 20
        self._visible = True
        self._activity_revision = 0
        self._last = self._fps_start = time.perf_counter()
        self._frames, self._after = 0, None
        self._last_motion = self._last
        self._notice, self._notice_until = "", 0.0
        self.root.attributes("-fullscreen", self.fullscreen)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<KeyPress>", self._key)
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Motion>", self._motion)
        self.root.bind("<Unmap>", self._visibility)
        self.root.bind("<Map>", self._visibility)
        self._after = self.root.after(25, self.frame)

    def _callback_exception(self, exception_type, value, tb):
        import traceback

        self.error = f"Callback stopped: {exception_type.__name__}: {value}"
        self.running = False
        self.root.title(self.error)
        traceback.print_exception(exception_type, value, tb)

    def _visibility(self, event):
        if event.widget is self.root:
            self._activity_revision += 1
            self._visible = str(event.type) in ("19", "Map")
            self.credit = 0.0
            self._last = time.perf_counter()

    def _motion(self, event=None):
        self._last_motion = time.perf_counter()
        self.canvas.configure(cursor="")

    def _click(self, event):
        self._motion()
        hits = [
            (math.hypot(event.x - x, event.y - y), uid, r)
            for uid, (x, y, r) in self.view.hitboxes.items()
        ]
        hits.sort()
        self.focus_uid = (
            hits[0][1] if hits and hits[0][0] < max(20, hits[0][2]) else None
        )
        self.draw()

    def _key(self, event):
        key = event.keysym.lower()
        self._motion()
        if key == "space":
            self._activity_revision += 1
            self.running = not self.running
            self.credit = 0.0
        elif key in ("f", "f11"):
            self.fullscreen = not self.fullscreen
            self.root.attributes("-fullscreen", self.fullscreen)
        elif key == "escape":
            if self.fullscreen:
                self.fullscreen = False
                self.root.attributes("-fullscreen", False)
            else:
                self.close()
                return
        elif key == "h":
            self.overlay = not self.overlay
        elif key == "m":
            modes = globals().get(
                "MODES",
                (
                    "Nugget rush",
                    "Scarcity",
                    "Moving seams",
                    "Siege",
                    "Tempest",
                    "Arms race",
                ),
            )
            names = list(modes.keys()) if isinstance(modes, dict) else list(modes)
            index = names.index(self.world.mode) if self.world.mode in names else -1
            self.world.set_mode(names[(index + 1) % len(names)])
        elif key == "n":
            self._activity_revision += 1
            self.world.advance_episode()
            self.focus_uid = None
        elif key == "r":
            self._activity_revision += 1
            self.world = BattleWorld(
                seed=(self.world.seed + 1) % (2**32),
                max_agents=self.world.max_agents,
                episode_ticks=self.world.episode_ticks,
            )
            self.focus_uid = None
        elif key in ("bracketright", "plus", "equal"):
            self.speed = min(90, self.speed * 1.5)
        elif key in ("bracketleft", "minus"):
            self.speed = max(2, self.speed / 1.5)
        elif key == "e":
            self.export_json()
        self.draw()

    def export_json(self):
        import json
        from tkinter import filedialog

        self._activity_revision += 1
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export this observed experiment",
            defaultextension=".json",
            initialfile=f"chitin-seed-{self.world.seed}-tick-{self.world.tick}.json",
            filetypes=[("Experiment JSON", "*.json")],
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.world.export(), f, ensure_ascii=False, indent=2)
                self._notice = "Experiment exported"
            except (OSError, ValueError, TypeError) as error:
                self._notice = f"Export failed: {error}"
            self._notice_until = time.perf_counter() + 6
        self._last = time.perf_counter()
        self.credit = 0.0
        self._activity_revision += 1

    def draw(self):
        if self.closed:
            return
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 20 or h < 20:
            return
        self.view.draw(self.world, w, h, focus_uid=self.focus_uid, overlay=self.overlay)
        # Ephemeral text uses the same pool; never creates an unbounded stream of items.
        label = self.error or (
            self._notice if time.perf_counter() < self._notice_until else ""
        )
        if not self.running:
            label = label or "PAUSED · SPACE resumes"
        if label:
            self.ink.layer = "notice"
            self.ink.rect(w / 2 - 220, 76, 440, 27, fill="#172330", outline="#4c6a80")
            self.ink.text(w / 2, 82, label[:74], 11, "#e7cf9c", anchor="n")
            self.ink.end()

    def frame(self):
        if self.closed:
            return
        start = time.perf_counter()
        elapsed = min(0.15, max(0.0, start - self._last))
        self._last = start
        if not self._visible or self.root.state() == "iconic":
            # Minimized windows consume no model/render work and never accrue catch-up debt.
            self.credit = 0.0
            self._after = self.root.after(250, self.frame)
            return
        if self.running and not self.error:
            self.credit = min(5.0, self.credit + elapsed * self.speed)
            steps = 0
            try:
                while (
                    self.credit >= 1
                    and steps < 5
                    and time.perf_counter() - start < 0.014
                ):
                    self.world.step()
                    self.credit -= 1
                    steps += 1
            except Exception as error:
                self.error = f"Simulation stopped: {type(error).__name__}: {error}"
                self.running = False
        try:
            self.draw()
        except Exception as error:
            self.error = f"Rendering stopped: {type(error).__name__}: {error}"
            self.running = False
            self.root.title(self.error)
        self._frames += 1
        if start - self._fps_start >= 1:
            self.fps = self._frames / (start - self._fps_start)
            self._frames, self._fps_start = 0, start
        if self.screensaver and start - self._last_motion > 3:
            self.canvas.configure(cursor="none")
        self.last_frame_ms = (time.perf_counter() - start) * 1000
        # A slow machine trades frame rate for breathing room, rather than saturating a core.
        # At most about 50% of one event-loop thread is spent on frame work.
        delay = max(
            8,
            round(1000 / self.target_fps - self.last_frame_ms),
            round(self.last_frame_ms),
        )
        self._after = self.root.after(delay, self.frame)

    def close(self):
        if not self.closed:
            self.closed = True
            if self._after:
                self.root.after_cancel(self._after)
                self._after = None
            self.root.destroy()

    def run(self):
        self.root.mainloop()


class SoakRecorder:
    """Opt-in bounded native-GUI endurance evidence, including Windows RSS.

    Eight hours means eight active, mapped, advancing GUI hours. Sleep,
    minimization and pause do not manufacture a successful endurance result.
    The report is an atomic rolling snapshot, not an ever-growing log.
    """

    def __init__(self, app, hours, path):
        import hashlib
        import platform
        from datetime import datetime, timezone

        self.app, self.path = app, Path(path)
        self.target = float(hours) * 3600
        self.start = self.previous = time.perf_counter()
        self.cpu_start = time.process_time()
        self.active = 0.0
        self.samples = deque(maxlen=576)
        self.last_sample = self.last_write = self.start
        self.last_tick = app.world.tick
        self.activity_revision = app._activity_revision
        self.world_identity = id(app.world)
        self.world_resets = 0
        self.reset_seeds = deque(maxlen=100)
        self.frames = 0
        self.max_items = self.max_rss = self.max_frame_ms = 0
        self.rss_first = None
        self.finished = False
        self.write_retries = 0
        self.meta = {
            "platform": platform.platform(),
            "python": sys.version,
            "tk": str(app.tk.TkVersion),
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "target_active_seconds": self.target,
            "seed": app.world.seed,
            "max_agents": app.world.max_agents,
            "interpretation": "Native event-loop test. Completion requires mapped non-iconic advancing simulation; "
            "sleep/minimized/paused intervals are excluded. CPU is fraction of one logical core. "
            "Mixed probe intervals containing pause, visibility, reset or export transitions are conservatively excluded. "
            "Memory is current process resident/working-set size, not system usage. "
            "Mapped does not prove the window was unobscured or watched by a person.",
        }
        # Validate destination before a lengthy run, without truncating old logs.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise ValueError(
                f"Endurance report already exists: {self.path}; choose a new path"
            )
        self.write("running")
        app.root.after(1000, self.probe)

    @staticmethod
    def rss_bytes():
        import os

        try:
            if sys.platform == "win32":
                # ctypes pointer types are cached globally on Python 3.10.
                # Defining a fresh Structure per probe leaks a new retained type.
                if not hasattr(SoakRecorder, "_windows_memory_api"):
                    import ctypes
                    from ctypes import wintypes

                    class MemoryCounters(ctypes.Structure):
                        _fields_ = [
                            ("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t),
                        ]

                    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                    psapi = ctypes.WinDLL("psapi", use_last_error=True)
                    kernel.GetCurrentProcess.restype = wintypes.HANDLE
                    psapi.GetProcessMemoryInfo.argtypes = [
                        wintypes.HANDLE,
                        ctypes.POINTER(MemoryCounters),
                        wintypes.DWORD,
                    ]
                    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
                    SoakRecorder._windows_memory_api = (
                        ctypes,
                        MemoryCounters,
                        kernel,
                        psapi,
                    )
                ctypes, counters, kernel, psapi = SoakRecorder._windows_memory_api
                info = counters()
                info.cb = ctypes.sizeof(info)
                if psapi.GetProcessMemoryInfo(
                    kernel.GetCurrentProcess(), ctypes.byref(info), info.cb
                ):
                    return int(info.WorkingSetSize)
            elif sys.platform.startswith("linux"):
                return int(
                    Path("/proc/self/statm").read_text().split()[1]
                ) * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, AttributeError, IndexError):
            pass
        return None

    def probe(self):
        try:
            self._probe()
        except Exception as error:
            self.app.error = (
                f"Endurance recorder failed: {type(error).__name__}: {error}"
            )
            self.app.running = False
            self.app.root.title(self.app.error)
            print(self.app.error, file=sys.stderr)
            self._retry_failure_report()

    def _retry_failure_report(self):
        if self.finished:
            return
        try:
            self.finish("failed")
        except (OSError, ValueError, TypeError) as error:
            self.write_retries += 1
            if self.write_retries <= 3 and not self.app.closed:
                self.app.root.after(5000, self._retry_failure_report)
            else:
                print(
                    f"Failed to save endurance failure report: {error}. "
                    "Any remaining running report is incomplete, never a pass.",
                    file=sys.stderr,
                )

    def _probe(self):
        if self.finished or self.app.closed:
            return
        now = time.perf_counter()
        gap = now - self.previous
        self.previous = now
        if id(self.app.world) != self.world_identity:
            self.world_identity = id(self.app.world)
            self.world_resets += 1
            self.reset_seeds.append(
                {"elapsed": now - self.start, "seed": self.app.world.seed}
            )
        advancing = self.app.world.tick != self.last_tick
        visible = self.app.root.winfo_ismapped() and self.app.root.state() != "iconic"
        uninterrupted = self.activity_revision == self.app._activity_revision
        self.activity_revision = self.app._activity_revision
        if (
            0 < gap < 3
            and uninterrupted
            and visible
            and advancing
            and self.app.running
            and not self.app.error
        ):
            self.active += gap
        self.last_tick = self.app.world.tick
        rss = self.rss_bytes()
        if rss is not None:
            self.max_rss = max(self.max_rss, rss)
            if self.rss_first is None:
                self.rss_first = rss
        items = sum(len(pool) for pool in self.app.ink.pool.values())
        self.max_items = max(self.max_items, items)
        self.max_frame_ms = max(self.max_frame_ms, self.app.last_frame_ms)
        self.frames += 1
        if now - self.last_sample >= 60 or not self.samples:
            self.samples.append(
                {
                    "elapsed": round(now - self.start, 3),
                    "active": round(self.active, 3),
                    "tick": self.app.world.tick,
                    "episode": self.app.world.episode,
                    "seed": self.app.world.seed,
                    "fps": round(self.app.fps, 2),
                    "frame_ms": round(self.app.last_frame_ms, 3),
                    "rss_bytes": rss,
                    "canvas_items": items,
                    "population": len(self.app.world.agents),
                    "learner_contexts": sum(
                        len(f.policy) for f in self.app.world.factions
                    ),
                    "ledger_error": self.app.world.last_ledger_error,
                }
            )
            self.last_sample = now
        if self.app.error:
            self.finish("failed")
            return
        if self.active >= self.target:
            self.finish("completed")
            self.app._notice = "Endurance test complete · report saved"
            self.app._notice_until = now + 60
            self.app.root.title("CHITIN — endurance test complete; report saved")
            return
        if now - self.last_write >= 60:
            self.write("running")
        self.app.root.after(1000, self.probe)

    def write(self, status):
        now = time.perf_counter()
        elapsed = now - self.start
        data = {
            **self.meta,
            "status": status,
            "elapsed_seconds": elapsed,
            "active_seconds": self.active,
            "cpu_seconds": time.process_time() - self.cpu_start,
            "mean_cpu_one_core_fraction": (time.process_time() - self.cpu_start)
            / max(elapsed, 0.001),
            "rss_first_bytes": self.rss_first,
            "rss_peak_observed_bytes": self.max_rss,
            "rss_latest_bytes": self.rss_bytes(),
            "max_canvas_items": self.max_items,
            "max_sampled_frame_ms": self.max_frame_ms,
            "probe_count": self.frames,
            "world_resets": self.world_resets,
            "recent_reset_seeds": list(self.reset_seeds),
            "report_write_retries": self.write_retries,
            "error": self.app.error,
            "samples": list(self.samples),
            "final_state": self.app.world.snapshot(),
        }
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temp.replace(self.path)
        self.last_write = now

    def finish(self, status="aborted"):
        if not self.finished:
            self.write(status)
            self.finished = True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Crab Battle Evolution — autonomous strategy art, Python/Tk only.",
        epilog="Keys: Space pause; F/F11 fullscreen; H telemetry; M mode; N next epoch; "
        "R fresh seed; [/] speed; E export; Esc leave fullscreen/close.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--headless", action="store_true", help="simulate without importing Tk"
    )
    parser.add_argument(
        "--screensaver",
        action="store_true",
        help="start full-screen autonomous display",
    )
    parser.add_argument(
        "--steps", type=int, default=3000, help="fixed model ticks per headless trial"
    )
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--max-agents", type=int, default=60)
    parser.add_argument("--episode-ticks", type=int, default=1500)
    parser.add_argument(
        "--compare-learning",
        action="store_true",
        help="paired Q/UCB feedback on/off; opponent observations and evolution remain active",
    )
    parser.add_argument("--no-learning", action="store_true")
    parser.add_argument(
        "--output", type=Path, help="save complete headless evidence as JSON"
    )
    parser.add_argument(
        "--selftest", action="store_true", help="run embedded model invariants"
    )
    parser.add_argument(
        "--soak-hours",
        type=float,
        help="opt-in native active GUI endurance hours (e.g. 8)",
    )
    parser.add_argument(
        "--soak-report",
        type=Path,
        help="NEW JSON report path; existing files are preserved",
    )
    args = parser.parse_args(argv)
    for name, value, lo, hi in (
        ("seed", args.seed, 0, 2**32 - 1),
        ("steps", args.steps, 1, 1000000),
        ("trials", args.trials, 1, 100),
        ("max-agents", args.max_agents, 24, 120),
        ("episode-ticks", args.episode_ticks, 300, 100000),
    ):
        if not lo <= value <= hi:
            parser.error(f"--{name} must be in [{lo}, {hi}]")
    if args.seed + args.trials - 1 > 2**32 - 1:
        parser.error("consecutive trial seeds exceed 32-bit seed range")
    if (args.output or args.compare_learning or args.no_learning) and not args.headless:
        parser.error(
            "--output, --compare-learning and --no-learning require --headless"
        )
    if args.compare_learning and args.no_learning:
        parser.error("--compare-learning already includes both learning states")
    if args.headless and args.screensaver:
        parser.error("--headless and --screensaver select different runtime modes")
    if args.selftest and (
        args.headless
        or args.screensaver
        or args.output
        or args.compare_learning
        or args.no_learning
    ):
        parser.error(
            "--selftest cannot be combined with simulation, export or screensaver modes"
        )
    if bool(args.soak_report) != (args.soak_hours is not None):
        parser.error("--soak-hours and --soak-report are required together")
    if args.soak_hours is not None and (
        not math.isfinite(args.soak_hours) or not 0.001 <= args.soak_hours <= 168
    ):
        parser.error("--soak-hours must be finite and between .001 and 168")
    if args.soak_report and (args.headless or args.selftest):
        parser.error(
            "endurance reports require the native GUI, not --headless or --selftest"
        )
    if args.selftest:
        result = self_check()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if args.headless:
        runs = []
        started = time.perf_counter()
        for index in range(args.trials):
            for learning in (
                (True, False) if args.compare_learning else (not args.no_learning,)
            ):
                world = BattleWorld(
                    seed=args.seed + index,
                    max_agents=args.max_agents,
                    episode_ticks=args.episode_ticks,
                    learning=learning,
                )
                t0 = time.perf_counter()
                for _ in range(args.steps):
                    world.step()
                exported = world.export()
                elapsed = time.perf_counter() - t0
                runs.append(
                    {
                        "seed": args.seed + index,
                        "learning": learning,
                        "elapsed_seconds": elapsed,
                        "ticks_per_second": args.steps / max(elapsed, 1e-9),
                        "summary": world.snapshot(),
                        "world": exported,
                    }
                )
                print(
                    f"seed={args.seed + index} learning={learning} ticks={world.tick} "
                    f"epoch={world.episode} population={len(world.agents)} "
                    f"rate={args.steps / max(elapsed, 1e-9):.1f} ticks/s"
                )
        report = {
            "artifact": "Crab Battle Evolution",
            "version": MODEL_VERSION,
            "steps_per_trial": args.steps,
            "paired_learning_ablation": args.compare_learning,
            "interpretation": "Q/UCB feedback ablation; opponent observations and genetic evolution remain active. "
            "Shared-ecology descriptive trials. Paired seeds match initialization; "
            "policy choices can change subsequent random draws. Scores are engineered objectives, "
            "not evidence of general intelligence or guaranteed improvement.",
            "elapsed_seconds": time.perf_counter() - started,
            "runs": runs,
        }
        if args.output:
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
                encoding="utf-8",
            )
            print(f"Saved {args.output}")
        else:
            print(
                json.dumps(
                    {"summaries": [r["summary"] for r in runs]},
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
            )
        return 0
    try:
        app = BattleApp(
            seed=args.seed,
            screensaver=args.screensaver,
            max_agents=args.max_agents,
            episode_ticks=args.episode_ticks,
        )
        recorder = (
            SoakRecorder(app, args.soak_hours, args.soak_report)
            if args.soak_report
            else None
        )
        try:
            app.run()
        except Exception as error:
            app.error = f"Native event loop failed: {type(error).__name__}: {error}"
            raise
        finally:
            if recorder:
                recorder.finish("failed" if app.error else "aborted")
        if app.error:
            print(app.error, file=sys.stderr)
            return 1
    except ImportError as error:
        print(
            f"Tk GUI unavailable: {error}. Headless mode requires only Python's standard library.",
            file=sys.stderr,
        )
        return 1
    except Exception as error:
        # Report failures instead of a silently frozen screensaver.
        import traceback

        traceback.print_exc()
        print(f"Battle display stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
