"""Extract Lookahead budget / forecast-validation stats from cmp_seed*.json (read-only)."""

import glob
import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
files = sorted(glob.glob(str(Path(sys.argv[1]) / "cmp_seed*.json")))
tot = Counter()
tot_f = 0.0
rows = []
for f in files:
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    for run in d["runs"]:
        s = run["summary"]["stats"]
        snaps = list(run["world"]["episodes"]) + [run["summary"]]
        la_dec = sum(
            fa["decisions"]
            for snap in snaps
            for fa in snap["factions"]
            if fa["method"] == "Lookahead"
        )
        all_dec = sum(fa["decisions"] for snap in snaps for fa in snap["factions"])
        la_actions = Counter()
        for snap in snaps:
            for fa in snap["factions"]:
                if fa["method"] == "Lookahead":
                    la_actions.update(fa["actions"])
        pred = run["summary"]["prediction"]
        row = dict(
            seed=run["seed"],
            learning=run["learning"],
            tps=round(run["ticks_per_second"], 1),
            decisions_stat=s.get("decisions"),
            decisions_sum=all_dec,
            la_decisions=la_dec,
            forecast_rollouts=s.get("forecast_rollouts"),
            rollouts_legacy=s.get("rollouts", 0),
            rollouts_per_la_decision=round(
                s.get("forecast_rollouts", 0) / max(1, la_dec), 2
            ),
            planning_energy=round(s.get("planning_energy", 0), 3),
            energy_spent=round(s.get("energy_spent", 0), 1),
            planning_pct=round(
                100 * s.get("planning_energy", 0) / max(1e-9, s.get("energy_spent", 0)),
                3,
            ),
            fc_registered=s.get("forecasts_registered"),
            fc_evaluated=s.get("forecasts_evaluated"),
            fc_censored=s.get("forecasts_censored"),
            val_registered=s.get("forecast_validations_registered"),
            val_evaluated=s.get("forecast_validations_evaluated"),
            val_censored=s.get("forecast_validations_censored"),
            val_mean_err=pred.get("validation_mean_state_error"),
            long_mean_err=pred.get("mean_absolute_state_error"),
            long_early_death=pred.get("early_death_observations"),
            censor_reasons=pred.get("validation_censor_reasons"),
            interventions=pred.get("validation_interventions"),
            opponent_predictions=s.get("opponent_predictions"),
            unique_opp_obs=s.get("unique_opponent_observations"),
            la_actions=dict(la_actions),
            learner_contexts=sum(len(v) for v in run["world"]["learners"].values()),
            forecasts_len=len(run["world"]["forecasts"]),
            episodes_len=len(run["world"]["episodes"]),
            history_len=len(run["world"]["history"]),
            ledger_error=run["summary"]["ledger_error"],
        )
        rows.append(row)
        for k in (
            "decisions_stat",
            "la_decisions",
            "forecast_rollouts",
            "rollouts_legacy",
            "fc_registered",
            "fc_evaluated",
            "fc_censored",
            "val_registered",
            "val_evaluated",
            "val_censored",
            "opponent_predictions",
            "unique_opp_obs",
        ):
            tot[k] += row[k] or 0
        tot_f += row["planning_energy"]
        tot["energy_spent"] += row["energy_spent"]
for r in rows:
    print(
        {
            k: v
            for k, v in r.items()
            if k not in ("censor_reasons", "interventions", "la_actions")
        }
    )
print(
    "\nTOTALS",
    dict(tot),
    "planning_energy",
    round(tot_f, 3),
    "planning_pct",
    round(100 * tot_f / tot["energy_spent"], 3),
)
print(
    "rollouts per Lookahead decision (pooled):",
    round(tot["forecast_rollouts"] / tot["la_decisions"], 3),
)
print(
    "candidates per Lookahead decision (rollouts/3):",
    round(tot["forecast_rollouts"] / tot["la_decisions"] / 3, 3),
)
print(
    "validation censored share:",
    round(100 * tot["val_censored"] / (tot["val_evaluated"] + tot["val_censored"]), 2),
    "%",
)
# weighted mean short error
num = sum((r["val_mean_err"] or 0) * (r["val_evaluated"] or 0) for r in rows)
print("pooled short validation mean error:", round(num / tot["val_evaluated"], 4))
numl = sum((r["long_mean_err"] or 0) * (r["fc_evaluated"] or 0) for r in rows)
print("pooled long (30/90/180) mean error:", round(numl / tot["fc_evaluated"], 4))
cr = Counter()
iv = Counter()
la = Counter()
for r in rows:
    cr.update(r["censor_reasons"] or {})
    iv.update(r["interventions"] or {})
    la.update(r["la_actions"] or {})
print("censor reasons:", dict(cr))
print("interventions:", dict(iv))
print("Lookahead actions:", dict(la))
# sample one validation outcome + one forecast candidate shape
d = json.loads(Path(files[0]).read_text(encoding="utf-8"))
p = d["runs"][0]["summary"]["prediction"]
print(
    "\nsample validation outcome:",
    p["validation_outcomes"][-1] if p["validation_outcomes"] else None,
)
print("sample long outcome:", p["outcomes"][-1] if p["outcomes"] else None)
fc = [x for x in d["runs"][0]["world"]["forecasts"] if x["method"] == "Lookahead"][-1:]
print("sample forecasts entry:", fc)
print("keys summary:", list(d["runs"][0]["summary"].keys()))
print("stats keys:", sorted(d["runs"][0]["summary"]["stats"].keys()))
