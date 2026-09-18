import { useState } from "react";
import type { Explanation } from "../types/scheduling";

const FACTOR_LABELS: Record<string, string> = {
  window: "Window too short",
  allocation: "Weekly access-nights spent",
  workfront: "No free workfront",
  capacity: "Locations at supply",
  predecessor: "Waiting on predecessor",
};

export default function DelayExplanations({ explanation }: { explanation: Explanation }) {
  const [open, setOpen] = useState<string | null>(null);
  const rows = explanation.explanations;

  if (!rows.length) {
    return <div className="validation">
      <h4>Why work slipped</h4>
      <p className="note">No activity overruns its planned completion date in this schedule.</p>
    </div>;
  }

  return <div className="validation">
    <div className="panel-heading">
      <h4>Why work slipped</h4>
      <span className="badge" role="status">
        {rows.length} {rows.length === 1 ? "activity" : "activities"} · {explanation.objective_score} objective
      </span>
    </div>
    <p className="note">
      Ranked by delay cost — contract tier sets the band, the activity's own priority nudges it within that band.
    </p>
    <table className="violation-summary">
      <thead><tr>
        <th>Activity</th><th>Contract</th><th>Overrun</th><th>Cost</th><th>Main reason</th>
      </tr></thead>
      <tbody>{rows.map(row => <tr key={row.activity_id}>
        <td>
          <button className="linklike" onClick={() => setOpen(open === row.activity_id ? null : row.activity_id)}
            aria-expanded={open === row.activity_id}>
            {row.activity_id}
          </button>
        </td>
        <td>{row.contract_number} <small>P{row.contract_priority}</small></td>
        <td>{row.overrun_days} d</td>
        <td>{row.weighted_cost}</td>
        <td>{FACTOR_LABELS[row.primary_factor] || row.primary_factor}</td>
      </tr>)}</tbody>
    </table>

    {rows.filter(row => row.activity_id === open).map(row => <div key={row.activity_id} className="explanation-detail">
      <p>{row.summary}</p>
      <div className="metrics">
        <span><strong>{row.nights_required}</strong> nights needed</span>
        <span><strong>{row.window_weeks}</strong> week window</span>
        <span><strong>wk {row.earliest_week}–{row.deadline_week}</strong> allowed</span>
        <span><strong>wk {row.completion_week}</strong> actual finish</span>
      </div>
      {row.window_shortfall > 0 && <p className="note">
        Structural shortfall of {row.window_shortfall} week{row.window_shortfall === 1 ? "" : "s"}.
        {row.shortfall_with_eclo === 0
          ? " ECLO nights would close it where the scenario allows them."
          : ` Even with ECLO it stays ${row.shortfall_with_eclo} week(s) short.`}
      </p>}
      {row.missed_weeks.length > 0 && <p className="note">
        Weeks inside its window with no access: {row.missed_weeks.join(", ")}.
      </p>}
      <ul className="violation-list">
        {Object.entries(row.blocking_factors).filter(([, count]) => count > 0).map(([factor, count]) =>
          <li key={factor}><code>{factor}</code> {FACTOR_LABELS[factor] || factor} — {count}</li>)}
        {row.hotspots.map(hotspot => <li key={hotspot.location_id}>
          <code>at supply</code> {hotspot.location_id} in weeks {hotspot.weeks.join(", ")}
        </li>)}
      </ul>
    </div>)}
  </div>;
}
