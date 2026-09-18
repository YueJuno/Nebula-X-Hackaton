# Public-instance solver outputs

These folders contain one independent answer set for each challenge scenario:

- `scenario_A`: fixed nominal supply, no ECLO, delay minimization.
- `scenario_B`: fixed planned completion dates, flexible supply and ECLO.
- `scenario_C`: balanced delay, limited excess supply and ECLO trade-offs.

Each folder contains the required `SCHEDULE_ACCESS.csv`,
`SCHEDULE_OCCUPANCY.csv`, and `RESULTS.csv`, plus an internal `report.json`.

Current public-instance results:

| Scenario | Solver status | Access rows | ECLO nights | Excess possessions | Contract overrun days | Objective |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| A | Optimal | 192 | 0 | 0 | 21 | 25.2 |
| B | Optimal | 189 | 6 | 0 | 0 | 30.0 |
| C | Optimal | 192 | 0 | 0 | 21 | 25.2 |

The reference validator was not included with the challenge package. These
outputs have passed the repository's solver and independent invariant tests,
but should still be run through the official validator before submission.

