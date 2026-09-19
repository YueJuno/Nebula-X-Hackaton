# Public-instance solver outputs

These folders contain one independent answer set for each challenge scenario:

- `scenario_A`: fixed nominal supply, no ECLO, delay minimization.
- `scenario_B`: fixed planned completion dates, flexible supply and ECLO.
- `scenario_C`: balanced delay, limited excess supply and ECLO trade-offs.

Each folder contains the required `SCHEDULE_ACCESS.csv`,
`SCHEDULE_OCCUPANCY.csv`, and `RESULTS.csv`, plus an internal `report.json`.

Current public-instance results, solved with week-strict buffers:

| Scenario | Solver status | Access rows | ECLO nights | Excess possessions | Contract overrun days | Objective |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | Optimal | 192 | 0 | 0 | 42 | 131.6 |
| B | Feasible | 187 | 10 | 0 | 0 | 50.0 |
| C | Optimal | 190 | 4 | 0 | 21 | 44.5 |

No Priority-1 contract overruns in any scenario. Scenario A's overrun is 7 days
on one Priority-2 contract plus 35 on Priority-3 contracts.

**All three pass this repository's checker under both modeled readings of section 2.4 rule 3.** The rule
does not say whether two activities in separate possessions may share a night,
and the official scoring program was not shipped to settle it, so these answers
are solved against the stricter week reading, including buffer–buffer separation,
which satisfies the looser per-possession reading as a side effect. Re-check any
folder under either:

```powershell
python -m scheduler ..\01_data --check ..\04_solver_outputs\scenario_A --granularity week
python -m scheduler ..\01_data --check ..\04_solver_outputs\scenario_A --granularity possession
```

The looser reading scored better in earlier solves (A 25.2, B 30.0, C 25.2) but
those schedules produced `closure` violations under the strict reading, so
it trades a mandatory feasibility gate for a quality margin. `SETUP.md` section
8 covers the trade-off, and the web app exposes both models.

Group labels are location-specific: a single access may use different labels
along its occupied route. Scenario B's compact search found a feasible score
of 50.0 but did not prove global optimality over unrestricted extra capacity;
its status is therefore reported as `FEASIBLE`.

The official scoring program was not included with the challenge package, so
the validator above is the repository's own reading of the published rules. A
feasible verdict here is evidence, not proof; run these outputs through the
official validator before submission if it becomes available.

