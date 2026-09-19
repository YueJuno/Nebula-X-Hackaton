# HANDOFF — Nebula-X PS1 session, 2026-09-19

> Integration correction (2026-09-19): The supplied `03_submission_sample/`
> is described in `PS1_README.md` as feasible, but has 11 location-groups whose
> members use different `access_night` indices within one contract/type/week.
> Therefore the night↔group equivalence claimed in section 2 below is not a
> safe hard rule. The integrated solver and built-in validator do **not**
> enforce it. Route-local group labels remain supported. The sample passes
> the built-in `possession` reading; the conservative `week` reading reports
> 49 buffer closures after literal buffer–buffer checks were added. The official validator is still unavailable.

Context transfer for an AI agent picking up this repo cold. Facts and file paths
only. Treat every "OPEN" item as unresolved.

---

## 0. Project

- Path: `C:\Users\ivand\OneDrive\Desktop\Nebula-X-Hackaton`
- Challenge: PS1 "Railway Track Access Optimisation" (spec verbatim in `PS1_README.md`). Dual-line Alpha/Beta network, overnight possession scheduling, scenarios A/B/C.
- Stack: CP-SAT (OR-Tools) in `backend/scheduler/`; FastAPI + SQLAlchemy + Neon Postgres in `backend/app/`; React/Vite in `frontend/`.
- Git remote: GitHub `YueJuno/Nebula-X-Hackaton`. **Deliverable asks for GitLab.**
- Public instance: 54 activities, 14 contracts, 76 locations, 30 weeks, horizon start 2027-01-04, 192 total accesses.

Three workstreams landed today: (1) a built-in validator, (2) a rule-5 solver bug fix, (3) a counterfactual explainability engine. Plus (4) resolution of a spec ambiguity that changed the shipped solver default.

---

## 1. Built-in reference validator (NEW)

The official scoring program was never shipped with the challenge pack. Judging dimension 2 is scored mechanically by it. So the repo now implements PS1 §2.4 hard rules and the §2.7 report itself.

| File | Contents |
|---|---|
| `backend/scheduler/submission.py` | `AccessRow`, `OccupancyRow`, `ResultRow`, `Submission`; `load_submission_files(dict[str,bytes])`, `load_submission_directory(Path)`. Rejects mixed-scenario `RESULTS.csv` + duplicate contract rows. Reuses `loader.read_rows` for exact-header checks. |
| `backend/scheduler/rules.py` | `Violation{rule,severity,detail}`; `Index.build(instance, submission, footprints)`; `check_structure`, `check_workload`, `check_start_dates`, `check_predecessors`, `check_closures`, `check_possessions`, `check_allocation`, `check_eclo`, `check_planned_dates`, `check_results`; helpers `show()`, `week_of()`. |
| `backend/scheduler/scoring.py` | `completion_table`, `capacity_usage`, `priority_weighted_score`, `score_submission`, `objective_score`; `FORMULA_VERSION = "ps1-2.5"`. |
| `backend/scheduler/validator.py` | REWRITTEN. `validate()`, `validate_files()`, `validate_directory()`, `unparseable()`. Kept `validate_submission()` as the external-binary adapter. `MAX_REPORTED_VIOLATIONS = 200`. |

**14 rule tags**: `workload`, `start_date`, `closure`, `mix`, `allocation`, `workfront`, `eclo`, `eclo_window`, `capacity`, `planned_date`, `predecessor`, `occupancy`, `results`, `format`.

**Report shape** = §2.7: `{scenario, feasible, hard_violations[], soft_scores{}, detail{}}`. `soft_scores` gains `objective_score` + `formula_version` only when feasible (per spec). `detail` adds `closure_granularity`, `hard_violations_total`, `violations_by_rule`, `contracts`. On parse failure: `soft_scores == {}`, one `format` violation (per spec).

**Independent cross-check**: validator scores recomputed from CSVs matched the solver's own `report.json` exactly for A/B/C (`overrun_days_total`, `eclo_nights_total`, `excess_access_nights_total`, `priority_weighted_score`, `nights_scheduled`). Two independent implementations agree.

---

## 2. Route-local co-sharing and night indices (INTEGRATED CORRECTION)

`co_share_group` belongs to `(location_id, week)`, not an entire activity route.
The organizer sample uses multiple labels on 169 of 192 accesses. The solver
now assigns each occupied location independently; safety co-share comparisons
use the actual shared location rather than a route anchor.

The earlier proposed `access_night` ↔ `co_share_group` equivalence was removed.
The challenge README describes the supplied sample as feasible, yet the sample
has 11 local groups containing activities of the same contract/type with
different `access_night` indices. Enforcing that equivalence would reject the
organizer's own example. Section 2.6 agrees outright: `access_night` is "a
local accounting index per contract+type+week, independent of location/sector".
Weekly allocation and workfront checks remain in place; the two fields are not
equated without official-validator evidence.

It was removed from the validator first and from the CP model afterwards. The
residual block in `constraints/possessions.py` still reified a `together` bool
over `possession[..., occupied[0]]` for each activity, which compared labels at
two *different* locations once the route anchor was dropped, so it constrained
nothing meaningful while excluding legal solutions. Removing it left A/B/C
objectives unchanged (131.6 / 50.0 / 44.5). Nothing now ties the two fields.

Regression checks now cover route-local labels, location-aware week safety,
the organizer sample under the possession reading, and A/B/C self-validation.

---

## 3. §2.4 rule 3 buffer granularity — AMBIGUITY, resolved by choice not by proof

**The ambiguity.** Rule 3 does not state whether two activities in *separate possessions* can occupy the same night. Two defensible readings:

- **`week`** — any two activities holding an access in the same week conflict when one's occupied span falls inside the other's closure zone **or their closure zones overlap**, unless co-sharing. Supported by the §2.7 example detail string `"wk4: A012 inside closure of ['A010'] at ['SEC:ALP:S02_S03:EB']"` (week-granular, no night named), and by the fact that *neither submitted field orders nights across contracts*: `access_night` is explicitly local to a contract+type, `co_share_group` is "an arbitrary label".
- **`possession`** — only activities sharing a `co_share_group` that week are concurrent, taking rule 5's "separate possessions on separate nights" as a network-wide guarantee.

Co-sharing exempts a pair under either reading.

**Measured cost** (solver + validator, public instance):

| Scenario | possession obj | week obj | possession-model checked under `week` |
|---|---:|---:|---|
| A | 25.2 | 131.6 | Previously 43–67 `closure` violations; recheck with current validator |
| B | 30.0 | 50.0 | (varies per optimal solution) |
| C | 25.2 | 44.5 | |

**Key asymmetry**: a week-strict schedule is feasible under **both** readings. A possession-strict schedule is feasible under only one. Feasibility is a mandatory gate; score is a margin.

**DECISION (user-approved)**: ship week-strict, expose both in the app.

**Implementation**:
- `backend/scheduler/constraints/safety.py` REWRITTEN. New `closure_zone(footprint)` = `buffers ∪ mirrored ∪ cross_line − occupied` (matches `rules.py` exactly). Two branches on `policy.buffer_granularity`.
  - week-strict, disjoint spans → `access[X,w] + access[Y,w] <= 1` (no co-share possible, so the week cannot hold both)
  - week-strict, shared location → at least one actual shared location has the same group when both are booked
- `buffer_granularity` threaded end to end: `Policy` (new field, **default `"week"`**) → `get_policy(scenario, buffer_granularity)` → `build_model`/`prepare`/`solve` → CLI `--granularity` → `RunRequest.buffer_granularity` → `Run.buffer_granularity` column → worker.

**NOTE for anyone re-reading my earlier analysis**: I initially flagged `safety.py`'s `if not occupied.isdisjoint(...): continue` skip as an independent bug. It is NOT. Under the possession reading it is correct (pairs sharing a location are either co-sharing, hence buffer-exempt, or in different possessions, hence different nights). It was the same granularity question wearing a different hat.

---

## 4. Counterfactual explainability (NEW)

`backend/scheduler/explain.py`. Two layers split by cost:

- `explain_delays(instance, schedule)` — reads the solved schedule only, no re-solve. Attached to every API run as `report["explanation"]`.
- `cheapest_unlocks(...)` — one full re-solve per lever. CLI/offline only.

Other symbols: `Lever{kind,target,description,cost_note,magnitude}`, `Usage`, `summarize()`, `candidate_levers()`, `apply_lever()`, `measure()`, `explain()`.

**Blocking factors** (`FACTORS` tuple, order = dominance): `window`, `allocation`, `workfront`, `capacity`, `predecessor`.

**Lever kinds**: `weekly_access`, `workfronts`, `supply`, `start_date`.

**Principal finding under the earlier possession-model baseline:** its 25.2 delay score was structurally unavoidable because an activity may take at most one access-night per week:

| Activity | Nights needed | Window | Short by |
|---|---:|---|---:|
| A036 (C006) | 7 | wk22–26 (5 wks) | 2 |
| A059 (C010) | 7 | wk14–19 (6 wks) | 1 |

No supply, workfront or allocation relief can remove these two window shortfalls. The earlier lever sweep found `start_date A036` → **−18.2**, `start_date A059` → **−7.0** under the possession baseline. The current week-strict A score is 131.6 and contains additional contention delay; do not call its whole objective structurally unavoidable.

This also explains Scenario B's ECLO spend exactly: closing those two windows at the 1.5× ECLO yield needs 4 ECLO nights on A036 (of 5) and 2 on A059 (of 6) = 6 total, which is what B used under the possession model. Verified against B's `SCHEDULE_ACCESS.csv`, not inferred.

---

## 5. CLI (`backend/scheduler/__main__.py`)

```
python -m scheduler <instance_dir> [--scenario A|B|C] [--time-limit N]
    [--submission-dir DIR] [--output FILE]
    [--check SUBMISSION_DIR] [--granularity week|possession]
    [--explain] [--unlocks N]
```

- `--check` validates without solving. **Needs no OR-Tools** (solver imports are lazy). Exit `0` feasible, `2` infeasible. Prints the §2.7 report plus a one-line verdict, e.g. `INFEASIBLE (week granularity): closure=49`.
- `--granularity` (default `week`) applies to **solving and checking**.
- Solve path now always self-validates into `report["validation"]`.

---

## 6. API / worker changes

- `app/services/scheduling.py`: `execute_run(payload, files, scenario, validator_command=None, time_limit_seconds=60, granularity="week")`. Always runs the built-in validator. External validator is now an optional cross-check into `report["external_validation"]`. Status is `completed` iff built-in feasible AND external not contradicting; otherwise `needs_validation` (CSVs stay downloadable either way).
- `app/schemas/scheduling.py`: `RunRequest.buffer_granularity: Literal["week","possession"] = "week"`; `RunResponse.buffer_granularity`.
- `app/models/scheduling.py`: `Run.buffer_granularity` `String(16)` default `"week"`.
- `app/api/routes/runs.py`, `app/workers/scheduling.py`: pass-through.

### ⚠ DB MIGRATION REQUIRED

`python -m app.db.init_db` only creates *missing tables*. An existing database needs:

```sql
ALTER TABLE scheduling_runs ADD COLUMN buffer_granularity VARCHAR(16) DEFAULT 'week';
```

---

## 7. Frontend

New: `src/components/ValidationReport.tsx` (verdict badge, per-rule counts, pinpoints), `src/components/DelayExplanations.tsx` (why-late table, expandable per activity).

Modified: `src/App.tsx` (buffer-reading toggle section, `granularity` state, default `"week"`); `src/api/scheduling.ts` (`createRun(datasetId, scenario, bufferGranularity)`); `src/types/scheduling.ts` (new `SoftScores`, `Validation`, `DelayExplanation`, `Explanation`; `Run.buffer_granularity`); `src/components/PlannerPanel.tsx` (takes `granularity` prop, renders both new panels); `src/styles/globals.css`.

`npx tsc --noEmit` clean.

---

## 8. Tests — 66 pass

New: `backend/tests/test_validator.py`, `backend/tests/test_explain.py`, and `backend/tests/test_hidden_variations.py`. The hidden-variation tests use a tiny two-line CSV instance with a midweek start and exercise A/B/C plus zero nominal supply in B/C. New in `test_scheduler.py`: `test_solver_output_passes_its_own_validator` (A/B/C), `test_week_strict_buffers_satisfy_both_readings` (A/B/C). New buffer–buffer regression cases in `test_constraints.py` and `test_validator.py` cover disjoint work sites with a shared closure location.

**Existing tests I changed because behaviour changed** (verify these were right calls):
1. `test_scheduler.py::test_run_solves_but_requires_reference_validation` → renamed `test_run_solves_and_self_validates`. Old assertion `validation["status"] == "unavailable"` encoded "no verdict without an external validator", which is exactly what this work removes.
2. `test_scheduling_api.py::test_upload_prepare_persist_and_owner_isolation` — asserted `status == "needs_validation"`; runs now reach `completed`.
3. `test_explain.py` ×2 — pinned possession-model numbers (`objective_after == 7.0`, exact overrun set `{A036, A059}`). Relaxed to invariants holding under either reading.
4. `test_explain.py::test_levers_are_proposed_only_where_evidence_exists` — asserts both structural remedies are proposed and every lever has evidence, without requiring an order that varies between equally optimal schedules.

**Bounded scale probes (diagnostic, not proof for unknown judge data):** A 40-activity toy instance took 0.13 seconds to construct and solve, then passed validation. The public instance plus 20 one-access jobs (74 activities) validated under A/B/C after about 20/21/38 seconds of model construction and search with the default 60-second search limit; a 10-second A attempt returned `UNKNOWN`. With 46 such jobs added (100 activities), A/B/C validated after about 34/42/64 seconds of model construction and search, respectively. The 100-activity C run returned `FEASIBLE`, not `OPTIMAL`; model construction can make elapsed time exceed the 60-second search limit. Larger or differently structured hidden instances remain unproven.

---

## 9. Regenerated deliverables

`04_solver_outputs/scenario_{A,B,C}/{SCHEDULE_ACCESS,SCHEDULE_OCCUPANCY,RESULTS}.csv` + `report.json` + `README.md`. **Now week-strict.**

| Scenario | Status | Access rows | Objective | Overrun | ECLO | Excess | P1/P2/P3 overrun days |
|---|---|---:|---:|---:|---:|---:|---|
| A | OPTIMAL | 192 | 131.6 | 42 | 0 | 0 | 0 / 7 / 35 |
| B | FEASIBLE | 187 | 50.0 | 0 | 10 | 0 | 0 / 0 / 0 |
| C | OPTIMAL | 190 | 44.5 | 21 | 4 | 0 | 0 / 0 / 21 |

All six checks pass: every scenario feasible under **both** `week` and `possession` in the built-in validator. No Priority-1 overrun anywhere.

---

## 10. OPEN — not started

Ranked by my assessment of value:

1. **Hosting** (deliverable 2). `compose.yaml` is dev-only: `Dockerfile.dev`, ports bound to `127.0.0.1`, source volume mounts. SETUP.md says "not production deployment". Zero points without it. Needs accounts, not code.
2. **2AM re-plan / urgent-maintenance re-optimisation** (bonus scope 1). Best demo value per hour. Sketch: churn penalty against a baseline assignment + `model.add_hint()` warm start in `objectives.py`, supply-override on the run request, diff view. Video brief explicitly says "user experience for a 2AM works controller".
3. **3-min video** (deliverable 3). Nothing exists.
4. **GitLab repo** (deliverable 4). Currently GitHub.
5. **Pareto / scenario comparison screen.** Data exists, nothing renders it.
6. **Displaced-work view** (rubric dim 1 asks what got displaced, not just what's late).
7. NL querying (bonus 2) — recommend routing through `explain.py` so answers are computed, not generated.
8. `ScheduleTimeline.tsx` still an 18-line bullet table; `NetworkPreview.tsx` draws stations only (no bounds/sectors/buffers).
9. Manual override; per-CSV download.
10. `expand` subcommand (§2.6 references `python3 -m trackaccess expand` for generating `co_share_group`).
11. `app/core/rate_limit.py` is a one-line placeholder; `REDIS_URL` is in `.env` but `Settings` has no `redis_url` field (`extra="ignore"` drops it). No rate limiting on any endpoint.
12. `cheapest_unlocks` has no warm start — every lever is a cold solve.
13. Lever sweep has no API/UI surface (deliberate: one solve per lever).

---

## 11. Assumptions an agent must NOT silently inherit

- **Buffer granularity is unresolved.** `week` was chosen for safety, not correctness. If the official validator surfaces, re-measure; possession scores 25.2/30.0/25.2 vs 131.6/50.0/44.5.
- **The validator is this repo's own reading of the published rules.** A feasible verdict is evidence, not proof.
- `check_predecessors` is not in §2.4's enumerated rule list. Enforced because the instance data models `predecessor_activity_id`.
- Interchange cross-line rule (pre-existing, unverified): a `Live` closure reaching either hub *or its connecting sector* triggers the cross-line closure. See `topology.py::calculate_footprint`.
- `check_start_dates` and the solver both allow the week *containing* `planned_start_date`, as rule 2 specifies. A midweek start date no longer blocks that entire week.
- `LOCATION_SUPPLY` has no week column — supply is flat per location. Confirmed against the CSV.

---

## 12. Environment / hygiene

- Packages were installed into **system Python**, not a venv: `ortools`, `pytest`, `httpx`, `sqlalchemy`, `psycopg[binary]`, `python-jose`, `pyjwt`, `passlib[bcrypt]`, `pydantic-settings`, `email-validator`, `python-multipart`, `watchfiles`. Move to `backend/.venv`.
- **Rotate the Neon database password** — it was pasted into a chat transcript.
- `SOLVER_TIME_LIMIT_SECONDS` and `VALIDATOR_COMMAND` unset; solver defaults to 60s, which may be tight for a hidden instance larger than the public one.
- Watch for `\0` octal escaping when writing Windows paths like `..\01_data` through Python heredocs — it silently produces control bytes. Bitten twice; both repaired.

---

## 13. Files touched

**New (8)**: `backend/scheduler/{submission,rules,scoring,explain}.py`, `backend/tests/test_{validator,explain}.py`, `frontend/src/components/{ValidationReport,DelayExplanations}.tsx`

**Modified (24)**: `backend/scheduler/{validator,solver,policies,__main__}.py`, `backend/scheduler/constraints/{safety,possessions}.py`, `backend/app/services/scheduling.py`, `backend/app/{schemas,models}/scheduling.py`, `backend/app/api/routes/runs.py`, `backend/app/workers/scheduling.py`, `backend/tests/test_{scheduler,scheduling_api}.py`, `frontend/src/App.tsx`, `frontend/src/api/scheduling.ts`, `frontend/src/types/scheduling.ts`, `frontend/src/components/PlannerPanel.tsx`, `frontend/src/styles/globals.css`, `SETUP.md` (new §8 validating, §9 explaining), `04_solver_outputs/README.md`, `04_solver_outputs/scenario_{A,B,C}/*`

Nothing is committed. `git status` is dirty by design.
