"""CHITIN Lookahead V3 comparison tool, frozen at registration (CHITIN/PLAN_LOOKAHEAD_V3_BG.md, sections 3-4).

Usage: chitin_compare.py <glob> [--epochs a-b] [--rows file.jsonl]

Read-only over the JSON written by `battle_evolution.py --headless --output`; stdlib only.
Row model of aggregate_methods.py: one row per (seed, learning, epoch, faction); snaps = episodes + [summary];
an epoch is closed when its index < len(snaps). Tables, contrasts and the rule use the closed epochs inside
--epochs (default 2-4, the registered primary window); the per-epoch breakdown and the run descriptives use
every closed epoch. Descriptive CIs are 1.96 * SE, naive and clustered by seed (both learning states of a
seed form one cluster). The registered rule uses Z_RULE * max(naive SE, seed SE); its contrasts and constants
are fixed in the code, not arguments. --rows writes every closed epoch as thin JSONL, so the raw JSON is not
needed for a re-analysis.
"""

import argparse
import glob
import json
import math
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

Z_DESC = 1.96
Z_RULE = 2.394  # Bonferroni for the 3 primary contrasts, two-sided, alpha .05
FOUR = ("Utility", "UCB", "Q-learning", "Opponent")
ROW_FIELDS = (
    "seed",
    "learning",
    "epoch",
    "faction",
    "method",
    "score",
    "births",
    "kills",
    "losses",
    "decisions",
    "pop",
    "version",
)


def load(pattern):
    """Return (files, rows of closed epochs, per-world descriptives)."""
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"no files match {pattern}")
    rows, worlds = [], []
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for run in d["runs"]:
            snaps = list(run["world"]["episodes"]) + [run["summary"]]
            limit = run["world"]["config"]["episode_ticks"]
            pred = run["summary"].get("prediction") or {}
            worlds.append(
                {
                    "seed": run["seed"],
                    "learning": run["learning"],
                    "tps": run["ticks_per_second"],
                    "closed": len(snaps) - 1,
                    "early": [
                        ep
                        for ep, snap in enumerate(snaps[:-1], 1)
                        if snap["episode_tick"] < limit
                    ],
                    "ledger": max(abs(snap["ledger_error"]) for snap in snaps),
                    "version": run["summary"]["version"],
                    "pred": pred,
                }
            )
            for ep, snap in enumerate(snaps[:-1], 1):
                pops = snap.get("populations") or [None] * 6
                for fa in snap["factions"]:
                    rows.append(
                        {
                            "seed": run["seed"],
                            "learning": run["learning"],
                            "epoch": ep,
                            "faction": fa["id"],
                            "method": fa["method"],
                            "score": fa["score"],
                            "births": fa["births"],
                            "kills": fa["kills"],
                            "losses": fa["losses"],
                            "decisions": fa["decisions"],
                            "pop": pops[fa["id"]],
                            "version": snap.get("version"),
                        }
                    )
    return files, rows, worlds


def ses(pairs):
    """pairs: (seed, value). Mean, sd, naive SE and seed-clustered SE (no small-sample correction)."""
    vals = [v for _, v in pairs]
    n = len(vals)
    m = st.mean(vals)
    sd = st.stdev(vals)
    g = defaultdict(float)
    for s, v in pairs:
        g[s] += v - m
    return n, m, sd, sd / math.sqrt(n), math.sqrt(sum(x * x for x in g.values())) / n


def stat(pairs, label):
    n, m, sd, naive, cl = ses(pairs)
    print(
        f"{label:34} n={n:4} mean={m:+7.2f} sd={sd:6.2f} naive+/-{Z_DESC * naive:5.2f} "
        f"seed+/-{Z_DESC * cl:5.2f} deff={(cl / naive) ** 2:4.2f}"
    )


def extinct(ep, keys, a, b):
    xa = [ep[k][a]["pop"] == 0 for k in keys]
    xb = [ep[k][b]["pop"] == 0 for k in keys]
    only_a = sum(1 for x, y in zip(xa, xb) if x and not y)
    only_b = sum(1 for x, y in zip(xa, xb) if y and not x)
    z = (
        (only_b - only_a) / math.sqrt(only_a + only_b)
        if only_a + only_b
        else float("nan")
    )
    tag = "LA" if a == "Lookahead" else a
    stat(
        [(k[0], float(x) - float(y)) for k, x, y in zip(keys, xa, xb)],
        f"{tag}-{b} extinct share",
    )
    print(
        f"extinct {tag} {100 * sum(xa) / len(keys):.1f}% {b} {100 * sum(xb) / len(keys):.1f}% | "
        f"only {tag} {only_a}, only {b} {only_b}, McNemar z={z:+.2f}"
    )


def method_table(subset, label):
    by = defaultdict(list)
    for r in subset:
        by[r["method"]].append(r)
    print(
        f"\n== {label}: {len({(r['seed'], r['learning'], r['epoch']) for r in subset})} epochs =="
    )
    print(
        f"{'method':11} {'n':>4} {'score mean':>10} {'median':>8} {'top1 %':>7} {'rank':>5} {'births':>7} "
        f"{'kills':>6} {'losses':>7} {'pop end':>8} {'decis':>7}"
    )
    for m, rs in sorted(by.items(), key=lambda kv: -st.mean(r["score"] for r in kv[1])):
        n = len(rs)
        print(
            f"{m:11} {n:4} {st.mean(r['score'] for r in rs):10.2f} {st.median(r['score'] for r in rs):8.2f} "
            f"{100 * sum(r['top'] for r in rs) / n:6.1f}% {st.mean(r['rank'] for r in rs):5.2f} "
            f"{st.mean(r['births'] for r in rs):7.2f} {st.mean(r['kills'] for r in rs):6.2f} "
            f"{st.mean(r['losses'] for r in rs):7.2f} "
            f"{st.mean(r['pop'] for r in rs if r['pop'] is not None):8.2f} {st.mean(r['decisions'] for r in rs):7.0f}"
        )


def primary(ep, keys):
    """The three registered contrasts, unit = (seed, learning, epoch)."""
    return (
        (
            "P1 score LA-Utility",
            [
                (k[0], ep[k]["Lookahead"]["score"] - ep[k]["Utility"]["score"])
                for k in keys
            ],
        ),
        (
            "P2 pop LA-Utility",
            [(k[0], ep[k]["Lookahead"]["pop"] - ep[k]["Utility"]["pop"]) for k in keys],
        ),
        (
            "P3 extinct LA-Utility",
            [
                (
                    k[0],
                    float(ep[k]["Lookahead"]["pop"] == 0)
                    - float(ep[k]["Utility"]["pop"] == 0),
                )
                for k in keys
            ],
        ),
    )


def contrasts(ep, keys):
    stat([(k[0], ep[k]["Lookahead"]["score"]) for k in keys], "LA score (absolute)")
    for a, b in (
        ("Lookahead", "Utility"),
        ("Lookahead", "Opponent"),
        ("Opponent", "Utility"),
        ("Lookahead", "UCB"),
    ):
        tag = "LA" if a == "Lookahead" else a
        stat(
            [(k[0], ep[k][a]["score"] - ep[k][b]["score"]) for k in keys],
            f"{tag}-{b} score",
        )
    stat(
        [
            (
                k[0],
                ep[k]["Lookahead"]["score"] - st.mean(ep[k][o]["score"] for o in FOUR),
            )
            for k in keys
        ],
        "LA-4 serious score",
    )
    for b in ("Opponent", "Utility"):
        for field, name in (
            ("births", "births"),
            ("losses", "losses"),
            ("pop", "end population"),
        ):
            stat(
                [(k[0], ep[k]["Lookahead"][field] - ep[k][b][field]) for k in keys],
                f"LA-{b} {name}",
            )
        extinct(ep, keys, "Lookahead", b)
    top = sum(1 for k in keys if ep[k]["Lookahead"]["top"])
    print(f"LA first place {top}/{len(keys)} = {100 * top / len(keys):.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "pattern", help="glob of headless --output JSON files, e.g. ...\\cmp_v3_*.json"
    )
    ap.add_argument(
        "--epochs", default="2-4", help="closed epoch index range a-b (default 2-4)"
    )
    ap.add_argument("--rows", type=Path, help="write closed-epoch rows as JSONL")
    args = ap.parse_args()
    match = re.fullmatch(r"(\d+)-(\d+)", args.epochs)
    if not match:
        raise SystemExit("--epochs must look like a-b, e.g. 2-4")
    sel = set(range(int(match[1]), int(match[2]) + 1))

    files, rows, worlds = load(args.pattern)
    by_epoch = defaultdict(list)
    for r in rows:
        by_epoch[(r["seed"], r["learning"], r["epoch"])].append(r)
    for rs in by_epoch.values():
        scores = [r["score"] for r in rs]
        best = max(scores)
        for r in rs:
            r["top"] = abs(r["score"] - best) <= 1e-9
            r["rank"] = 1 + sum(s > r["score"] + 1e-9 for s in scores)
    if args.rows:
        with args.rows.open("w", encoding="utf-8", newline="\n") as fh:
            for r in rows:
                fh.write(json.dumps({k: r[k] for k in ROW_FIELDS}) + "\n")

    chosen = [r for r in rows if r["epoch"] in sel]
    ep = defaultdict(dict)  # (seed, learning, epoch) -> method -> row
    for r in chosen:
        ep[(r["seed"], r["learning"], r["epoch"])][r["method"]] = r
    keys = list(ep)
    print(
        f"files {len(files)} | worlds {len(worlds)} | seeds {len({w['seed'] for w in worlds})} | "
        f"closed epochs {len(by_epoch)} | selected epochs {args.epochs}: {len(keys)} | rows {len(rows)}"
    )
    print("versions", sorted(ascii(v) for v in {w["version"] for w in worlds}))
    print(
        "closed epochs per world",
        dict(sorted(Counter(w["closed"] for w in worlds).items())),
    )

    # Table A: per-method outcomes (aggregate_methods.py).
    method_table(chosen, f"closed epochs {args.epochs}, all runs")
    method_table(
        [r for r in chosen if r["learning"]],
        f"closed epochs {args.epochs}, learning ON",
    )
    method_table(
        [r for r in chosen if not r["learning"]],
        f"closed epochs {args.epochs}, learning OFF (Q/UCB ablated)",
    )
    diffs = [
        ep[k]["Lookahead"]["score"]
        - st.mean(r["score"] for m, r in ep[k].items() if m != "Lookahead")
        for k in keys
    ]
    n = len(diffs)
    se = st.stdev(diffs) / math.sqrt(n)
    wins = sum(x > 0 for x in diffs)
    print(
        f"\nPaired per epoch (n={n}): Lookahead - others mean = {st.mean(diffs):+.2f} +/- {Z_DESC * se:.2f} "
        f"(95% CI) | epochs where Lookahead > others: {wins}/{n} = {100 * wins / n:.0f}%"
    )
    print(f"sign test z = {(wins - n / 2) / math.sqrt(n / 4):+.2f} (|z|>1.96 ~ p<0.05)")
    top = sum(1 for k in keys if ep[k]["Lookahead"]["top"])
    print(
        f"Lookahead ranks first in {top}/{n} epochs = {100 * top / n:.0f}% (chance 16.7%)"
    )

    # Table B: paired contrasts within the same world and epoch.
    print(
        f"\n--- contrasts, epochs {args.epochs}: {len(keys)} epochs, {len({k[0] for k in keys})} seeds"
    )
    contrasts(ep, keys)
    for state in (True, False):
        sub = [k for k in keys if k[1] == state]
        print(f"--- learning {'ON' if state else 'OFF'}: {len(sub)} epochs")
        for name, pairs in primary(ep, sub):
            stat(pairs, name)

    # Per-epoch breakdown over every closed epoch; epoch 1 has the fixed method order.
    full = defaultdict(dict)
    for r in rows:
        full[(r["seed"], r["learning"], r["epoch"])][r["method"]] = r
    print("\n--- by epoch index (all closed epochs)")
    for e in sorted({k[2] for k in full}):
        ks = [k for k in full if k[2] == e]
        for b, tag in (("Opponent", "Opp"), ("Utility", "Util")):
            d = [full[k]["Lookahead"]["score"] - full[k][b]["score"] for k in ks]
            sd = st.stdev(d) if len(d) > 1 else float("nan")
            print(
                f"epoch {e}: LA-{tag} {st.mean(d):+.2f} +/-{Z_DESC * sd / math.sqrt(len(d)):.2f} sd {sd:.2f} n={len(d)}"
            )

    # Registered rule (plan section 4).
    print(
        f"\n--- registered rule: Z={Z_RULE}, SE = wider of naive and seed-clustered, epochs {args.epochs}"
    )
    ci = {}
    for name, pairs in primary(ep, keys):
        n, m, sd, naive, cl = ses(pairs)
        wide = max(naive, cl)
        ci[name] = (m - Z_RULE * wide, m + Z_RULE * wide)
        print(
            f"{name:24} n={n} mean={m:+.4f} naiveSE={naive:.4f} seedSE={cl:.4f} "
            f"wider={'naive' if naive >= cl else 'seed'} half={Z_RULE * wide:.4f} "
            f"CI=[{ci[name][0]:+.4f}; {ci[name][1]:+.4f}]"
        )
    trigger = (
        ci["P1 score LA-Utility"][1] < 0
        or ci["P2 pop LA-Utility"][1] < 0
        or ci["P3 extinct LA-Utility"][0] > 0
    )
    print("decision:", "TRIGGER" if trigger else "CLOSE")

    # Run descriptives (do not decide).
    print("\n--- descriptives")
    early_sel = sum(1 for w in worlds for e in w["early"] if e in sel)
    early_all = sum(len(w["early"]) for w in worlds)
    print(
        f"early-closed epochs: selected {early_sel}/{len(keys)} = {100 * early_sel / len(keys):.1f}% | "
        f"all closed {early_all}/{len(by_epoch)} = {100 * early_all / len(by_epoch):.1f}%"
    )
    tps = [w["tps"] for w in worlds]
    print(
        f"ticks/s per world: min {min(tps):.1f} median {st.median(tps):.1f} max {max(tps):.1f} (n={len(tps)})"
    )
    print(
        f"max |ledger_error| over all snapshots: {max(w['ledger'] for w in worlds):.3e}"
    )
    for label, count, censored, err in (
        (
            "short (validation)",
            "validation_evaluated",
            "validation_censored",
            "validation_mean_state_error",
        ),
        ("long (30/90/180)", "evaluated", None, "mean_absolute_state_error"),
    ):
        tot = sum(w["pred"].get(count) or 0 for w in worlds)
        pooled = sum(
            (w["pred"].get(err) or 0) * (w["pred"].get(count) or 0) for w in worlds
        ) / max(1, tot)
        line = f"prediction {label}: evaluated {tot}, pooled mean error {pooled:.3f}"
        if censored:
            cens = sum(w["pred"].get(censored) or 0 for w in worlds)
            line += f", censored {cens} = {100 * cens / max(1, cens + tot):.2f}%"
        print(line)


if __name__ == "__main__":
    main()
