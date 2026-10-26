# CHITIN 2.0.1 changed-contract review — 2026-10-26

**Verdict: scoped GO for the four demonstrated correctness contracts, subject to the root's integration/native acceptance.** No remaining blocking code defect was found in the reviewed paths. This is a manual changed-contract review, not a complete AST graph, whole-program proof, categorical strategy-success claim or eight-hour native acceptance.

**Review independence:** this reviewer implemented the narrow RAID contact fix. Lifetime, calibration and endurance changes were independently read and challenged by this reviewer; RAID still relies on the separate root/cross-review for author-independent acceptance.

The frozen optimized `_forecast_lifetime` function was independently executed against production `BattleWorld.step`. Its AST source-segment SHA256 (UTF-8, normalized line endings) is:

`68e6527f691378f73476a84c95defb036336239e5dfe20dc6b833d537fca974b`

## Contracts followed through their consumers

| Changed path | Required invariant and evidence | Disposition |
|---|---|---|
| Sensing → RAID contact → trajectory/target → movement | Rich contact identity supplies both attributes and measured trail; unrelated nearest-contact motion changes neither target nor resulting movement. Same-contact, missing/null contact, ATTACK/FLANK and distant-coordinate controls retained. | Correct; author-owned RAID tests7PASS, root cross-review remains distinct. |
| Post-metabolism state → lifetime trajectory → forecast score | Initial action can earn pre-death yield; future metabolism/death stops later yield, repair and expenditure. Spending never exceeds available energy; birth split is a transfer plus12 construction cost. | Independent exact-step comparison passed6 initial states ×3 horizons. |
| Choice → frozen short point → next decision/death → trust | Short state is measured before the next action/planning charge. Actual action/target/context interference is censored explicitly; death remains an adverse outcome. BUILD uses its actual one-tick transition. | Source and tests cover ordering; no remaining phase mismatch identified. |
| Long frozen forecast → later outcomes | Outcomes survive replanning as descriptive evidence, with action/target/context/replan flags; their errors do not enter short trust. | Correct after the review-found same-action/same-target replan flag gap was fixed. |
| GUI transition → activity revision → probe → completion | Pause/resume or unmap/remap within a probe interval cannot disappear because endpoints match; mixed intervals are discarded, continuous valid intervals accrue once. | O(1) revision guard covers the real mutation handlers; native event delivery is a separate acceptance gate. |

## Lifetime phase and independent oracle

The canonical forecast starts **after current metabolism and before current action**. Thus H1/E0 hunter already at ore can mine now and on four subsequent surviving ticks:2.75 ore. A historically reported H1/E0 **pre-step** actor first becomes H0.78 before forecast creation and earns2.2. Both are correct for their stated phase; the tests retain both.

Independent oracle setup used one stationary hunter, fixed MINE, ordinary production `World.step`, no model-method stubs, no hazards/command/forecaster, and a finite ore node. It executed the current action first, then180 future production steps. Initial H/E pairs were1/0,1/0.32,70/80,0.1/0.1,10/0.69 and70/0.7. Ore, actual energy spent and terminal/nonterminal H/E matched the helper at30/90/180, each residual below1e-9. The helper hash stayed unchanged during the run. The lifetime worker subsequently promoted representative exact-step cases into `tests/test_chitin_lifetime.py`.

The short trajectory includes current action, intervening complete turns and the deadline tick's metabolism/repair, **excluding its next action and planning charge**. Long snapshots include the horizon tick's action. BUILD constructs once, transfers45% of remaining energy to the child and pays only the12 construction units as dissipation. Death is absorbing across every later horizon. No RNG is consumed by the projection or observation ledger.

Audit evidence outside the checkout: `C:\Users\rmanov\Downloads\chitin-concept-audit-20261026\prediction\INDEPENDENT-LIFETIME-REVIEW.json` and `independent_lifetime_review.py`. Native UI and adversarial multi-agent combat timing were not simulated by this oracle; expected combat remains a disclosed approximation.

## Review finding resolved during implementation

The first calibration candidate stored a decision ID but did not compare it when flagging interventions. A same-action/same-target replan, including a new planning charge, therefore left long outcomes marked as uninterrupted. The review raised this; the owner added a `replanned` flag and a failing-then-passing regression. Short settlement remains before decision-ID replacement, so this does not falsely censor valid held-action segments.

A separate root/skeptic review found that a context change followed by death could remove the agent before the long lane recorded its intervention. The root added an actual `World.step` RED-to-GREEN regression and marks pending long-record interventions inside `observe_death` while the agent is still available. This preserves terminal metadata without changing the lifetime helper or the short-error admission rule; resolved.

Epoch resets censor pending short/long outcomes without fabricating accuracy. Aggregate short statistics remain global; no automatic forgiveness or preferred-method reward was introduced. Long error counters remain available separately and no longer feed `predictive_scores` trust.

## Resource cost and residual limitations

- The helper performs one shared pass of at most181 instants per eligible action, captures all short/long points, caps expected combat at60 contact ticks and stops on own death. No nested rerun for each horizon, unbounded search, new dependency or source of randomness was added.
- Measured optimized microcost is about2.73ms/initial-forager prediction versus0.31ms originally (8.75×); local combat about2.34ms versus0.78ms (3×). These are real per-call increases, not whole-app CPU measurements. The owner's3000-tick natural run measured approximately3.0→3.313 process-CPU seconds, with changed trajectories/call counts; it is not a strict identical-work benchmark. Native frame/CPU acceptance must account for the cost, especially a concentrated planner population.
- Short-transition accuracy is not calibration of30/90/180-tick accuracy. Aggregate trust remains global across contexts; the guide explicitly states this. The unchanged trust formula can receive smaller errors at the shorter horizon and hence different authority; that is not proof of improved ecological fitness.
- Terrain, other agents' future choices, hidden future hazards, aging and full branching action planning remain outside the local model. These limits are not mislabeled as repaired by the four-contract change.
- C2 target inertia until the next decision remains the prior low-priority note; no new harm was measured or repair added.
- Soak recording conservatively loses mixed intervals rather than estimating their partial active fraction. Root's native witness is needed to establish real Tk event delivery; mocked tests alone cannot do that. A new source hash requires its own endurance evidence.

The accompanying `.dot` is a manually checked graph of changed producer/consumer and temporal edges. Dashed edges are explicit invalidation or excluded influence, not an assertion that all runtime paths were enumerated.
