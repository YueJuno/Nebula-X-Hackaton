import { useEffect, useState, type FormEvent } from "react";
import { createRun, downloadRunFile, getCapabilities, getDataset, getRun, listDatasets, listRuns, uploadDataset } from "../api/scheduling";
import type { User } from "../types/auth";
import type { Capabilities, Dataset, Instance, Run } from "../types/scheduling";
import NetworkPreview from "./NetworkPreview";
import ScheduleTimeline from "./ScheduleTimeline";
import ValidationReport from "./ValidationReport";
import DelayExplanations from "./DelayExplanations";

export default function PlannerPanel({ user, scenario, granularity }: { user: User | null; scenario: string; granularity: string }) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState("");
  const [instance, setInstance] = useState<Instance | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("Planning instance");
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [activityId, setActivityId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    getCapabilities().then(value => { if (active) setCapabilities(value); }).catch(() => {});
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let active = true;
    setDatasets([]); setRuns([]); setSelected(""); setInstance(null); setActiveRun(null); setFiles([]); setError("");
    if (user) Promise.all([listDatasets(), listRuns()]).then(([data, history]) => {
      if (active) { setDatasets(data); setRuns(history); setSelected(data[0]?.id || ""); }
    }).catch(cause => { if (active) setError(String(cause.message)); });
    return () => { active = false; };
  }, [user?.id, refresh]);

  useEffect(() => {
    let active = true;
    setInstance(null); setActivityId("");
    if (selected && user) getDataset(selected).then(data => {
      if (active) { setInstance(data.instance); setActivityId(data.instance.activities[0]?.activity_id || ""); }
    }).catch(cause => { if (active) setError(String(cause.message)); });
    return () => { active = false; };
  }, [selected, user?.id]);

  useEffect(() => {
    if (!activeRun || !["queued", "running"].includes(activeRun.status) || !user) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      getRun(activeRun.id).then(run => {
        if (!cancelled) {
          setActiveRun(run);
          setRuns(previous => [run, ...previous.filter(item => item.id !== run.id)]);
        }
      }).catch(cause => { if (!cancelled) setError(String(cause.message)); });
    }, 2000);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activeRun, user?.id]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const dataset = await uploadDataset(name, files);
      setDatasets(previous => [dataset, ...previous]); setSelected(dataset.id); setActiveRun(null); setFiles([]);
      event.currentTarget?.reset();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Upload failed."); }
    finally { setBusy(false); }
  }

  async function start() {
    setBusy(true); setError("");
    try {
      const run = await createRun(selected, scenario, granularity);
      setActiveRun(run); setRuns(previous => [run, ...previous]);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not start run."); }
    finally { setBusy(false); }
  }

  async function download(kind: "report" | "submission") {
    if (!activeRun) return;
    try { await downloadRunFile(activeRun, kind); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Download failed."); }
  }

  const dataset = datasets.find(item => item.id === selected);
  const footprint = activeRun?.dataset_id === selected ? activeRun.report?.footprints[activityId] : undefined;

  return <section className="panel" aria-labelledby="planner-heading">
    <div className="panel-heading"><h2 id="planner-heading">Planning workspace</h2>
      <button onClick={() => setRefresh(value => value + 1)} disabled={busy}>Refresh</button></div>
    {capabilities && !capabilities.can_schedule && <p className="notice" role="status">
      Data upload and model preparation are available. Scheduling awaits the railway constraints: {capabilities.missing_constraints.join(", ")}.
    </p>}
    {!user ? <p>Sign in to upload datasets and save scheduling runs.</p> : <>
      <form className="upload-form" onSubmit={upload}>
        <label>Dataset name<input value={name} maxLength={128} required disabled={busy} onChange={event => setName(event.target.value)} /></label>
        <label>Eight instance CSVs<input key={`${user.id}:${datasets.length}`} type="file" accept=".csv" multiple required disabled={busy}
          onChange={event => setFiles(Array.from(event.target.files || []))} /></label>
        {files.length > 0 && <p>{files.length} files selected: {files.map(file => file.name).join(", ")}</p>}
        <details><summary>Required filenames</summary><ul>{capabilities?.required_files.map(file => <li key={file}>{file}</li>)}</ul></details>
        <button type="submit" disabled={busy || files.length !== 8}>{busy ? "Please wait…" : "Validate and upload"}</button>
      </form>
      {datasets.length > 0 && <div className="dataset-picker">
        <label>Saved dataset<select value={selected} disabled={busy} onChange={event => { setSelected(event.target.value); setActiveRun(null); }}>
          {datasets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>
        {dataset && <div className="metrics">
          <span><strong>{dataset.summary.contracts}</strong> contracts</span><span><strong>{dataset.summary.activities}</strong> activities</span>
          <span><strong>{dataset.summary.total_accesses}</strong> required accesses</span><span><strong>{dataset.summary.horizon_weeks}</strong> weeks</span>
        </div>}
        <button disabled={busy || !selected || activeRun?.status === "queued" || activeRun?.status === "running"} onClick={start}>
          {capabilities?.can_schedule ? `Schedule scenario ${scenario}` : `Prepare scenario ${scenario}`}
        </button>
      </div>}
      {activeRun && <div className="run-result" aria-live="polite">
        <h3>Scenario {activeRun.scenario}: {activeRun.status.replace(/_/g, " ")}</h3>
        <p>{activeRun.message || "Waiting for a scheduling worker. Start the worker if this remains queued."}</p>
        {activeRun.report && <>
          <p className="note">{activeRun.report.notice}</p>
          {activeRun.report.solution && <div className="metrics" aria-label="Schedule summary">
            <span><strong>{activeRun.report.solution.objective_score}</strong> objective</span>
            <span><strong>{activeRun.report.solution.nights_scheduled}</strong> access rows</span>
            <span><strong>{activeRun.report.solution.overrun_days_total}</strong> overrun days</span>
            <span><strong>{activeRun.report.solution.excess_access_nights_total}</strong> extra possessions</span>
            <span><strong>{activeRun.report.solution.eclo_nights_total}</strong> ECLO nights</span>
          </div>}
          <button onClick={() => download("report")}>Download solve / validation report</button>
          <details><summary>Model statistics</summary><pre>{activeRun.report.model_stats}</pre></details>
          {activeRun.report.validation && <ValidationReport validation={activeRun.report.validation} />}
          {activeRun.report.explanation && <DelayExplanations explanation={activeRun.report.explanation} />}
          {activeRun.report.external_validation && <ValidationReport validation={activeRun.report.external_validation} />}
        </>}
        {["completed", "needs_validation"].includes(activeRun.status) &&
          <button onClick={() => download("submission")}>Download submission CSVs</button>}
        {activeRun.schedule && instance && activeRun.dataset_id === selected && <ScheduleTimeline instance={instance} schedule={activeRun.schedule} />}
      </div>}
      {instance && <>
        <h3>Network and activity demand</h3>
        <label>Inspect activity<select value={activityId} onChange={event => setActivityId(event.target.value)}>
          {instance.activities.map(activity => <option key={activity.activity_id} value={activity.activity_id}>{activity.activity_id} — {activity.contract_number}</option>)}
        </select></label>
        <NetworkPreview instance={instance} footprint={footprint} />
        {footprint && <div className="footprints">{(["occupied", "buffers", "mirrored", "cross_line"] as const).map(key => <details key={key}>
          <summary>{key.replace(/_/g, " ")}: {footprint[key].length} locations</summary><ul>{footprint[key].map(location => <li key={location}><code>{location}</code></li>)}</ul>
        </details>)}</div>}
        <details><summary>Activity demand table</summary><div className="table-scroll"><table>
          <thead><tr><th>Activity</th><th>Contract</th><th>Route</th><th>Accesses</th><th>Earliest start</th></tr></thead>
          <tbody>{instance.activities.map(activity => <tr key={activity.activity_id}><td>{activity.activity_id}</td><td>{activity.contract_number}</td>
            <td>{activity.start_location_id} → {activity.end_location_id}</td><td>{activity.total_accesses}</td><td>{activity.planned_start_date}</td></tr>)}</tbody>
        </table></div></details>
        <details><summary>Nominal location supply</summary><div className="table-scroll"><table>
          <thead><tr><th>Location</th><th>Available possessions per week</th></tr></thead>
          <tbody>{instance.locations.map(location => <tr key={location.location_id}><td>{location.location_id}</td><td>{location.supply_capacity}</td></tr>)}</tbody>
        </table></div></details>
      </>}
      {runs.length > 0 && <><h3>Run history</h3><div className="run-history">{runs.map(run => <button key={run.id} onClick={() => { setSelected(run.dataset_id); setActiveRun(run); }}>
        Scenario {run.scenario} · {run.status.replace(/_/g, " ")} · {new Date(run.created_at).toLocaleString()}
      </button>)}</div></>}
    </>}
    {error && <p className="error multiline" role="alert">{error}</p>}
  </section>;
}
