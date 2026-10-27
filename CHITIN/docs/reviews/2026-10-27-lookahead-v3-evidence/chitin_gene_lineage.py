"""Read-only: where do founders' inherited genes come from at each epoch start? (method that set best_genes)."""

import importlib.util
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_lineage", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

tally = Counter()
counts = Counter()
gene_dev = []
orig_adv = m.BattleWorld.advance_episode


def sync(world):
    """Attribute any new best_fitness record to the epoch/method active right now."""
    last = world.__dict__.setdefault("_last_best", {})
    for f in world.factions:
        if last.get(f.id) != f.best_fitness:
            last[f.id] = f.best_fitness
            if world.episode >= 1:
                f._src = (world.episode, f.method)


def patched(self):
    if self.episode >= 1:
        sync(self)  # records set during the closing epoch belong to it
    orig_adv(self)
    if self.episode > 1:
        for f in self.factions:
            src = getattr(f, "_src", None)
            counts["inherited"] += 1
            if src is None:
                tally["never_set"] += 1
                continue
            tally[("epochs_back", self.episode - src[0])] += 1
            tally["same_method" if src[1] == f.method else "other_method"] += 1
            if src[1] == "Lookahead" and f.method != "Lookahead":
                counts["LA_to_other"] += 1
            if src[1] != "Lookahead" and f.method == "Lookahead":
                counts["other_to_LA"] += 1
            if f.method == "Opponent" and src[1] == "Lookahead":
                counts["LA_to_Opponent"] += 1
            gene_dev.append(max(abs(g - 1) for g in f.best_genes))
    self.__dict__["_last_best"] = {f.id: f.best_fitness for f in self.factions}


m.BattleWorld.advance_episode = patched
for seed in (101, 202, 303, 404):
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500)
    for _ in range(6000):
        w.step()
        sync(w)
print(dict(tally))
print(dict(counts))
if gene_dev:
    gene_dev.sort()
    print(
        f"max |gene-1| of inherited genome: median {gene_dev[len(gene_dev) // 2]:.3f}, max {gene_dev[-1]:.3f}"
    )
