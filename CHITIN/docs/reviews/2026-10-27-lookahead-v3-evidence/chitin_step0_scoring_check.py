"""Read-only re-score of the Step 0 opponent probe under a proper scoring rule.

Same hook and same rows as chitin_step0_opponent_skill.py (60-tick realized combat-capable share of the nearest
enemy, rows with >=30 observed ticks), but each predictor is scored by MAE and by squared error (Brier/MSE),
the loss that matches an expected-value plug-in. Predictors: persistence indicator (current class), histogram mass
p_aggr (f.opponent), histogram recalibrated (linear fit on the other seed), conditional mean of the share given
the enemy's current action (fit on the other seed). Also a delayed window [t+10, t+69] (the regime contact>=10)
and the 'not currently chasing' subset for the chase share.
"""

import ctypes
import importlib.util
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(
        ctypes.windll.kernel32.GetCurrentProcess(), 0x4000
    )
except Exception:
    pass
SOURCE = Path(r"C:\Users\rmanov\algorithmic-arts\CHITIN\battle_evolution.py")
spec = importlib.util.spec_from_file_location("chitin_probe_c", SOURCE)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
A = m.ACTIONS
CHASE = {"ATTACK", "FLANK", "RAID"}
SHIELD = {"GUARD", "ESCORT"}
COMBAT = CHASE | SHIELD


def collect(seed, ticks=6000):
    w = m.BattleWorld(seed=seed, max_agents=60, episode_ticks=1500, learning=True)
    pending = []
    action_log = defaultdict(dict)
    orig = m.BattleWorld._choose

    def choose(self, a, s):
        f = self.factions[a.faction]
        total = sum(f.opponent)
        observed = total - 8
        conc = max(f.opponent) / total
        gated = observed >= 16 and conc > 0.25
        p_chase = sum(f.opponent[i] for i in (2, 5, 6)) / total
        p_shield = (f.opponent[4] + f.opponent[7]) / total
        e = s.get("enemy")
        if e is not None:
            pending.append(
                (
                    self.tick,
                    f.method,
                    gated,
                    e.uid,
                    e.action,
                    p_chase,
                    p_shield,
                    ((a.x - e.x) ** 2 + (a.y - e.y) ** 2) ** 0.5,
                )
            )
        return orig(self, a, s)

    m.BattleWorld._choose = choose
    try:
        for _ in range(ticks):
            w.step()
            for ag in w.agents:
                action_log[ag.uid][w.tick] = ag.action
    finally:
        m.BattleWorld._choose = orig
    rows = []
    for t, method, gated, uid, act, pc, ps, d in pending:
        log = action_log.get(uid, {})
        out = {}
        for name, lo in (("w0", 1), ("w10", 10)):
            win = [log[k] for k in range(t + lo, t + lo + 60) if k in log]
            if len(win) < 30:
                out = None
                break
            out[name] = (
                sum(x in COMBAT for x in win) / len(win),
                sum(x in CHASE for x in win) / len(win),
            )
        if out is None:
            continue
        rows.append(dict(method=method, gated=gated, act=act, pc=pc, ps=ps, d=d, **out))
    return rows


def fit(rows, win):
    by = defaultdict(list)
    byc = defaultdict(list)
    for r in rows:
        by[r["act"]].append(r[win][0])
        byc[r["act"]].append(r[win][1])
    cm = {k: st.mean(v) for k, v in by.items()}
    cmc = {k: st.mean(v) for k, v in byc.items()}
    # linear recalibration of histogram mass: y = a + b*p
    xs = [r["pc"] + r["ps"] for r in rows]
    ys = [r[win][0] for r in rows]
    mx, my = st.mean(xs), st.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / max(
        1e-12, sum((x - mx) ** 2 for x in xs)
    )
    xc = [r["pc"] for r in rows]
    yc = [r[win][1] for r in rows]
    mxc, myc = st.mean(xc), st.mean(yc)
    bc = sum((x - mxc) * (y - myc) for x, y in zip(xc, yc)) / max(
        1e-12, sum((x - mxc) ** 2 for x in xc)
    )
    return cm, cmc, (my - b * mx, b), (myc - bc * mxc, bc)


def evaluate(train, test, label):
    for win in ("w0", "w10"):
        cm, cmc, (a0, b0), (a1, b1) = fit(train, win)
        gm = st.mean(r[win][0] for r in train)
        for sub_label, sub in (
            (
                "LA gated",
                [r for r in test if r["method"] == "Lookahead" and r["gated"]],
            ),
            ("all gated", [r for r in test if r["gated"]]),
        ):
            if len(sub) < 30:
                continue
            preds = {
                "persist": lambda r: float(r["act"] in COMBAT),
                "hist_p": lambda r: r["pc"] + r["ps"],
                "hist_recal": lambda r: min(
                    1.0, max(0.0, a0 + b0 * (r["pc"] + r["ps"]))
                ),
                "cond_mean": lambda r: cm.get(r["act"], gm),
                "const": lambda r: gm,
            }
            res = []
            for name, fn in preds.items():
                mae = st.mean(abs(r[win][0] - fn(r)) for r in sub)
                mse = st.mean((r[win][0] - fn(r)) ** 2 for r in sub)
                res.append(f"{name} MAE {mae:.3f} MSE {mse:.4f}")
            print(
                f"[{label}] {win} combat share {sub_label} n={len(sub)}: "
                + " | ".join(res)
            )
        # chase share for enemies NOT currently chasing (persistence predicts 0 = contact 1e9 for passive candidates)
        sub = [r for r in test if r["gated"] and r["act"] not in CHASE]
        gmc = st.mean(r[win][1] for r in train)
        preds = {
            "persist(0)": lambda r: 0.0,
            "hist_pchase": lambda r: r["pc"],
            "hist_recal": lambda r: min(1.0, max(0.0, a1 + b1 * r["pc"])),
            "cond_mean": lambda r: cmc.get(r["act"], gmc),
        }
        res = []
        for name, fn in preds.items():
            mae = st.mean(abs(r[win][1] - fn(r)) for r in sub)
            mse = st.mean((r[win][1] - fn(r)) ** 2 for r in sub)
            res.append(f"{name} MAE {mae:.3f} MSE {mse:.4f}")
        print(
            f"[{label}] {win} chase share, enemy not chasing now, all gated n={len(sub)} "
            f"(realized mean {st.mean(r[win][1] for r in sub):.3f}): " + " | ".join(res)
        )
        share0 = sum(r[win][1] < 1e-9 for r in sub) / len(sub)
        print(
            f"[{label}] {win}   share of those rows with realized chase share exactly 0: {100 * share0:.1f}%"
        )


rows101 = collect(101)
print("seed 101 rows", len(rows101), flush=True)
rows202 = collect(202)
print("seed 202 rows", len(rows202), flush=True)
evaluate(rows101, rows202, "fit 101 -> test 202")
evaluate(rows202, rows101, "fit 202 -> test 101")
