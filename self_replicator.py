#!/usr/bin/env python3
"""Self-Replicator Observatory — an Algorithmic Arts experiment.

One file, Python >= 3.10, standard library only. The GUI needs tkinter.
  python self_replicator.py
  python self_replicator.py --selftest
  python self_replicator.py --headless --steps 600 --trials 5 --output experiment.json

An explicit artificial ecology, not a model of consciousness or molecular life.
No networking, subprocesses, dynamic code execution, or real file replication.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass, replace
from pathlib import Path

BG = "#06080c"
PANEL = "#0b1019"
LINE = "#253044"
TEXT = "#dce6f6"
MUTED = "#8a9ab2"
CYAN = "#51d8ef"
AMBER = "#ffbd69"
PINK = "#d895ff"
GREEN = "#77d8a3"
RED = "#ff7a8d"
NAMES = ("Cautious", "Bold", "Adaptive")
COLORS = (CYAN, AMBER, PINK)
RULES = ("Reflex", "Utility", "Hybrid")
ACTIONS = ("FORAGE", "REPRODUCE", "FLEE", "FIGHT", "FREEZE", "REST")
COLS, ROWS = 24, 16
MAX_AGENTS = 360  # computational guard, not an ecological carrying capacity
MODEL_VERSION = "1.0"


def clamp(value, low, high):
    return min(high, max(low, value))


def delta(a, b, size):
    """Shortest signed displacement on a periodic world."""
    return (b - a + size / 2) % size - size / 2


@dataclass(frozen=True)
class Config:
    resources: float = 1800.0
    regrowth: float = 8.0
    replication_cost: float = 12.0
    mutation: float = 0.12
    competition: float = 0.60
    rule: str = "Hybrid"
    self_modify: bool = True
    seed: int = 42
    founders: int = 12  # per lineage, always equal

    def __post_init__(self):
        limits = {"resources": (0, 4000), "regrowth": (0, 30),
                  "replication_cost": (2, 40), "mutation": (0, 1),
                  "competition": (0, 1), "founders": (1, 40)}
        for name, (low, high) in limits.items():
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be in [{low}, {high}]")
        if self.rule not in RULES:
            raise ValueError(f"rule must be one of {RULES}")
        if not isinstance(self.seed, int) or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be an integer from 0 to 4294967295")
        if not isinstance(self.founders, int):
            raise ValueError("founders must be an integer")
        if not isinstance(self.self_modify, bool):
            raise ValueError("self_modify must be true or false")


@dataclass(frozen=True)
class Genome:
    risk: float = 0.5
    efficiency: float = 1.0
    reserve: float = 14.0

    def mutate(self, rng):
        name, low, high = rng.choice((("risk", 0.05, 0.95),
                                      ("efficiency", 0.6, 1.4),
                                      ("reserve", 8.0, 20.0)))
        old = getattr(self, name)
        change = rng.choice((-1, 1)) * rng.uniform(0.04, 0.16) * (high - low)
        new = old + change
        if new < low or new > high:
            new = old - change  # reflect: a mutation always changes its gene
        return replace(self, **{name: clamp(new, low, high)}), name


@dataclass
class Decision:
    action: str
    reason: str
    danger: float
    strength: float
    escape: bool
    food: float
    energy: float
    risk: float
    threshold: float
    scores: dict


@dataclass
class Agent:
    uid: int
    lineage: int
    x: float
    y: float
    energy: float
    genome: Genome
    generation: int = 0
    parent: int | None = None
    age: int = 0
    offset: float = 0.0  # acquired; never copied to a child
    checkpoint_energy: float = 18.0
    injury: float = 0.0
    action: str = "REST"
    trace: Decision | None = None

    @property
    def risk(self):
        return clamp(self.genome.risk + self.offset, 0.05, 0.95)


def decide(agent, cfg, danger, strength, escape, food, room=True):
    """Pure, inspectable policy; no RNG, hidden optimizer, or learned model."""
    risk = agent.risk
    threshold = 0.18 + 0.48 * risk
    ready = room and agent.energy >= cfg.replication_cost + 2 * agent.genome.reserve
    scores = {}
    reflex = cfg.rule == "Reflex" or (cfg.rule == "Hybrid" and danger >= 0.65)
    if reflex:
        if danger >= threshold:
            if cfg.rule == "Hybrid" and escape:
                action, reason = "FLEE", "Extreme danger: open escape route has priority."
            elif risk >= 0.55 and strength >= 0.85:
                action, reason = "FIGHT", "Threat crosses threshold; risk and relative strength permit fighting."
            elif escape:
                action, reason = "FLEE", "Threat crosses threshold; a lower-threat neighboring cell exists."
            elif strength >= 1.1:
                action, reason = "FIGHT", "Escape is blocked; this agent is stronger."
            else:
                action, reason = "FREEZE", "Escape is blocked and the opponent is stronger."
        elif ready:
            action, reason = "REPRODUCE", "Energy covers construction plus two offspring-sized reserves."
        elif food > 0.02:
            action, reason = "FORAGE", "Threat is below threshold; accessible food is available."
        else:
            action, reason = "REST", "No nearby food: reduce metabolic loss while waiting."
    else:
        gain = min(food, 0.70 + 0.55 * agent.genome.efficiency)
        scores = {"FORAGE": gain - 0.13 - danger * (1 - risk) * 1.4,
                  "REST": 0.02 - 0.5 * danger}
        if ready:
            scores["REPRODUCE"] = 0.75 + 0.015 * agent.energy - danger * (1 - risk)
        if danger > 0.04:
            if escape:
                scores["FLEE"] = danger * (1 - risk) * 2.2 - 0.14 - 0.1 * gain
            else:
                scores["FREEZE"] = danger * (1 - risk) * 0.4 - 0.1
            scores["FIGHT"] = danger * (risk * min(strength, 3) * 1.8 - (1 - risk)) - 0.12
        action = max(scores, key=scores.get)
        reason = f"Highest eligible heuristic score: {action} = {scores[action]:+.2f}."
    return Decision(action, reason, danger, strength, escape, food,
                    agent.energy, risk, threshold, scores)


class World:
    """Finite local resource field, randomized sequential agents, fixed ticks.

    Food -> stored energy is a transfer. Construction, metabolism, movement,
    injury, learning and death dissipate energy. Inflow is the only new energy.
    """

    def __init__(self, cfg=Config()):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        # Environmental randomness is independent of agent-turn randomness.
        terrain_rng = random.Random(cfg.seed ^ 0x71A5)
        centers = [(terrain_rng.uniform(0, COLS), terrain_rng.uniform(0, ROWS)) for _ in range(9)]
        weights = [0.03 + sum(math.exp(-(delta(x, cx, COLS)**2 + delta(y, cy, ROWS)**2) / 7)
                             for cx, cy in centers) for y in range(ROWS) for x in range(COLS)]
        scale = cfg.resources / sum(weights)
        self.capacity = [w * scale for w in weights]
        self.food = self.capacity.copy()
        self.agents = []
        self.next_id = 0
        # Matched positions/energy across lineages; equal starts per seed.
        for _ in range(cfg.founders):
            x, y = self.rng.uniform(0, COLS), self.rng.uniform(0, ROWS)
            for lineage, risk in enumerate((0.2, 0.8, 0.5)):
                self.agents.append(self._new(lineage, x, y, 18, Genome(risk=risk)))
        self.tick = 0
        self.inflow = 0.0
        self.heat = 0.0
        self.initial_energy = sum(self.food) + sum(a.energy for a in self.agents)
        self.births = [0, 0, 0]
        self.deaths = [0, 0, 0]
        self.mutations = 0
        self.modifications = 0
        self.cap_hits = 0
        self.last = {}
        self.events = deque(maxlen=80)
        self.actions = Counter()
        self.history = []
        self.history_interval = 5
        self._record()

    def _new(self, lineage, x, y, energy, genome, generation=0, parent=None):
        a = Agent(self.next_id, lineage, x % COLS, y % ROWS, energy, genome,
                  generation, parent, checkpoint_energy=energy)
        self.next_id += 1
        return a

    def cell(self, x, y):
        return int(y % ROWS) * COLS + int(x % COLS)

    def spend(self, agent, amount):
        paid = min(agent.energy, max(0.0, amount))
        agent.energy -= paid
        self.heat += paid
        return paid

    def event(self, kind, **data):
        data = dict(kind=kind, tick=self.tick, **data)
        self.last[kind] = data
        self.events.append(data)

    def _neighbors(self, agent, buckets):
        found = []
        ix, iy = int(agent.x), int(agent.y)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                for other in buckets.get(((ix + dx) % COLS, (iy + dy) % ROWS), ()):
                    if other.lineage == agent.lineage or other.energy <= 0:
                        continue
                    distance = math.hypot(delta(agent.x, other.x, COLS), delta(agent.y, other.y, ROWS))
                    if distance < 2.2:
                        found.append((distance, other))
        return found

    def _sense(self, a, buckets):
        neighbors = self._neighbors(a, buckets)
        nearest = min(neighbors, key=lambda x: (x[0], x[1].uid)) if neighbors else None
        enemy = nearest[1] if nearest else None
        strength = (a.energy + 2) / (enemy.energy + 2) if enemy else 1.0
        danger = (self.cfg.competition * (1 - nearest[0] / 2.2) *
                  min(1.5, 1 / strength)) if nearest else 0.0
        # Empty neighboring cell = a feasible escape route, even on a torus.
        options = [(a.x + dx, a.y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
        def pressure(pos):
            return sum(max(0, 1.5 - math.hypot(delta(pos[0], o.x, COLS),
                                               delta(pos[1], o.y, ROWS))) for _, o in neighbors)
        escape_target = min(options, key=pressure)
        escape = bool(enemy) and pressure(escape_target) < pressure((a.x, a.y)) - 0.05
        target = max(options, key=lambda p: self.food[self.cell(*p)])
        food = self.food[self.cell(*target)]
        return enemy, min(1, danger), strength, escape, escape_target, target, food

    def _move(self, a, target, speed):
        dx, dy = delta(a.x, target[0], COLS), delta(a.y, target[1], ROWS)
        distance = math.hypot(dx, dy)
        if distance > 0:
            f = min(speed / distance, 1.0)
            a.x, a.y = (a.x + dx * f) % COLS, (a.y + dy * f) % ROWS

    def _birth(self, parent):
        cost = self.cfg.replication_cost
        before = parent.energy
        self.spend(parent, cost)
        parent.energy /= 2
        genome, gene = parent.genome, None
        if self.rng.random() < self.cfg.mutation:
            genome, gene = genome.mutate(self.rng)
            self.mutations += 1
        angle = self.rng.uniform(0, math.tau)
        child = self._new(parent.lineage, parent.x + 0.45 * math.cos(angle),
                          parent.y + 0.45 * math.sin(angle), parent.energy,
                          genome, parent.generation + 1, parent.uid)
        self.births[parent.lineage] += 1
        self.event("birth", uid=parent.uid, child=child.uid, lineage=parent.lineage,
                   x=parent.x, y=parent.y, before=before, cost=cost,
                   parent_energy=parent.energy, child_energy=child.energy,
                   parent_genome=asdict(parent.genome), child_genome=asdict(genome), mutation=gene)
        if gene:
            self.last["mutation"] = self.last["birth"].copy()
        return child

    def _fight(self, a, enemy, pairs):
        pair = tuple(sorted((a.uid, enemy.uid)))
        distance = math.hypot(delta(a.x, enemy.x, COLS), delta(a.y, enemy.y, ROWS))
        if distance >= 0.9 or pair in pairs or self.rng.random() >= 0.35 * self.cfg.competition:
            return
        pairs.add(pair)
        chance = (a.energy + 2) / (a.energy + enemy.energy + 4)
        winner, loser = (a, enemy) if self.rng.random() < chance else (enemy, a)
        injury_a = self.spend(a, 0.8 + self.rng.random() * 0.6)
        injury_b = self.spend(enemy, 0.8 + self.rng.random() * 0.6)
        a.injury += injury_a
        enemy.injury += injury_b
        transfer = min(loser.energy * 0.3, 3 * self.cfg.competition)
        loser.energy -= transfer
        winner.energy += transfer
        self.event("fight", uid=a.uid, other=enemy.uid, x=a.x, y=a.y,
                   lineage=a.lineage, winner=winner.uid, loser=loser.uid,
                   transfer=transfer, heat=injury_a + injury_b)

    def _adapt(self, a):
        if a.lineage != 2 or not self.cfg.self_modify or a.age % 40 or a.energy < 1:
            return
        difference = a.energy - a.checkpoint_energy
        change = -0.08 if a.injury > 0.3 else (0.08 if difference < -1 else 0.0)
        old = a.risk
        a.offset = clamp(a.offset + change, -0.25, 0.25)
        if abs(a.risk - old) > 1e-9:
            self.spend(a, 0.35)
            self.modifications += 1
            self.event("adapt", uid=a.uid, lineage=a.lineage, x=a.x, y=a.y,
                       before=old, after=a.risk, gene=a.genome.risk,
                       stimulus="recent injury" if a.injury > 0.3 else "falling energy",
                       cost=0.35)
        a.checkpoint_energy, a.injury = a.energy, 0.0

    def step(self):
        self.tick += 1
        total_capacity = self.cfg.resources
        if total_capacity:
            for i, cap in enumerate(self.capacity):
                added = min(cap - self.food[i], self.cfg.regrowth * cap / total_capacity)
                self.food[i] += added
                self.inflow += added
        buckets = {}
        for a in self.agents:
            buckets.setdefault((int(a.x), int(a.y)), []).append(a)
        order = self.agents.copy()
        self.rng.shuffle(order)
        children, pairs = [], set()
        for a in order:
            if a.energy <= 0:
                continue
            a.age += 1
            enemy, danger, strength, escape, escape_target, target, food = self._sense(a, buckets)
            room = len(self.agents) + len(children) < MAX_AGENTS
            if not room and a.energy >= self.cfg.replication_cost + 2 * a.genome.reserve:
                self.cap_hits += 1
            trace = decide(a, self.cfg, danger, strength, escape, food, room)
            a.action, a.trace = trace.action, trace
            self.actions[a.action] += 1
            metabolism = (0.07 + 0.03 * a.genome.efficiency**2)
            self.spend(a, metabolism * (0.45 if a.action == "REST" else 0.65 if a.action == "FREEZE" else 1))
            if a.energy <= 0:
                continue
            old_cell = (int(a.x), int(a.y))
            if a.action == "FORAGE":
                self._move(a, target, 0.32)
                self.spend(a, 0.025)
                if a.energy > 0:
                    i = self.cell(a.x, a.y)
                    gain = min(self.food[i], 0.70 + 0.55 * a.genome.efficiency)
                    self.food[i] -= gain
                    a.energy += gain
            elif a.action == "FLEE":
                self._move(a, escape_target, 0.62)
                self.spend(a, 0.14)
            elif a.action == "FIGHT" and enemy and enemy.energy > 0:
                self._move(a, (enemy.x, enemy.y), 0.42)
                self.spend(a, 0.09)
                if a.energy > 0:
                    self._fight(a, enemy, pairs)
            elif a.action == "REPRODUCE":
                # Metabolism precedes birth; recheck the full reserve condition.
                if a.energy >= self.cfg.replication_cost + 2 * a.genome.reserve:
                    children.append(self._birth(a))
            if old_cell != (int(a.x), int(a.y)):
                buckets[old_cell].remove(a)
                buckets.setdefault((int(a.x), int(a.y)), []).append(a)
            self._adapt(a)
            if a.age >= 1400:
                self.spend(a, a.energy)
        survivors = []
        for a in self.agents:
            if a.energy > 0:
                survivors.append(a)
            else:
                self.deaths[a.lineage] += 1
                self.event("death", uid=a.uid, lineage=a.lineage, x=a.x, y=a.y)
        self.agents = survivors + children
        if self.tick % self.history_interval == 0:
            self._record()

    def snapshot(self):
        groups = [[a for a in self.agents if a.lineage == i] for i in range(3)]
        return {"tick": self.tick, "population": [len(g) for g in groups],
                "resources": sum(self.food), "stored": sum(a.energy for a in self.agents),
                "inflow": self.inflow, "heat": self.heat,
                "births": self.births.copy(), "deaths": self.deaths.copy(),
                "gene_risk": [statistics.fmean(a.genome.risk for a in g) if g else None for g in groups],
                "expressed_risk": [statistics.fmean(a.risk for a in g) if g else None for g in groups],
                "mutations": self.mutations, "modifications": self.modifications,
                "cap_hits": self.cap_hits}

    def _record(self):
        self.history.append(self.snapshot())
        if len(self.history) > 2000:
            self.history = self.history[::2]
            self.history_interval *= 2

    def samples(self):
        return self.history + ([self.snapshot()] if self.history[-1]["tick"] != self.tick else [])

    def ledger_error(self):
        return self.initial_energy + self.inflow - self.heat - sum(self.food) - sum(a.energy for a in self.agents)

    def export(self):
        return {"model_version": MODEL_VERSION, "config": asdict(self.cfg),
                "initial_energy": self.initial_energy, "ledger_error": self.ledger_error(),
                "history": self.samples(), "last_events": self.last,
                "action_counts": dict(self.actions)}


def summarize(runs):
    """All strategies compete together in every trial; no isolated fitness claim."""
    result = []
    for i, name in enumerate(NAMES):
        endpoints = [r["history"][-1]["population"][i] for r in runs]
        result.append({"strategy": name, "mean": statistics.fmean(endpoints),
                       "min": min(endpoints), "max": max(endpoints),
                       "surviving_trials": sum(n > 0 for n in endpoints),
                       "mean_births": statistics.fmean(r["history"][-1]["births"][i] for r in runs)})
    return result


def write_export(path, world=None, comparison=None):
    data = {"model_version": MODEL_VERSION}
    if world is not None:
        data["live_run"] = world.export()
    if comparison is not None:
        data["comparison"] = comparison
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def write_csv(path, world):
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["tick", *NAMES, "resources", "stored_energy", "inflow", "heat",
                         "mutations", "self_modifications", "cap_hits", "seed", "config_json"])
        config = json.dumps(asdict(world.cfg), sort_keys=True)
        for row in world.samples():
            writer.writerow([row["tick"], *row["population"], row["resources"], row["stored"],
                             row["inflow"], row["heat"], row["mutations"], row["modifications"],
                             row["cap_hits"], world.cfg.seed, config])


# =============================================================================
# POOLED CANVAS — the same dark, luminous line language as spectral_geometry.py
# =============================================================================

FONT = "Consolas"
CONCEPTS = ("Architecture", "Finite resources", "Replication", "Mutation",
            "Competition", "Self-modification", "Evolution", "Decision logic")


class Ink:
    """Reusable Tk items with style/coordinate caches; also records headlessly."""

    def __init__(self, canvas=None):
        self.canvas = canvas
        self.pool = {}
        self.used = Counter()
        self.commands = []

    def begin(self):
        self.used.clear()
        self.commands.clear()

    def draw(self, kind, coords, **style):
        coords = tuple(coords)
        self.commands.append((kind, coords, style))
        if self.canvas is None:
            return
        index = self.used[kind]
        self.used[kind] += 1
        pool = self.pool.setdefault(kind, [])
        style = dict(style, state="normal")
        if index == len(pool):
            item = getattr(self.canvas, "create_" + kind)(*coords, **style)
            pool.append([item, coords, style])
        else:
            entry = pool[index]
            if entry[1] != coords:
                self.canvas.coords(entry[0], *coords)
                entry[1] = coords
            if entry[2] != style:
                self.canvas.itemconfigure(entry[0], **style)
                entry[2] = style
            self.canvas.tag_raise(entry[0])

    def end(self):
        if self.canvas:
            for kind, pool in self.pool.items():
                for entry in pool[self.used[kind]:]:
                    if entry[2].get("state") != "hidden":
                        self.canvas.itemconfigure(entry[0], state="hidden")
                        entry[2] = dict(entry[2], state="hidden")

    def line(self, *coords, color=LINE, width=1, arrow=False, dash=()):
        self.draw("line", coords, fill=color, width=width, arrow="last" if arrow else "none", dash=dash)

    def rect(self, x, y, w, h, fill="", outline=LINE, width=1):
        self.draw("rectangle", (x, y, x + w, y + h), fill=fill, outline=outline, width=width)

    def circle(self, x, y, r, color=CYAN, fill="", width=1):
        self.draw("oval", (x - r, y - r, x + r, y + r), fill=fill, outline=color, width=width)

    def text(self, x, y, text, size=13, color=TEXT, anchor="nw", width=0, bold=False):
        self.draw("text", (x, y), text=str(text), fill=color, anchor=anchor,
                  font=(FONT, -size, "bold" if bold else "normal"), width=width, justify="left")

    def bar(self, x, y, w, value, color=CYAN, height=7):
        self.rect(x, y, w, height, fill=LINE, outline="")
        if value > 0:
            self.rect(x, y, w * clamp(value, 0, 1), height, fill=color, outline="")


def draw_chart(ink, rows, box, title="Population trajectories", resource=False):
    x, y, w, h = box
    ink.text(x, y, title, 15, bold=True)
    if not rows:
        return
    ymax = max(1, max(r["resources"] if resource else max(r["population"]) for r in rows))
    ymax = math.ceil(ymax / 5) * 5
    first, last = rows[0]["tick"], max(rows[-1]["tick"], rows[0]["tick"] + 1)
    left, top, cw, ch = x + 40, y + 37, w - 52, h - 84
    for part in range(4):
        gy = top + ch * part / 3
        ink.line(left, gy, left + cw, gy)
        ink.text(left - 9, gy, f"{ymax * (3-part)/3:.0f}", 11, MUTED, anchor="e")
    for i in range(1 if resource else 3):
        points = []
        # Bound drawing work while retaining the complete numerical export.
        stride = max(1, len(rows) // 450)
        selected = rows[::stride]
        if selected[-1] is not rows[-1]:
            selected.append(rows[-1])
        for row in selected:
            value = row["resources"] if resource else row["population"][i]
            points.extend((left + (row["tick"] - first) / (last-first) * cw,
                           top + ch * (1 - value / ymax)))
        if len(points) >= 4:
            ink.line(*points, color=GREEN if resource else COLORS[i], width=2)
    for frac in (0, 0.5, 1):
        ink.text(left + cw * frac, top + ch + 10, f"{first+(last-first)*frac:.0f}",
                 11, MUTED, anchor="n")
    ink.text(left + cw / 2, y + h - 2, "simulation tick", 11, MUTED, anchor="s")
    if not resource:
        for i, name in enumerate(NAMES):
            lx = x + w - 300 + i * 102
            ink.line(lx, y + 8, lx + 14, y + 8, color=COLORS[i], width=2)
            ink.text(lx + 20, y + 8, name, 11, COLORS[i], anchor="w")


class ObservatoryView:
    """Rendering is separate from simulation: opening a diagram cannot change a run."""

    def __init__(self, ink):
        self.p = ink
        self.arena = (0, 0, 1, 1)

    def heading(self, w, title, subtitle):
        self.p.text(22, 17, title, 24, bold=True)
        self.p.text(22, 52, subtitle, 12, MUTED, width=w-44)

    def selected(self, world, uid):
        return next((a for a in world.agents if a.uid == uid), None)

    def world(self, world, w, h, uid, resource_chart=False):
        p = self.p
        self.heading(w, "Self-replicator observatory", "Finite energy. Inherited variation. Decisions before minds.")
        chart_y = h - 232
        available_w, available_h = w - 285, chart_y - 124
        cell = min(available_w / COLS, available_h / ROWS)
        aw, ah = cell * COLS, cell * ROWS
        ax, ay = 22 + (available_w - aw) / 2, 105 + (available_h - ah) / 2
        self.arena = ax, ay, aw, ah
        counts = Counter(a.lineage for a in world.agents)
        p.text(22, 83, f"TICK {world.tick:05d}    POP {len(world.agents):3d}    FOOD {sum(world.food):6.1f}", 12, MUTED)
        p.rect(ax, ay, aw, ah, outline=LINE)
        # Subdued resource field: bright dots are full patches, dim dots depleted.
        for i, amount in enumerate(world.food):
            cap = world.capacity[i]
            fraction = amount / cap if cap else 0
            if fraction > 0.03:
                shade = int(28 + 76 * fraction)
                color = f"#{int(shade*.50):02x}{shade:02x}{int(shade*.82):02x}"
                x, y = ax + (i % COLS + .5) * cell, ay + (i // COLS + .5) * cell
                p.circle(x, y, min(cell * .22, 1 + math.sqrt(amount) * .7), color, color)
        for event in world.events:
            age = world.tick - event["tick"]
            if 0 <= age <= 12 and event["kind"] in ("birth", "fight", "adapt"):
                color = {"birth": GREEN, "fight": RED, "adapt": PINK}[event["kind"]]
                p.circle(ax + event["x"] / COLS * aw, ay + event["y"] / ROWS * ah,
                         7 + age * .8, color, width=1)
        for a in world.agents:
            x, y = ax + a.x / COLS * aw, ay + a.y / ROWS * ah
            radius = 3.0 + min(4, math.sqrt(a.energy) * .48)
            color = COLORS[a.lineage]
            points = []
            for j in range(7):
                angle = j * math.tau / 6 + a.uid * .37
                points.extend((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
            p.line(*points, color=color, width=1.3)
            p.circle(x, y, 1.4, color, color)
            if abs(a.offset) > .02:
                p.circle(x, y, radius + 2.5, PINK)
            if a.uid == uid:
                p.circle(x, y, radius + 6, TEXT, width=1.5)
                p.line(x + radius + 7, y, x + radius + 17, y, color=TEXT)
        p.text(ax, ay + ah + 9, "Dot = food   hexagon = agent   ring = event   edges wrap", 11, MUTED)
        rx, rw = w - 235, 213
        for i, name in enumerate(NAMES):
            p.text(rx, 88 + i*25, name, 13, COLORS[i])
            p.text(w-24, 88+i*25, f"{counts[i]:3d}", 14, COLORS[i], anchor="ne", bold=True)
        p.line(rx, 171, w-22, 171)
        agent = self.selected(world, uid)
        if agent:
            p.text(rx, 186, f"AGENT #{agent.uid} / GEN {agent.generation}", 12, MUTED)
            p.text(rx, 211, agent.action, 20, COLORS[agent.lineage], bold=True)
            p.text(rx, 242, f"Energy {agent.energy:.1f}  Age {agent.age}", 12)
            p.bar(rx, 267, rw, agent.energy / (world.cfg.replication_cost + 2*agent.genome.reserve), COLORS[agent.lineage])
            p.text(rx, 286, f"Gene risk      {agent.genome.risk:.2f}\nExpressed risk {agent.risk:.2f}", 12, MUTED)
            if agent.trace:
                p.text(rx, 328, agent.trace.reason, 12, TEXT, width=rw)
        else:
            p.text(rx, 190, "Click an agent", 17, bold=True)
            p.text(rx, 224, "Inspect its energy, inherited genes and latest decision.\n\nSelected agents are not replaced when they die.", 12, MUTED, width=rw)
        if not world.agents:
            p.text(ax+aw/2, ay+ah/2, "EXTINCTION", 28, TEXT, anchor="center", bold=True)
        if world.cap_hits:
            p.text(22, chart_y-8, f"COMPUTATIONAL CAP REACHED: {MAX_AGENTS} agents. Births were blocked; interpret this run cautiously.", 11, AMBER, width=w-44, anchor="sw")
        draw_chart(p, world.samples(), (22, chart_y, w-44, 218),
                   "Available resource stock" if resource_chart else "Population trajectories", resource_chart)

    def concepts(self, world, w, h, index, uid):
        p = self.p
        title = CONCEPTS[index]
        self.heading(w, f"{index+1:02d} / {title}", "Diagrams follow the active run. Pause to inspect; use arrows or the concept selector.")
        y = 112
        if index == 0:
            p.text(32, 89, "Structural schematic · the drawing is an abstraction", 12, MUTED)
            cx, cy, radius = w*.30, h*.43, min(145, h*.23)
            p.circle(cx, cy, radius+7, LINE)
            p.circle(cx, cy, radius, CYAN, width=2)
            p.text(cx, cy-radius-30, "BOUNDARY / AGENT", 14, CYAN, anchor="center")
            p.text(cx, cy-64, "inherited description", 12, MUTED, anchor="center")
            for j, (name, value) in enumerate((("risk", .5), ("efficiency", .7), ("reserve", .55))):
                p.text(cx-88, cy-37+j*30, name, 12)
                p.bar(cx+13, cy-32+j*30, 76, value, COLORS[j])
            p.rect(cx-88, cy+67, 176, 35, fill=PANEL, outline=CYAN)
            p.text(cx, cy+84, "interpreter / rules", 12, CYAN, anchor="center")
            bx = w*.63
            boxes = (("RESOURCE FIELD", GREEN), ("CONSTRUCTOR", CYAN), ("COPIER + MUTATION", PINK), ("SEPARATOR", AMBER))
            for j, (label, color) in enumerate(boxes):
                yy = y + j*91
                p.rect(bx, yy, w*.29, 47, fill=PANEL, outline=color)
                p.text(bx+w*.145, yy+23, label, 13, color, anchor="center")
                if j < 3:
                    p.line(bx+w*.145, yy+51, bx+w*.145, yy+83, color=color, arrow=True)
            p.line(cx+radius+10, cy, bx-12, cy, color=CYAN, arrow=True)
            self.note(w, h, "Description + machinery + energy + separation",
                      "The genome stores three parameters. Fixed Python rules interpret them. Construction spends energy; copying passes genes; separation creates a new independent agent. The boundary is conceptual: this is an artificial ecology.")
        elif index == 1:
            total = world.initial_energy + world.inflow
            current = (sum(world.food), sum(a.energy for a in world.agents), world.heat)
            labels = ("FIELD / available", "AGENTS / stored", "HEAT / dissipated")
            colors = (GREEN, CYAN, RED)
            x, width = 42, w-84
            p.text(x, y, f"Initial energy {world.initial_energy:.1f}  +  actual inflow {world.inflow:.1f}  =  {total:.1f}", 15)
            start = x
            for value, label, color in zip(current, labels, colors):
                part = width * value/max(total, 1)
                if part:
                    p.rect(start, y+57, part, 67, fill=color, outline=BG)
                start += part
            for j, (value, label, color) in enumerate(zip(current, labels, colors)):
                lx = x+j*width/3
                p.text(lx, y+152, label, 13, color)
                p.text(lx, y+178, f"{value:.1f}", 28, color)
            p.line(x+40, y+245, x+width*.45, y+245, color=GREEN, arrow=True)
            p.line(x+width*.53, y+245, x+width-30, y+245, color=RED, arrow=True)
            p.text(x+width*.25, y+264, "forage: transfer", 12, GREEN, anchor="n")
            p.text(x+width*.75, y+264, "living / construction / injury", 12, RED, anchor="n")
            p.text(x, y+319, f"Accounting residual: {world.ledger_error():+.2e}   |   field capacity: {world.cfg.resources:.0f}", 13, MUTED)
            self.note(w, h, "No free offspring. No energy from resting.",
                      "Field capacity is finite. Regrowth adds at most the configured energy per tick, less when patches are full. Foraging moves energy into agents. Every cost goes to heat. Set regrowth to zero to test a closed budget.")
        elif index == 2:
            event = world.last.get("birth")
            if event:
                before, cost, after = event["before"], event["cost"], event["child_energy"]
                p.text(32, y, f"Observed birth at tick {event['tick']}: #{event['uid']} → #{event['child']}", 14, GREEN)
            else:
                cost = world.cfg.replication_cost
                before = cost + 28
                after = (before-cost)/2
                p.text(32, y, "Illustration until the first observed birth (reserve = 14).", 13, MUTED)
            cy = y + 158
            nodes = ((w*.18, "PARENT", before), (w*.58, "PARENT", after), (w*.83, "CHILD", after))
            for x, label, value in nodes:
                p.circle(x, cy, 49, CYAN if label == "PARENT" else GREEN, width=2)
                p.text(x, cy-7, f"{value:.1f}", 23, anchor="center", bold=True)
                p.text(x, cy+74, label, 13, MUTED, anchor="center")
            p.line(w*.26, cy, w*.49, cy, color=CYAN, width=2, arrow=True)
            p.line(w*.38, cy, w*.38, cy-85, w*.83, cy-85, w*.83, cy-54,
                   color=GREEN, arrow=True)
            p.text(w*.63, cy-106, "copy + separate", 12, GREEN, anchor="center")
            p.line(w*.38, cy, w*.38, cy+110, color=RED, arrow=True)
            p.text(w*.38, cy+132, f"{cost:.1f} heat", 13, RED, anchor="center")
            p.text(w*.5, cy+207, f"{before:.1f} − {cost:.1f} = {after:.1f} + {after:.1f}", 24, anchor="center")
            self.note(w, h, "Build → copy → separate",
                      "Reproduction is eligible only when energy ≥ cost + 2 × reserve. After metabolism, eligibility is checked again. Construction cost is dissipated; remaining energy is split equally. Children begin acting next tick.")
        elif index == 3:
            event = world.last.get("mutation")
            parent = event["parent_genome"] if event else asdict(Genome())
            child = event["child_genome"] if event else parent.copy()
            if not event:
                child["risk"] = .61
            p.text(32, y, f"Observed mutation / tick {event['tick']} / child #{event['child']}" if event else "Illustration: one gene changes in the copy.", 14, PINK)
            left, right, bw = 40, w*.55, w*.34
            p.text(left, y+48, "PARENT GENOME", 14, CYAN)
            p.text(right, y+48, "CHILD GENOME", 14, PINK)
            for j, (name, low, high) in enumerate((("risk", .05, .95), ("efficiency", .6, 1.4), ("reserve", 8, 20))):
                yy = y+98+j*87
                for x, genome, color in ((left, parent, CYAN), (right, child, PINK)):
                    p.text(x, yy, f"{name:10s} {genome[name]:.3f}", 15, color)
                    p.bar(x, yy+30, bw, (genome[name]-low)/(high-low), color, 10)
                p.line(left+bw+12, yy+34, right-14, yy+34, color=PINK if parent[name] != child[name] else LINE, arrow=True)
            p.text(40, y+371, f"Mutation probability / birth = {world.cfg.mutation:.0%}     observed mutations = {world.mutations}", 14, MUTED)
            self.note(w, h, "Variation is inherited; improvement is not guaranteed.",
                      "At each birth, probability μ changes one randomly chosen gene by 4–16% of its allowed range, reflected at bounds. The parent does not change. A mutation may help, harm, or have no measurable effect in this environment.")
        elif index == 4:
            event = world.last.get("fight")
            cy = y+120
            p.circle(w*.24, cy, 57, CYAN, width=2)
            p.circle(w*.76, cy, 57, AMBER, width=2)
            p.text(w*.24, cy, "AGENT A", 15, CYAN, anchor="center")
            p.text(w*.76, cy, "AGENT B", 15, AMBER, anchor="center")
            p.line(w*.32, cy, w*.68, cy, color=RED, width=2, arrow=True)
            p.text(w*.5, cy-38, "encounter / injury / transfer", 12, RED, anchor="center")
            p.circle(w*.5, cy+162, 23, GREEN, GREEN)
            p.line(w*.45, cy+155, w*.25, cy+73, color=GREEN, arrow=True)
            p.line(w*.55, cy+155, w*.75, cy+73, color=GREEN, arrow=True)
            p.text(w*.5, cy+205, "the same finite food patch", 13, GREEN, anchor="center")
            if event:
                p.text(36, y+371, f"Last fight t={event['tick']}: #{event['winner']} gained {event['transfer']:.2f}; both lost {event['heat']:.2f} to injury.", 13, width=w-72)
            else:
                p.text(36, y+371, "No fight observed yet. Diagram shows a possible encounter.", 13, MUTED)
            self.note(w, h, "Competition has two mechanisms.",
                      "All agents deplete shared patches, even with competition set to zero. The competition slider controls perceived threat and combat frequency/loot. Nearby fights transfer energy but injure both agents; fleeing costs energy and forfeits feeding.")
        elif index == 5:
            event = world.last.get("adapt")
            old, new = (event["before"], event["after"]) if event else (.5, .42)
            gene = event["gene"] if event else .5
            p.text(34, y, f"Observed adjustment / tick {event['tick']} / #{event['uid']}" if event else "Illustration: an Adaptive agent reacts to injury.", 14, PINK)
            for yy, label, value, color in ((y+67, "INHERITED RISK", gene, CYAN), (y+159, "BEFORE EXPERIENCE", old, MUTED), (y+251, "AFTER EXPERIENCE", new, PINK)):
                p.text(42, yy, label, 14, color)
                p.bar(w*.41, yy+6, w*.46, value, color, 12)
                p.text(w*.91, yy, f"{value:.2f}", 15, color, anchor="ne")
            p.line(w*.37, y+178, w*.37, y+264, color=PINK, arrow=True)
            stimulus = event["stimulus"] if event else "recent injury"
            p.text(42, y+340, f"Trigger: {stimulus}   |   adjustment costs 0.35 energy", 14, PINK)
            self.note(w, h, "A small controller edits its own parameter.",
                      "Only Adaptive agents adjust expressed risk every 40 ticks: injury lowers it, falling energy without injury raises it. Offset is bounded to ±0.25, costs energy, and is NOT inherited. This is parameter adaptation, not source-code rewriting.")
        elif index == 6:
            p.text(32, y, "SURVIVOR DISTRIBUTION / inherited risk", 14, MUTED)
            left, top, cw, ch = 60, y+58, w-100, min(234, h*.33)
            bins = [[0]*12 for _ in range(3)]
            for a in world.agents:
                bins[a.lineage][min(11, int(a.genome.risk*12))] += 1
            maxbin = max(1, max(sum(b[i] for b in bins) for i in range(12)))
            for i in range(12):
                bottom = top+ch
                for lineage in range(3):
                    height = bins[lineage][i]/maxbin*ch
                    if height:
                        p.rect(left+i*cw/12+3, bottom-height, cw/12-6, height, fill=COLORS[lineage], outline=BG)
                    bottom -= height
            p.line(left, top+ch, left+cw, top+ch)
            for value in (0, .5, 1):
                p.text(left+cw*value, top+ch+14, f"{value:.1f}", 12, MUTED, anchor="n")
            p.text(left-12, top, str(maxbin), 11, MUTED, anchor="ne")
            p.text(left, top-25, "agents per bin", 11, MUTED)
            snap = world.snapshot()
            for i, name in enumerate(NAMES):
                value = snap["gene_risk"][i]
                mean = "extinct" if value is None else f"{value:.3f}"
                p.text(40+i*(w-60)/3, top+ch+57, f"{name}\nmean {mean}\nbirths {world.births[i]}", 13, COLORS[i])
            self.note(w, h, "Evolution belongs to populations across generations.",
                      "Births copy genes; mutations introduce variation; unequal reproduction and survival change this distribution. Colors retain founder strategy identity. Strategy labels never mutate. A rising population alone does not demonstrate genetic adaptation.")
        else:
            agent = self.selected(world, uid)
            trace = agent.trace if agent else None
            if not trace:
                p.text(36, y+25, "Select a living agent in the World tab and advance one tick.", 16, MUTED, width=w-72)
            else:
                p.text(32, y, f"#{agent.uid} / {NAMES[agent.lineage]} / {world.cfg.rule} controller", 15, COLORS[agent.lineage])
                widths = (w-104)/3
                inputs = (("ENERGY", f"{trace.energy:.2f}"), ("DANGER", f"{trace.danger:.2f}"), ("ESCAPE", "open" if trace.escape else "blocked"))
                for i, (label, value) in enumerate(inputs):
                    x = 32+i*(widths+20)
                    p.rect(x, y+43, widths, 69, fill=PANEL)
                    p.text(x+14, y+54, label, 11, MUTED)
                    p.text(x+14, y+76, value, 21)
                    p.line(x+widths/2, y+119, x+widths/2, y+147, color=LINE, arrow=True)
                p.rect(32, y+155, w-64, 65, fill=PANEL, outline=CYAN)
                p.text(50, y+169, f"risk {trace.risk:.2f}  |  threat threshold {trace.threshold:.2f}  |  strength ratio {trace.strength:.2f}", 13, CYAN, width=w-100)
                if trace.scores:
                    ymax = max(1, max(abs(s) for s in trace.scores.values()))
                    for i, action in enumerate(ACTIONS):
                        yy = y+246+i*25
                        value = trace.scores.get(action)
                        color = CYAN if action == trace.action else MUTED
                        p.text(42, yy, action, 12, color)
                        mid = w*.58
                        p.line(mid, yy, mid, yy+17)
                        if value is not None:
                            end = mid + value/ymax*w*.23
                            p.line(mid, yy+8, end, yy+8, color=color, width=6)
                            p.text(w-43, yy, f"{value:+.2f}", 12, color, anchor="ne")
                        else:
                            p.text(w-43, yy, "ineligible", 12, MUTED, anchor="ne")
                else:
                    p.line(w*.5, y+227, w*.5, y+270, color=CYAN, arrow=True)
                    p.text(w*.5, y+305, trace.action, 32, CYAN, anchor="center", bold=True)
                    p.text(42, y+349, trace.reason, 14, width=w-84)
            self.note(w, h, "Sense → evaluate → act → pay costs → repeat",
                      "Reflex uses ordered thresholds. Utility ranks explicitly chosen heuristic gains and costs. Hybrid gives extreme danger a survival reflex, otherwise uses scores. These are inspectable engineered rules, not evidence of subjective experience.")

    def note(self, w, h, title, body):
        p = self.p
        y = h-132
        p.line(24, y, w-24, y)
        p.text(30, y+18, title, 17, bold=True)
        p.text(30, y+49, body, 13, MUTED, width=w-60)

    def compare(self, comparison, progress, w, h):
        p = self.p
        self.heading(w, "Compare strategies", "Mixed ecology · equal founders · consecutive seeds · descriptive results, not a universal ranking")
        if not comparison:
            p.text(36, 130, "One lucky trajectory is not enough.", 25, bold=True)
            for i, (name, color, risk) in enumerate(zip(NAMES, COLORS, (.2, .8, .5))):
                x = 38+i*(w-56)/3
                p.circle(x+46, 242, 33, color, width=2)
                p.text(x, 303, name, 18, color)
                p.text(x, 338, f"Starting risk {risk:.1f}\nSame starting energy\nSame resource field", 12, MUTED)
            p.text(38, 444, progress or "Choose trials and ticks above, then run the comparison.", 14, CYAN, width=w-76)
            self.note(w, h, "Compare under the same ecological conditions.",
                      "Every trial includes all three strategies together. The comparison uses the pending sidebar settings and consecutive seeds. The live run pauses. Output includes final means, ranges, survival counts, births and mean trajectories. Export JSON to retain every trial.")
            return
        cfg = comparison["config"]
        p.text(28, 90, f"{len(comparison['runs'])} trials × {comparison['steps']} ticks  |  seeds {comparison['seeds'][0]}–{comparison['seeds'][-1]}  |  {cfg['rule']}", 13, MUTED)
        p.text(28, 116, f"Resource cap {cfg['resources']:g} · inflow ≤{cfg['regrowth']:g} · birth cost {cfg['replication_cost']:g} · μ {cfg['mutation']:.0%} · conflict {cfg['competition']:.0%} · adapt {'on' if cfg['self_modify'] else 'off'}", 11, MUTED, width=w-56)
        cols = (28, w*.27, w*.45, w*.64, w*.82)
        for x, name in zip(cols, ("STRATEGY", "MEAN FINAL", "MIN–MAX", "SURVIVED", "MEAN BIRTHS")):
            p.text(x, 165, name, 11, MUTED)
        for i, row in enumerate(comparison["summary"]):
            yy = 197+i*42
            p.line(28, yy+29, w-28, yy+29)
            values = (row["strategy"], f"{row['mean']:.1f}", f"{row['min']}–{row['max']}",
                      f"{row['surviving_trials']}/{len(comparison['runs'])}", f"{row['mean_births']:.1f}")
            for x, value in zip(cols, values):
                p.text(x, yy, value, 15, COLORS[i])
        histories = [r["history"] for r in comparison["runs"]]
        means = [{"tick": rows[0]["tick"], "population": [statistics.fmean(r["population"][i] for r in rows) for i in range(3)]} for rows in zip(*histories)]
        draw_chart(p, means, (28, 345, w-56, max(165, h-496)), "Mean population across trials")
        capped = sum(r["history"][-1]["cap_hits"] > 0 for r in comparison["runs"])
        warning = f" {capped} trials hit the computational population cap." if capped else ""
        self.note(w, h, "The winner depends on the environment and the rules.",
                  "Ranges are observed minima and maxima, not confidence intervals. Change one parameter and repeat with the same seeds. Acquired risk is separate from inherited risk. Results describe this model only." + warning)


PRESETS = {
    "Balanced": {},
    "Closed budget": {"regrowth": 0},
    "Scarcity": {"resources": 500, "regrowth": 2},
    "No combat": {"competition": 0},
    "High conflict": {"competition": 1},
    "No mutation": {"mutation": 0},
    "Fast variation": {"mutation": .65},
}


class App:
    def __init__(self, cfg=Config(), root=None):
        # Lazy imports keep all headless functions independent of Tcl/Tk.
        import tkinter as tk
        from tkinter import font
        global FONT
        self.tk = tk
        self.root = root or tk.Tk()
        families = {name.casefold(): name for name in font.families(self.root)}
        FONT = families.get("consolas", families.get("dejavu sans mono", "Courier"))
        self.root.title("Algorithmic Arts · Self-Replicator Observatory")
        self.root.configure(bg=BG)
        self.root.geometry("1440x920")
        self.root.minsize(1120, 790)
        self.world = World(cfg)
        self.uid = 2
        self.running = True
        self.tab = "World"
        self.concept = 0
        self.comparison = None
        self.job = None
        self.progress = ""
        self.closed = False
        self.credit = 0
        self.last_frame = time.perf_counter()
        self.pending = {}
        self.status = tk.StringVar(value="Click an agent to inspect its decision. Space: pause · N: step · R: new run")
        self.dirty = tk.StringVar(value="Settings match live run")
        self._build(cfg)
        self.ink = Ink(self.canvas)
        self.view = ObservatoryView(self.ink)
        self.canvas.bind("<Button-1>", self.select_agent)
        self.root.bind("<space>", lambda event: self.shortcut(event, self.toggle))
        self.root.bind("n", lambda event: self.shortcut(event, self.step_once))
        self.root.bind("r", lambda event: self.shortcut(event, self.new_run))
        self.root.bind("<Left>", lambda event: self.shortcut(event, lambda: self.change_concept(-1)))
        self.root.bind("<Right>", lambda event: self.shortcut(event, lambda: self.change_concept(1)))
        self.root.bind("<Escape>", lambda event: self.cancel_compare() if self.job else None)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.after_id = None

    def label(self, parent, text, color=TEXT, size=10, **kwargs):
        widget = self.tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                               font=(FONT, size), anchor="w", **kwargs)
        return widget

    def button(self, parent, text, command, accent=False):
        return self.tk.Button(parent, text=text, command=command, bg="#143344" if accent else PANEL,
                              fg=CYAN if accent else TEXT, activebackground=LINE, activeforeground=TEXT,
                              relief="flat", bd=0, padx=10, pady=7, highlightthickness=1,
                              highlightbackground=LINE, font=(FONT, 10), cursor="hand2")

    def option(self, parent, variable, values, command=None):
        menu = self.tk.OptionMenu(parent, variable, *values, command=command)
        menu.configure(bg=PANEL, fg=TEXT, activebackground=LINE, activeforeground=TEXT,
                       font=(FONT, 10), bd=0, highlightthickness=1, highlightbackground=LINE,
                       anchor="w", relief="flat")
        menu["menu"].configure(bg=PANEL, fg=TEXT, activebackground=LINE, activeforeground=CYAN,
                               font=(FONT, 10), relief="flat")
        return menu

    def _build(self, cfg):
        tk = self.tk
        sidebar = tk.Frame(self.root, bg=PANEL, width=252)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        # A scrolling control panel also supports short laptop displays / scaling.
        scroller = tk.Canvas(sidebar, bg=PANEL, highlightthickness=0, width=240)
        scroll = tk.Scrollbar(sidebar, orient="vertical", command=scroller.yview, width=10,
                              bg=LINE, troughcolor=PANEL, activebackground=MUTED,
                              bd=0, highlightthickness=0, relief="flat")
        scroll.pack(side="right", fill="y")
        scroller.pack(fill="both", expand=True)
        scroller.configure(yscrollcommand=scroll.set)
        controls = tk.Frame(scroller, bg=PANEL, padx=16, pady=18)
        scroller.create_window((0, 0), window=controls, anchor="nw", width=242)
        controls.bind("<Configure>", lambda event: scroller.configure(scrollregion=scroller.bbox("all")))
        self.label(controls, "ALGORITHMIC ARTS", CYAN, 10).pack(fill="x")
        self.label(controls, "Experiment controls", TEXT, 13).pack(fill="x", pady=(8, 12))
        self.preset = tk.StringVar(value="Balanced")
        self.option(controls, self.preset, PRESETS, self.use_preset).pack(fill="x", pady=(0, 12))
        specs = (("resources", "Resource capacity", 0, 4000, 50, "Finite food stock at reset"),
                 ("regrowth", "Resource inflow / tick", 0, 30, .5, "Upper limit; full patches reject inflow"),
                 ("replication_cost", "Replication cost", 2, 40, 1, "Energy dissipated per birth"),
                 ("mutation", "Mutation / birth", 0, 1, .01, "Probability; changes one inherited gene"),
                 ("competition", "Competition", 0, 1, .05, "Threat + combat; food remains shared"))
        for key, label, low, high, resolution, help_text in specs:
            self.label(controls, label, TEXT, 10).pack(fill="x", pady=(6, 0))
            variable = tk.DoubleVar(value=getattr(cfg, key))
            self.pending[key] = variable
            scale = tk.Scale(controls, from_=low, to=high, resolution=resolution, variable=variable,
                             orient="horizontal", bg=PANEL, fg=CYAN, troughcolor=LINE,
                             activebackground=CYAN, highlightthickness=0, bd=0, relief="flat",
                             sliderlength=16, width=8, font=(FONT, 9), length=210)
            scale.pack(fill="x")
            self.label(controls, help_text, MUTED, 8, wraplength=207).pack(fill="x")
        self.label(controls, "Decision rules", TEXT, 10).pack(fill="x", pady=(13, 4))
        self.pending["rule"] = tk.StringVar(value=cfg.rule)
        self.option(controls, self.pending["rule"], RULES).pack(fill="x")
        self.pending["self_modify"] = tk.BooleanVar(value=cfg.self_modify)
        tk.Checkbutton(controls, text="Self-modify (Adaptive)", variable=self.pending["self_modify"],
                       bg=PANEL, fg=PINK, selectcolor=BG, activebackground=PANEL,
                       activeforeground=PINK, highlightthickness=0, anchor="w",
                       font=(FONT, 9)).pack(fill="x", pady=9)
        seed_row = tk.Frame(controls, bg=PANEL)
        seed_row.pack(fill="x", pady=4)
        self.label(seed_row, "Seed", MUTED, 10).pack(side="left")
        self.pending["seed"] = tk.StringVar(value=str(cfg.seed))
        tk.Entry(seed_row, textvariable=self.pending["seed"], bg=BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", width=13, font=(FONT, 10)).pack(side="right", ipady=4)
        self.founders = cfg.founders
        self.button(controls, "New run / apply settings", self.new_run, True).pack(fill="x", pady=(9, 5))
        tk.Label(controls, textvariable=self.dirty, fg=MUTED, bg=PANEL,
                 font=(FONT, 8), wraplength=205, anchor="w", justify="left").pack(fill="x")
        self.label(controls, "Playback ticks / second", MUTED, 9).pack(fill="x", pady=(15, 0))
        self.speed = tk.IntVar(value=20)
        tk.Scale(controls, from_=1, to=100, variable=self.speed, orient="horizontal", bg=PANEL,
                 fg=TEXT, troughcolor=LINE, highlightthickness=0, bd=0, width=7,
                 sliderlength=16, font=(FONT, 9)).pack(fill="x")
        for name, variable in self.pending.items():
            variable.trace_add("write", self.mark_dirty)
        self.button(controls, "Load settings…", self.load_settings).pack(fill="x", pady=(12, 4))
        self.label(controls, "Local simulation · no network\nPython standard library only", MUTED, 8).pack(fill="x", pady=12)

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        nav = tk.Frame(main, bg=BG, padx=16, pady=10)
        nav.pack(fill="x")
        self.nav_buttons = {}
        for tab in ("World", "Mechanisms", "Compare"):
            b = self.button(nav, tab, lambda name=tab: self.set_tab(name))
            b.pack(side="left", padx=(0, 6))
            self.nav_buttons[tab] = b
        self.button(nav, "Export JSON", self.export_json).pack(side="right", padx=(6, 0))
        self.button(nav, "CSV", self.export_csv).pack(side="right")
        self.play_button = self.button(nav, "Pause", self.toggle, True)
        self.play_button.pack(side="right", padx=6)
        self.button(nav, "Step", self.step_once).pack(side="right")
        self.toolbar = tk.Frame(main, bg=BG, padx=16, height=42)
        self.toolbar.pack(fill="x")
        self.world_tools = tk.Frame(self.toolbar, bg=BG)
        self.label(self.world_tools, "Chart", MUTED, 9).pack(side="left", padx=(0, 7))
        self.chart = tk.StringVar(value="Population")
        self.option(self.world_tools, self.chart, ("Population", "Resources")).pack(side="left")
        self.label(self.world_tools, "  Click a hexagon to inspect · Space to pause", MUTED, 9).pack(side="left")
        self.concept_tools = tk.Frame(self.toolbar, bg=BG)
        self.button(self.concept_tools, "←", lambda: self.change_concept(-1)).pack(side="left")
        self.concept_var = tk.StringVar(value=CONCEPTS[0])
        self.option(self.concept_tools, self.concept_var, CONCEPTS, self.choose_concept).pack(side="left", padx=8)
        self.button(self.concept_tools, "→", lambda: self.change_concept(1)).pack(side="left")
        self.compare_tools = tk.Frame(self.toolbar, bg=BG)
        self.trials_var = tk.StringVar(value="5")
        self.steps_var = tk.StringVar(value="600")
        for label, var, options in (("Trials", self.trials_var, ("3", "5", "10")),
                                     ("Ticks", self.steps_var, ("300", "600", "1200"))):
            self.label(self.compare_tools, label, MUTED, 9).pack(side="left", padx=(0, 5))
            self.option(self.compare_tools, var, options).pack(side="left", padx=(0, 10))
        self.compare_button = self.button(self.compare_tools, "Run comparison", self.start_compare, True)
        self.compare_button.pack(side="left")
        self.cancel_button = self.button(self.compare_tools, "Cancel", self.cancel_compare)
        self.cancel_button.pack(side="left", padx=8)
        self.cancel_button.configure(state="disabled")
        tk.Label(main, textvariable=self.status, bg=PANEL, fg=MUTED, anchor="w",
                 font=(FONT, 9), padx=16, pady=7).pack(side="bottom", fill="x")
        self.canvas = tk.Canvas(main, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.set_tab("World")

    def read_config(self):
        values = {name: var.get() for name, var in self.pending.items()}
        values["seed"] = int(values["seed"])
        values["founders"] = self.founders
        return Config(**values)

    def mark_dirty(self, *_):
        try:
            matches = self.read_config() == self.world.cfg
        except (ValueError, self.tk.TclError):
            matches = False
        self.dirty.set("Settings match live run" if matches else "Pending changes. New run applies them; Compare uses them immediately.")

    def use_preset(self, name):
        cfg = replace(Config(), seed=self.world.cfg.seed, **PRESETS[name])
        self.apply_to_controls(cfg)
        self.status.set(f"{name} loaded into controls. New run applies it; Compare uses these settings.")

    def apply_to_controls(self, cfg):
        for name, variable in self.pending.items():
            variable.set(getattr(cfg, name))
        self.founders = cfg.founders
        self.mark_dirty()

    def set_tab(self, name):
        self.tab = name
        for tab, button in self.nav_buttons.items():
            button.configure(bg="#143344" if tab == name else PANEL, fg=CYAN if tab == name else TEXT)
        for frame in (self.world_tools, self.concept_tools, self.compare_tools):
            frame.pack_forget()
        {"World": self.world_tools, "Mechanisms": self.concept_tools, "Compare": self.compare_tools}[name].pack(fill="x")

    def choose_concept(self, name):
        self.concept = CONCEPTS.index(name)

    def change_concept(self, direction):
        self.set_tab("Mechanisms")
        self.concept = (self.concept + direction) % len(CONCEPTS)
        self.concept_var.set(CONCEPTS[self.concept])

    def shortcut(self, event, callback):
        widget_class = event.widget.winfo_class()
        if widget_class in ("Entry", "Scale", "Menubutton"):
            return None
        if event.keysym == "space" and widget_class in ("Button", "Checkbutton"):
            return None
        callback()
        return "break"

    def toggle(self):
        if self.job:
            return
        self.running = not self.running
        self.credit = 0
        self.play_button.configure(text="Pause" if self.running else "Play")

    def step_once(self):
        if self.job:
            return
        self.running = False
        self.play_button.configure(text="Play")
        self.world.step()
        self.draw()

    def new_run(self):
        from tkinter import messagebox
        if self.job:
            self.status.set("Cancel or finish the comparison before starting a new live run.")
            return
        try:
            cfg = self.read_config()
        except (ValueError, self.tk.TclError) as error:
            messagebox.showerror("Invalid settings", str(error), parent=self.root)
            return
        self.world = World(cfg)
        self.uid = 2
        self.credit = 0
        self.mark_dirty()
        self.status.set(f"New run · seed {cfg.seed} · {cfg.rule} · {cfg.founders} founders per strategy")
        self.draw()

    def select_agent(self, event):
        if self.tab != "World":
            return
        ax, ay, aw, ah = self.view.arena
        if not (ax <= event.x <= ax+aw and ay <= event.y <= ay+ah):
            return
        closest = min(self.world.agents, key=lambda a: math.hypot(ax+a.x/COLS*aw-event.x, ay+a.y/ROWS*ah-event.y), default=None)
        if closest and math.hypot(ax+closest.x/COLS*aw-event.x, ay+closest.y/ROWS*ah-event.y) < 20:
            self.uid = closest.uid
            self.status.set(f"Selected #{closest.uid} · {NAMES[closest.lineage]} · Mechanisms → Decision logic explains its latest choice")
            self.draw()

    def start_compare(self):
        from tkinter import messagebox
        if self.job:
            return
        try:
            cfg = self.read_config()
            trials, steps = int(self.trials_var.get()), int(self.steps_var.get())
            if cfg.seed + trials - 1 > 2**32 - 1:
                raise ValueError("Choose a seed with room for all consecutive trial seeds.")
        except (ValueError, self.tk.TclError) as error:
            messagebox.showerror("Invalid comparison settings", str(error), parent=self.root)
            return
        self.running = False
        self.play_button.configure(text="Play", state="disabled")
        self.compare_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.job = {"config": cfg, "trials": trials, "steps": steps, "runs": [], "world": World(cfg)}
        self.progress = f"Trial 1/{trials} · 0/{steps} ticks"
        self.status.set("Comparing frozen settings. Sidebar edits will apply to the next experiment.")
        self.set_tab("Compare")

    def advance_compare(self):
        job = self.job
        if not job:
            return
        deadline = time.perf_counter() + .014
        world = job["world"]
        while world.tick < job["steps"] and time.perf_counter() < deadline:
            world.step()
        self.progress = f"Trial {len(job['runs'])+1}/{job['trials']} · {world.tick}/{job['steps']} ticks"
        self.status.set(self.progress + " · Esc cancels · live run is paused")
        if world.tick == job["steps"]:
            job["runs"].append(world.export())
            if len(job["runs"]) == job["trials"]:
                self.comparison = {"config": asdict(job["config"]), "steps": job["steps"],
                                   "seeds": [job["config"].seed+i for i in range(job["trials"])],
                                   "runs": job["runs"], "summary": summarize(job["runs"])}
                self._finish_compare()
                self.progress = "Comparison complete"
                self.status.set("Comparison complete. JSON includes every trial and its exact configuration. Live run remains paused.")
            else:
                job["world"] = World(replace(job["config"], seed=job["config"].seed+len(job["runs"])))

    def _finish_compare(self):
        self.job = None
        self.play_button.configure(state="normal")
        self.compare_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")

    def cancel_compare(self):
        if self.job:
            self._finish_compare()
            self.progress = "Cancelled. Partial results discarded."
            self.status.set("Comparison cancelled. Previous completed results retained; live run remains paused.")

    def export_json(self):
        from tkinter import filedialog, messagebox
        path = filedialog.asksaveasfilename(parent=self.root, title="Export full experiment",
                                           defaultextension=".json", initialfile=f"replicator-seed-{self.world.cfg.seed}.json",
                                           filetypes=[("JSON", "*.json")])
        if path:
            try:
                write_export(path, self.world, self.comparison)
                self.status.set(f"Exported live run and completed comparison to {Path(path).name}")
            except OSError as error:
                messagebox.showerror("Export failed", str(error), parent=self.root)

    def export_csv(self):
        from tkinter import filedialog, messagebox
        path = filedialog.asksaveasfilename(parent=self.root, title="Export live trajectory",
                                           defaultextension=".csv", initialfile=f"replicator-seed-{self.world.cfg.seed}.csv",
                                           filetypes=[("CSV", "*.csv")])
        if path:
            try:
                write_csv(path, self.world)
                self.status.set("Live trajectory exported with seed and settings. Comparison trials are in JSON export.")
            except OSError as error:
                messagebox.showerror("Export failed", str(error), parent=self.root)

    def load_settings(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(parent=self.root, title="Load settings from an exported experiment",
                                         filetypes=[("JSON", "*.json")])
        if path:
            try:
                cfg = read_config_file(path)
                self.apply_to_controls(cfg)
                self.status.set("Settings loaded. New run recreates the seeded experiment from tick zero.")
            except (OSError, ValueError, TypeError, KeyError) as error:
                messagebox.showerror("Could not load settings", str(error), parent=self.root)

    def draw(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 200 or h < 200:
            return
        self.ink.begin()
        if self.tab == "World":
            self.view.world(self.world, w, h, self.uid, self.chart.get() == "Resources")
        elif self.tab == "Mechanisms":
            self.view.concepts(self.world, w, h, self.concept, self.uid)
        else:
            self.view.compare(None if self.job else self.comparison, self.progress, w, h)
        self.ink.end()

    def frame(self):
        if self.closed:
            return
        now = time.perf_counter()
        elapsed, self.last_frame = min(now-self.last_frame, .2), now
        if self.job:
            self.advance_compare()
        elif self.running:
            self.credit = min(8, self.credit + elapsed*self.speed.get())
            deadline = now + .014
            while self.credit >= 1 and time.perf_counter() < deadline:
                self.world.step()
                self.credit -= 1
        self.draw()
        self.after_id = self.root.after(33, self.frame)

    def close(self):
        self.closed = True
        self.job = None
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.root.destroy()

    def run(self):
        self.frame()
        self.root.mainloop()


def read_config_file(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object containing experiment settings.")
    if "live_run" in data:
        data = data["live_run"]
    elif "comparison" in data:
        data = data["comparison"]
    if not isinstance(data, dict):
        raise ValueError("Expected an experiment object.")
    return Config(**data.get("config", data))


def selftest():
    """Behavioral and accounting checks, including the shared diagram renderer."""
    import tempfile
    import unittest

    class ModelTests(unittest.TestCase):
        def test_reproducibility_and_render_independence(self):
            a, b = World(Config(seed=7)), World(Config(seed=7))
            for _ in range(100):
                a.step()
                b.step()
            self.assertEqual(a.export(), b.export())
            before = a.rng.getstate()
            ink = Ink()
            view = ObservatoryView(ink)
            for i in range(len(CONCEPTS)):
                ink.begin()
                view.concepts(a, 1000, 760, i, a.agents[0].uid)
            self.assertEqual(before, a.rng.getstate())
            a.step()
            b.step()
            self.assertEqual(a.export(), b.export())
            self.assertEqual([asdict(x) for x in a.agents], [asdict(x) for x in b.agents])

        def test_energy_conservation_and_population_accounting(self):
            for rule in RULES:
                w = World(Config(rule=rule, mutation=1, competition=1, seed=19))
                for _ in range(160):
                    w.step()
                    self.assertAlmostEqual(w.ledger_error(), 0, places=6)
                    self.assertTrue(all(0 <= f <= c+1e-9 for f, c in zip(w.food, w.capacity)))
                    self.assertTrue(all(a.energy > 0 and 0 <= a.x < COLS and 0 <= a.y < ROWS for a in w.agents))
                counts = Counter(a.lineage for a in w.agents)
                for i in range(3):
                    self.assertEqual(counts[i], w.cfg.founders+w.births[i]-w.deaths[i])

        def test_empty_closed_world_goes_extinct(self):
            w = World(Config(resources=0, regrowth=0))
            for _ in range(700):
                w.step()
            self.assertEqual(len(w.agents), 0)
            self.assertEqual(sum(w.births), 0)
            self.assertEqual(w.inflow, 0)
            self.assertAlmostEqual(w.heat, w.initial_energy)

        def test_regrowth_bounded_and_full_field_rejects_inflow(self):
            w = World(Config(regrowth=8, competition=0))
            w.step()
            self.assertAlmostEqual(w.inflow, 0)
            prior = w.inflow
            for _ in range(30):
                w.step()
                self.assertLessEqual(w.inflow-prior, w.cfg.regrowth+1e-8)
                prior = w.inflow

        def test_birth_spends_energy_and_does_not_inherit_learning(self):
            w = World(Config(mutation=0))
            a = w.agents[2]
            a.energy = 60
            a.offset = .2
            child = w._birth(a)
            self.assertEqual(child.genome, a.genome)
            self.assertEqual(child.offset, 0)
            self.assertEqual(child.parent, a.uid)
            self.assertEqual(child.generation, a.generation+1)
            self.assertAlmostEqual(a.energy+child.energy+w.cfg.replication_cost, 60)
            self.assertEqual(w.heat, w.cfg.replication_cost)

        def test_mutation_changes_exactly_one_bounded_gene(self):
            w = World(Config(mutation=1))
            for _ in range(50):
                parent = w.agents[0]
                parent.energy = 80
                original = parent.genome
                child = w._birth(parent)
                self.assertEqual(parent.genome, original)
                self.assertEqual(sum(getattr(original, k) != getattr(child.genome, k) for k in asdict(original)), 1)
                self.assertTrue(.05 <= child.genome.risk <= .95)
                self.assertTrue(.6 <= child.genome.efficiency <= 1.4)
                self.assertTrue(8 <= child.genome.reserve <= 20)
            self.assertEqual(w.mutations, 50)

        def test_zero_mutation_preserves_genomes(self):
            w = World(Config(mutation=0))
            for _ in range(200):
                w.step()
            self.assertGreater(sum(w.births), 0)
            self.assertEqual(w.mutations, 0)
            for a in w.agents:
                self.assertEqual(a.genome, Genome(risk=(.2, .8, .5)[a.lineage]))

        def test_adaptation_is_acquired_bounded_and_costly(self):
            w = World()
            a = w.agents[2]
            a.age, a.injury = 40, 1
            energy = a.energy
            w._adapt(a)
            self.assertEqual(a.genome.risk, .5)
            self.assertAlmostEqual(a.risk, .42)
            self.assertAlmostEqual(energy-a.energy, .35)
            for _ in range(8):
                a.injury = 1
                w._adapt(a)
            self.assertAlmostEqual(a.offset, -.25)
            w.cfg = replace(w.cfg, self_modify=False)
            a.injury = 1
            old = asdict(a)
            w._adapt(a)
            self.assertEqual(asdict(a), old)

        def test_survival_reflex_and_action_eligibility(self):
            a = Agent(0, 0, 0, 0, 18, Genome(risk=.2))
            cfg = Config(rule="Hybrid")
            self.assertEqual(decide(a, cfg, .9, .5, True, 4).action, "FLEE")
            self.assertEqual(decide(a, cfg, .9, .5, False, 4).action, "FREEZE")
            self.assertEqual(decide(a, cfg, .9, 1.5, False, 4).action, "FIGHT")
            cfg = replace(cfg, rule="Reflex")
            self.assertEqual(decide(a, cfg, 0, 1, False, 4).action, "FORAGE")
            self.assertEqual(decide(a, cfg, 0, 1, False, 0).action, "REST")
            a.energy = 80
            self.assertEqual(decide(a, cfg, 0, 1, False, 4).action, "REPRODUCE")
            self.assertNotEqual(decide(a, cfg, 0, 1, False, 4, room=False).action, "REPRODUCE")
            a.energy = 3
            self.assertNotIn("REPRODUCE", decide(a, replace(cfg, rule="Utility"), .2, 1, True, 1).scores)

        def test_zero_competition_disables_combat(self):
            w = World(Config(competition=0))
            for _ in range(80):
                w.step()
            self.assertNotIn("fight", w.last)
            self.assertEqual(w.actions["FIGHT"], 0)
            self.assertLess(sum(w.food), w.cfg.resources)

        def test_periodic_geometry(self):
            self.assertAlmostEqual(delta(.1, COLS-.1, COLS), -.2)
            w = World(Config(founders=1))
            a, b = w.agents[:2]
            a.x, a.y = .1, 4
            b.x, b.y = COLS-.1, 4
            found = w._neighbors(a, {(int(b.x), int(b.y)): [b]})
            self.assertEqual(len(found), 1)
            self.assertAlmostEqual(found[0][0], .2)

        def test_cap_is_visible_and_blocks_births(self):
            w = World(Config(founders=1, rule="Reflex", competition=0))
            template = w.agents[0]
            w.agents = [replace(template, uid=i, energy=60) for i in range(MAX_AGENTS)]
            w.next_id = MAX_AGENTS
            w.step()
            self.assertLessEqual(len(w.agents), MAX_AGENTS)
            self.assertGreater(w.cap_hits, 0)
            self.assertEqual(sum(w.births), 0)

        def test_history_keeps_origin_and_exact_endpoint(self):
            w = World(Config(resources=0, founders=1))
            w.agents = []
            for _ in range(10013):
                w.step()
            self.assertLessEqual(len(w.history), 2000)
            self.assertEqual(w.samples()[0]["tick"], 0)
            self.assertEqual(w.samples()[-1]["tick"], 10013)
            self.assertGreater(w.history_interval, 5)

        def test_exports_reload_config_and_reproduce(self):
            w = World(Config(seed=123, rule="Utility"))
            for _ in range(21):
                w.step()
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/"run.json"
                write_export(path, w)
                loaded = read_config_file(path)
                self.assertEqual(loaded, w.cfg)
                replay = World(loaded)
                for _ in range(21):
                    replay.step()
                self.assertEqual(replay.export(), w.export())
                csv_path = Path(tmp)/"run.csv"
                write_csv(csv_path, w)
                with csv_path.open(newline="", encoding="utf-8") as stream:
                    rows = list(csv.DictReader(stream))
                self.assertEqual(int(rows[-1]["tick"]), 21)
                self.assertEqual(json.loads(rows[-1]["config_json"]), asdict(w.cfg))

        def test_comparison_uses_actual_endpoints(self):
            runs = []
            for seed in (1, 2, 3):
                w = World(Config(seed=seed, founders=2))
                for _ in range(25):
                    w.step()
                runs.append(w.export())
            rows = summarize(runs)
            for i, row in enumerate(rows):
                vals = [r["history"][-1]["population"][i] for r in runs]
                self.assertEqual(row["mean"], sum(vals)/3)
                self.assertEqual(row["min"], min(vals))
                self.assertEqual(row["max"], max(vals))

        def test_all_diagrams_have_finite_geometry(self):
            ink = Ink()
            view = ObservatoryView(ink)
            w = World(Config(founders=2, mutation=1))
            for ticks in (0, 120):
                for _ in range(ticks):
                    w.step()
                uid = w.agents[0].uid if w.agents else None
                for width, height in ((868, 650), (1188, 800)):
                    renderers = [lambda: view.world(w, width, height, uid),
                                 lambda: view.compare(None, "", width, height)]
                    renderers += [lambda i=i: view.concepts(w, width, height, i, uid) for i in range(8)]
                    for render in renderers:
                        ink.begin()
                        render()
                        self.assertGreater(len(ink.commands), 5)
                        self.assertTrue(all(math.isfinite(v) for _, coords, _ in ink.commands for v in coords))

        def test_invalid_config_is_rejected(self):
            for kwargs in ({"mutation": 2}, {"regrowth": -1}, {"seed": -1},
                           {"resources": float("nan")}, {"rule": "unknown"},
                           {"seed": 2**32}, {"founders": 1.5}, {"self_modify": "false"}):
                with self.assertRaises(ValueError):
                    Config(**kwargs)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
    return 0 if result.wasSuccessful() else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selftest", action="store_true", help="run deterministic model and renderer checks without a display")
    parser.add_argument("--headless", action="store_true", help="run a comparison without Tk or a display")
    parser.add_argument("--config", type=Path, help="JSON configuration or previously exported experiment")
    parser.add_argument("--seed", type=int, help="override starting seed")
    parser.add_argument("--steps", type=int, default=600, help="ticks per headless trial (1–100000)")
    parser.add_argument("--trials", type=int, default=5, help="headless trials (1–100)")
    parser.add_argument("--output", type=Path, help="write headless comparison to JSON")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        cfg = read_config_file(args.config) if args.config else Config()
        if args.seed is not None:
            cfg = replace(cfg, seed=args.seed)
        if not 1 <= args.steps <= 100000 or not 1 <= args.trials <= 100:
            raise ValueError("steps must be 1–100000 and trials 1–100")
        if args.headless and cfg.seed + args.trials-1 > 2**32-1:
            raise ValueError("Seed range exceeds 4294967295")
        if args.output and not args.headless:
            raise ValueError("--output requires --headless; use Export JSON in the GUI")
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    if args.headless:
        runs = []
        for i in range(args.trials):
            world = World(replace(cfg, seed=cfg.seed+i))
            for _ in range(args.steps):
                world.step()
            runs.append(world.export())
            print(f"trial {i+1}/{args.trials} seed={cfg.seed+i} final={world.snapshot()['population']} ledger={world.ledger_error():+.2e}")
        comparison = {"config": asdict(cfg), "steps": args.steps,
                      "seeds": [cfg.seed+i for i in range(args.trials)], "runs": runs, "summary": summarize(runs)}
        print(json.dumps(comparison["summary"], indent=2))
        if args.output:
            try:
                write_export(args.output, comparison=comparison)
                print(f"Saved {args.output}")
            except OSError as error:
                print(f"Could not save output: {error}", file=sys.stderr)
                return 1
        return 0
    try:
        app = App(cfg)
    except ImportError:
        print("GUI needs Python's tkinter module (often the OS package python3-tk on Linux). No pip packages are needed. --selftest and --headless work without Tk.", file=sys.stderr)
        return 1
    except Exception as error:
        # Report missing display/Tcl setup clearly; do not hide unrelated defects.
        import tkinter as tk
        if not isinstance(error, tk.TclError):
            raise
        print(f"Cannot open Tk window: {error}\nUse a desktop session, or --selftest / --headless.", file=sys.stderr)
        return 1
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
