"""V3 plan: LA vs Utility on end population / extinction / births / losses (naive and seed-clustered 95% CI)."""

import runpy, sys, math

sys.argv = [sys.argv[0], sys.argv[1]]
import io

buf = io.StringIO()
if True:
    g = runpy.run_path(sys.argv[0].replace("_util", ""), run_name="v3")
ep, stat = g["ep"], g["stat"]
for epochs, tag in (({1, 2, 3, 4}, "all closed"), ({2, 3, 4}, "epochs 2-4")):
    keys = [k for k in ep if k[2] in epochs]
    print(f"--- {tag}: n={len(keys)}")
    for field in ("births", "losses", "pop"):
        stat(
            [(k[0], ep[k]["Lookahead"][field] - ep[k]["Utility"][field]) for k in keys],
            f"LA-Utility {field}",
        )
    la0 = [ep[k]["Lookahead"]["pop"] == 0 for k in keys]
    ut0 = [ep[k]["Utility"]["pop"] == 0 for k in keys]
    stat(
        [(k[0], float(x) - float(y)) for k, x, y in zip(keys, la0, ut0)],
        "LA-Utility extinct share",
    )
    b = sum(1 for x, y in zip(la0, ut0) if x and not y)
    c = sum(1 for x, y in zip(la0, ut0) if y and not x)
    print(
        f"extinct LA {100 * sum(la0) / len(keys):.1f}% Utility {100 * sum(ut0) / len(keys):.1f}% | only LA {b}, only Utility {c}, McNemar z={(c - b) / math.sqrt(b + c):+.2f}"
    )
    early = sum(1 for k in keys if False)
