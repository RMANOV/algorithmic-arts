# CHITIN — The Island Learns

An autonomous, multicolored battle ecology derived from **Self-Replicator Observatory 1.2**. The original `self_replicator.py` and its documentation are preserved. The new runtime is the single file `battle_evolution.py`: Python 3.10+, the standard library and the Tk supplied with the Python/OS distribution. No pip packages, network access, external fonts, images, browser, account or server.

```bash
python battle_evolution.py
python battle_evolution.py --screensaver --max-agents 60
```

The Windows ZIP includes three double-click launchers. Extract it before opening `START.cmd`, `SCREENSAVER.cmd` or `TEST_8_HOURS.cmd`. They use the same installed Python/Tk as the other Algorithmic Arts pieces, or a suitable `python/python.exe` already supplied by the user. They install nothing and require no administrator rights. This is a fullscreen artwork, not a replacement for Windows security locking.

## What happens without intervention

Six populations of mechanical crabs mine metal, construct descendants, fight and salvage bodies. Each population uses a different decision method. Methods rotate between colors at new epochs; the method-labelled counters reset, while completed epoch summaries preserve their actual assignments. Heritable action weights mutate; acquired Q/UCB values form separate method-level cultural memory.

The director switches between **Nugget rush, Scarcity, Moving seams, Siege, Tempest and Arms race** at seeded random intervals. It introduces temporary hazards and gradually opens more tactical choices. New epochs prevent a finished battle or extinction from leaving a static screen. Learning tables persist with mode/level context. Complexity is a scheduled curriculum, not a claim that elapsed time proves mastery.

Five observational lenses cycle through ecology, tactical intent, feedback genealogy and command. The focus moves between real living agents. Every visible target, strike, birth and selected decision comes from model state. A separate last-outcome label names its action and tick; current choice scores are not presented as already achieved rewards. Color remains a faction identity, not an assurance of immutable genes or one permanent algorithm.

## Strategies and consequences

| Method | Actual mechanism |
| --- | --- |
| Reflex | Resource/strength thresholds with shared emergency avoidance. |
| Utility | Explicit resource, force-balance, health and cost scores. |
| UCB | Contextual realized reward estimates and an exploration bonus, combined with utility. |
| Q-learning | Tabular delayed-transition updates with a legal-next-action bootstrap. |
| Opponent | Deduplicated observed enemy decisions; confidence-gated response to their action distribution. |
| Lookahead | Bounded 30/90/180-tick projections of energy, survival, food depletion and offspring cost, plus local-motion interception. Predictions are explicitly fallible and measured against later observations. |

Actions are **MINE, BUILD, ATTACK, RETREAT, GUARD, FLANK, RAID and ESCORT**. A stationary RETREAT serves as WAIT when there is no enemy or environmental threat. Missing resources/targets cannot become physically eligible merely through a high learned score. Shared emergency avoidance can override every method.

Reward uses realized metal extraction, damage, injury, energy expenditure and offspring survival. Energy transferred to a child is distinguished from dissipated construction cost. The BUILD transition captures its own post-action observation; its delayed result is credited exactly once. An unfinished offspring observation at an epoch boundary is counted as censored, not fabricated as success or failure.

Metal follows an explicit per-epoch balance: ore + carried metal + body metal + reserve. Mining and reserve showers transfer metal; construction puts it into a body; death returns scrap. A new epoch explicitly provisions a new arena. Energy is separate: foragers consume a bounded renewable food stock; hunters transfer actual victim energy with conversion loss. Maintenance, repair, movement, combat, construction and planning dissipate energy. There is no unlimited solar subsidy.

## Predation, scarcity and earned offspring

The default world starts with **24 organisms**, four per faction, and allows at most **60**. Three founders per faction forage; one is a faster hunter. Both need metal, but hunters acquire energy through actual predation. Damage and feeding are capped by the victim’s remaining health and energy. The prey–predator coupling is inspired by Lotka–Volterra; this is an individual-based spatial model, not a numerical solution of the classical equations and not a promise of periodic cycles.

The shared food stock regenerates logistically with a finite capacity. Consumption can exceed renewal, causing scarcity, starvation and contraction. Saturating intake leaves room for stock recovery after a collapse. These Malthusian crises arise from resource pressure rather than a timer that kills a population. Epoch renewal is a separately disclosed theatrical reset.

Every birth spends **3.5 personal merit**, six metal and construction energy, plus the parent-to-child energy split. It also requires maturity, sufficient health and energy and a recovery interval. Merit comes from actual extraction/combat contributions, cannot be inherited, and is charged anew for each birth. Children inherit mutated traits; commander rank grants no fertility exemption. Survival of descendants remains a separate delayed outcome.

## Command, control and prediction

Each faction can form a commander, lieutenants and members. Leadership follows measured lifetime contribution and surviving offspring, with hysteresis to avoid constant rank switching. Orders are broadcast every 24 ticks, over a direct range of 22 world units or one relay hop of 12. A received target is frozen and expires after 70 ticks; an isolated unit can finish its last mission but learns no new orders. Commander death invalidates its mission immediately, and the next broadcast elects a successor. This uses an authoritative own-faction liveness registry, a deliberate simplification rather than a physical radio simulation. Enemies are observed locally; the network does not remotely track them through the map.

HUNT, RAID, FORAGE and REGROUP adjust real tactical scores and movement. The same physical rules apply to every decision method. Emergency avoidance remains stronger than command advice. Crowns, chevrons and the restrained C2 lens show actual ranks and links rather than decorative authority.

Lookahead evaluates three horizons (30/90/180 model ticks; about 1.7/5/10 seconds at normal speed), anticipating food runway, engagement costs and reproductive burden. A small real energy cost accompanies planning. Interception uses visible trail displacement with a bounded lead, never the enemy’s private intended destination. RAID scoring and interception use the same selected contact, including its own trail; distant frozen command coordinates remain frozen. Hypothetical planning consumes neither random stream.

Version 2.0.1 uses a shared, bounded local lifetime trajectory. Death stops all further resource gains and energy expenditure while preserving earlier gains; spending is capped by available energy. Projection starts after the current metabolism and before the current action. Short validation ends before the next decision and its new planning cost; long horizon samples are taken after that horizon's action. These phases are intentionally distinct.

Confidence uses separate fixed-action short-segment observations (normally 8–12 ticks; BUILD 1 tick). The original trust formula and score weights remain unchanged. Long 30/90/180 outcomes are still reported, with intervening replans/action/target/context changes, but their mixed errors no longer drive confidence. Death remains evidence; interrupted contexts and epoch boundaries are explicitly counted as censored. Outcome histories are bounded to 120 entries per lane; aggregate short-error statistics remain global and are not a per-role or per-regime probability calibration. Good short predictions do not establish accurate long predictions. A visible flash warning can redirect mining toward one of at most eight safer known deposits before the pulse arrives.

This remains fixed-action heuristic projection, not branching multi-action planning. Terrain, other organisms' future choices and unannounced hazards are not fully rolled out. No categorical Lookahead victory is promised or used as a correctness criterion.

Smarter decisions can earn greater survival, descendants and command influence. No method receives extra health, damage or fertility merely because it is called predictive. Comparisons measure whether the advantage emerges; there is no guaranteed winner or universal monotonic improvement.

## The environment is an opponent

| Visitor | Mechanical effect and visible signal |
| --- | --- |
| Ice | Temporary slow field; a crystalline footprint marks it. |
| Flash | Local warning followed by a short damaging discharge, then safe residual decay. No fullscreen strobe. |
| Sandworm | Moving, turning predator; the head's danger ring is physical, trailing segments are an illustrative wake. |
| Mountains | Temporary exclusion area that changes routes; a ring shows the actual footprint. |
| River | Current and slow water in a bounded basin, with a horizontal ford. |
| Alien | Moving adversary attracted to valuable cargo, with a visible path and contact danger. |
| Relic | Unknown beneficial or harmful contact effect, learned through experience. Its hidden polarity is not revealed by the renderer. |

Warnings precede physical activation. Hazards expire, while the director introduces new situations. Local separation keeps individual agents legible without exceeding their movement budget or consuming decision randomness.

## Controls

| Input | Result |
| --- | --- |
| Space | Pause/resume. |
| F / F11 | Toggle fullscreen. |
| H | Toggle telemetry. |
| Click a crab | Inspect its actual current choice and last observed outcome. |
| M | Next resource regime. |
| N | Next epoch, retaining learned method memory. |
| R | Next seed and a fresh experiment. |
| [ / ] | Playback speed; model tick semantics remain fixed. |
| E | Export the observed experiment as JSON. |
| Esc | Leave fullscreen; in a normal window, close. |

Minimizing suspends simulation and drawing. Restore discards elapsed catch-up debt. The default drawing target is 20 fps, with cooperative pacing that leaves time between expensive frames. This is not an OS CPU quota. The Windows launchers use a 60-agent cap; the CLI can select another bounded cap. Models, history, events, forecasts, observer caches, color cache and Canvas pools all have explicit finite domains or limits.

## Reproducibility and honest comparisons

```bash
python battle_evolution.py --selftest
python -m unittest discover -s tests -p 'test_battle*.py' -v
python battle_evolution.py --headless --seed 101 --steps 6000 --trials 5 --compare-learning --output comparison.json
```

The paired comparison disables **Q/UCB feedback and exploration only**. Opponent observations, genetic inheritance and mutation remain active. Common seeds reproduce initialization; policy changes can alter subsequent random draws and encounters. These are shared-ecology descriptive comparisons, not isolated estimates of policy fitness or a theorem that learning wins.

Exports include configuration, model version, learners, recent forecasts, epoch summaries and bounded histories. The same seed/config/model reproduces an automatic run. Export is evidence and configuration, **not a saved-game checkpoint loader**. The bounded timeline cannot reconstruct an arbitrarily long manually controlled session. Utility and rollout scores are heuristic quantities, not calibrated probabilities.

## The Windows endurance report

`TEST_8_HOURS.cmd` starts a native window and a new JSON file under `reports`. The report records its own source hash, Python/Tk/platform, active time, process CPU, resident/working-set memory, Canvas count, learner contexts, resets, model state and errors. It updates atomically every minute. Existing reports are never silently overwritten.

Version 2.0.1 conservatively excludes an entire probe interval when pause/resume, visibility, manual reset or export-dialog transitions occurred inside it, even if both sampled endpoints are running. This can undercount active fractions near transitions; it cannot turn those paused fractions into endurance success. A run from another source hash does not accept this version.

```bash
python battle_evolution.py --max-agents 60 --soak-hours 8 --soak-report reports/new-test.json
```

`completed` means eight hours of mapped, non-iconic, advancing GUI execution. Paused, minimized and long interrupted intervals are excluded. Mapped does not prove the window was unobscured or watched by a person. `aborted` means an early normal close; `failed` records an observed error. A leftover `running` report after a crash is incomplete. A missing RSS measurement is `null`, never zero. Completion is a duration result; assess the recorded resource measurements separately.

The Windows RSS API definitions are cached once, including on Python 3.10; repeated probes must not accumulate ctypes classes. Callback exceptions stop the simulation and fail the report. A transient report-write error also stops the run and has a bounded failure-report retry, rather than silently returning success. The application does not change OS sleep/security policy.

## Research and provenance

The conceptual seed is Anatoly Dneprov's 1958 story *Crabs on the Island*. Exact original artifact provenance was matched against the October 12 source hash and delivery report. Both existing files in the Drive folder **Автомисляч** were read in full: the Predictive OODA Memory OS specification v1.1 and the synthesis from Boolean gates to a verifiable reasoning system. Their source/observation/decision/outcome distinctions inform this bounded laboratory; their production memory infrastructure is not copied into the artwork.

The new [research note](https://docs.google.com/document/d/1yQBxbbBApdPro9tIi26vvMO_K0vnUH0lS1tDZn_JE4w/edit) documents this mapping and the limits of the UCB/Q-learning analogies. The [algorithmic philosophy](battle_evolution-philosophy.md) describes the visual composition. Existing Drive notes were not edited.

Validation receipts distinguish original-model checks, current model/renderer checks, accelerated simulation time, short native Linux GUI runs and the user-run Windows endurance test. No Linux result is presented as a completed eight-hour run on the Kreston Windows machine.
