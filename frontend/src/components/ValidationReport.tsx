import { useState } from "react";
import type { Validation } from "../types/scheduling";

const RULE_LABELS: Record<string, string> = {
  workload: "Workload conservation (rule 1)",
  start_date: "Planned start week (rule 2)",
  closure: "Closures and buffers (rule 3)",
  mix: "Legal possession mixes (rule 4)",
  co_share: "Co-sharing exemption (rule 5)",
  allocation: "Weekly allocation (rule 6)",
  workfront: "Workfronts (rule 7)",
  eclo: "ECLO prohibition (rule 8)",
  eclo_window: "ECLO continuity window (rule 9)",
  capacity: "Location supply",
  planned_date: "Fixed planned dates",
  predecessor: "Predecessor ordering",
  occupancy: "Occupancy coverage",
  results: "RESULTS.csv agreement",
  format: "File format",
};

function Score({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null) return null;
  return <span><strong>{String(value)}</strong> {label}</span>;
}

export default function ValidationReport({ validation }: { validation: Validation }) {
  const [expanded, setExpanded] = useState(false);
  const { feasible, soft_scores: scores = {}, detail = {} } = validation;
  const counts = Object.entries(detail.violations_by_rule || {});
  const violations = validation.hard_violations || [];
  const shown = expanded ? violations : violations.slice(0, 8);

  if (validation.status !== "validated") {
    return <div className="validation">
      <h4>Feasibility check</h4>
      <p className="note">Validator unavailable: {validation.status}.</p>
    </div>;
  }

  return <div className="validation">
    <div className="panel-heading">
      <h4>Feasibility check{validation.validator === "external" ? " (external)" : ""}</h4>
      <span className={`badge ${feasible ? "connected" : "unavailable"}`} role="status">
        {feasible ? "0 hard violations" : `${detail.hard_violations_total ?? violations.length} hard violations`}
      </span>
    </div>

    <div className="metrics" aria-label="Soft scores">
      {feasible && <Score label="objective score" value={scores.objective_score} />}
      <Score label="overrun days" value={scores.overrun_days_total} />
      <Score label="contracts overrunning" value={scores.contracts_overrunning} />
      <Score label="excess access-nights" value={scores.excess_access_nights_total} />
      <Score label="ECLO nights" value={scores.eclo_nights_total} />
      <Score label="priority-weighted" value={scores.priority_weighted_score} />
    </div>

    {scores.priority_overrun && <p className="note">
      Overrun days by contract tier — P1: {scores.priority_overrun["1"]},
      P2: {scores.priority_overrun["2"]}, P3: {scores.priority_overrun["3"]}.
      {detail.closure_granularity && ` Buffers checked at ${detail.closure_granularity} granularity.`}
    </p>}

    {counts.length > 0 && <>
      <table className="violation-summary">
        <thead><tr><th>Rule</th><th>Breaches</th></tr></thead>
        <tbody>{counts.map(([rule, count]) => <tr key={rule}>
          <td>{RULE_LABELS[rule] || rule} <code>{rule}</code></td><td>{count}</td>
        </tr>)}</tbody>
      </table>
      <ul className="violation-list">
        {shown.map((violation, index) => <li key={index}>
          <code>{violation.rule}</code> {violation.detail}
        </li>)}
      </ul>
      {violations.length > 8 && <button onClick={() => setExpanded(value => !value)}>
        {expanded ? "Show fewer" : `Show all ${violations.length} pinpoints`}
      </button>}
    </>}
  </div>;
}
