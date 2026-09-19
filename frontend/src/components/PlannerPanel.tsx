import { useEffect, useRef, useState, type FormEvent } from "react";
import { createRun, downloadRunFile, getCapabilities, getDataset, getRun, listDatasets, listRuns, uploadDataset } from "../api/scheduling";
import type { User } from "../types/auth";
import type { Capabilities, Dataset, Instance, Run } from "../types/scheduling";
import NetworkPreview from "./NetworkPreview";
import ScheduleTimeline from "./ScheduleTimeline";
import Icon from "./Icon";
import ValidationReport from "./ValidationReport";
import DelayExplanations from "./DelayExplanations";

export default function PlannerPanel({ user, scenario, granularity, onPendingChange }: {
  user: User | null; scenario: string; granularity: string; onPendingChange: (pending: boolean) => void;
}) {
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState("");
  const [instance, setInstance] = useState<Instance | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState("My rail plan");
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [activityId, setActivityId] = useState("");
  const [operation, setOperation] = useState<"upload" | "generate" | "download" | "refresh" | null>("refresh");
  const busy = operation !== null;
  const inFlight = useRef(true);
  const [downloadNotice, setDownloadNotice] = useState("");
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => { onPendingChange(busy); }, [busy, onPendingChange]);
  useEffect(() => { setDownloadNotice(""); }, [activeRun?.id]);

  function begin(action: NonNullable<typeof operation>) {
    if (inFlight.current) return false;
    inFlight.current = true; setOperation(action); setError(""); setDownloadNotice("");
    return true;
  }
  function finish() { inFlight.current = false; setOperation(null); }

  async function refreshPlans() {
    if (!begin("refresh")) return;
    try {
      const [data, history] = await Promise.all([listDatasets(), listRuns()]);
      setDatasets(data); setRuns(history);
      setSelected(current => data.some(item => item.id === current) ? current : data[0]?.id || "");
      setActiveRun(current => current ? history.find(item => item.id === current.id) || current : null);
      setRefresh(value => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not refresh plans."); }
    finally { finish(); }
  }

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
    }).catch(cause => { if (active) setError(String(cause.message)); }).finally(() => { if (active) finish(); });
    else finish();
    return () => { active = false; };
  }, [user?.id]);

  useEffect(() => {
    let active = true;
    setInstance(null); setActivityId("");
    if (selected && user) getDataset(selected).then(data => {
      if (active) { setInstance(data.instance); setActivityId(data.instance.activities[0]?.activity_id || ""); }
    }).catch(cause => { if (active) setError(String(cause.message)); });
    return () => { active = false; };
  }, [selected, user?.id]);

  useEffect(() => {
    setPollError("");
    if (!activeRun || !["queued", "running"].includes(activeRun.status) || !user) return;
    let cancelled = false;
    let timer: number;
    const poll = () => {
      getRun(activeRun.id).then(run => {
        if (!cancelled) {
          setActiveRun(run);
          setRuns(previous => [run, ...previous.filter(item => item.id !== run.id)]);
        }
      }).catch(cause => {
        if (!cancelled) {
          setPollError(`${String(cause.message)} Retrying the schedule status…`);
          timer = window.setTimeout(poll, 5000);
        }
      });
    };
    timer = window.setTimeout(poll, 2000);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [activeRun, user?.id]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!begin("upload")) return;
    try {
      const dataset = await uploadDataset(name, files);
      setDatasets(previous => [dataset, ...previous]); setSelected(dataset.id); setActiveRun(null); setFiles([]);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Upload failed."); }
    finally { finish(); }
  }

  async function start() {
    if (!selected || !begin("generate")) return;
    try {
      const run = await createRun(selected, scenario, granularity);
      setActiveRun(run); setRuns(previous => [run, ...previous]);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not start run."); }
    finally { finish(); }
  }

  async function downloadSubmission() {
    if (!activeRun || !begin("download")) return;
    try { await downloadRunFile(activeRun, "submission"); setDownloadNotice("Download started. Check your browser downloads for the submission ZIP."); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Download failed."); }
    finally { finish(); }
  }

  const dataset = datasets.find(item => item.id === selected);
  const footprint = activeRun?.dataset_id === selected ? activeRun.report?.footprints[activityId] : undefined;

  return <section className="panel planner-panel" aria-labelledby="planner-heading">
    <div className="panel-heading"><div><p className="section-kicker">CREATE A SCHEDULE</p><h2 id="planner-heading">Upload, generate and download</h2></div>
      {user && <button onClick={refreshPlans} disabled={busy}>{operation === "refresh" ? "Refreshing…" : "Refresh"}</button>}</div>
    <ol className="workflow-steps" aria-label="Scheduling workflow"><li><span>1</span><strong>Upload</strong><small>Eight input CSVs</small></li><li><span>2</span><strong>Generate</strong><small>Choose your approach</small></li><li><span>3</span><strong>Download</strong><small>Submission ZIP</small></li></ol>
    {user && capabilities && !capabilities.can_schedule && <p className="notice" role="status">
      You can upload and explore your network. Schedule generation is not available yet.
    </p>}
    {!user ? <div className="upload-welcome"><span className="upload-icon"><Icon name="upload" size={25} /></span><h3>Start with your input files</h3><p>Sign in, upload the eight challenge CSV files, and OptiTrack will guide you to the submission download.</p><button className="primary-button" onClick={() => window.dispatchEvent(new Event("auth:open"))}>Sign in to begin<Icon name="arrow" size={17} /></button><span className="upload-hint">Upload · Generate · Review · Download</span></div> : <>
      <form className="upload-form" onSubmit={upload}>
        <div className="workflow-heading"><span>1</span><div><h3>Upload input files</h3><p>Choose all eight challenge CSV files at the same time.</p></div></div>
        <label>Plan name<input value={name} maxLength={128} required disabled={busy} onChange={event => setName(event.target.value)} /></label>
        <label className="file-upload-zone"><span><Icon name="upload" /> Select all 8 challenge input files</span><input key={`${user.id}:${datasets.length}`} type="file" accept=".csv" multiple required disabled={busy}
          onChange={event => setFiles(Array.from(event.target.files || []))} /></label>
        <p className={`file-count ${files.length === 8 ? "complete" : ""}`}><strong>{files.length} of 8 files selected</strong>{files.length > 0 && <> · {files.map(file => file.name).join(", ")}</>}</p>
        <details><summary>Required filenames</summary><ul>{capabilities?.required_files.map(file => <li key={file}>{file}</li>)}</ul></details>
        <button className="primary-button" type="submit" disabled={busy || files.length !== 8}>{operation === "upload" ? "Checking files…" : "Upload and check files"}<Icon name="arrow" size={17} /></button>
      </form>
      {datasets.length > 0 && <div className="dataset-picker">
        <div className="workflow-heading"><span>2</span><div><h3>Generate a schedule</h3><p>Choose an uploaded plan, then generate the selected scenario.</p></div></div>
        <label>Uploaded plan<select value={selected} disabled={busy} onChange={event => { setSelected(event.target.value); setActiveRun(null); }}>
          {datasets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>
        {dataset && <div className="metrics">
          <span><strong>{dataset.summary.contracts}</strong> contracts</span><span><strong>{dataset.summary.activities}</strong> activities</span>
          <span><strong>{dataset.summary.total_accesses}</strong> required accesses</span><span><strong>{dataset.summary.horizon_weeks}</strong> weeks</span>
        </div>}
        <button className="primary-button" disabled={busy || !selected || activeRun?.status === "queued" || activeRun?.status === "running"} onClick={start}>
          {operation === "generate" ? "Starting schedule…" : activeRun?.status === "queued" ? "Schedule queued…" : activeRun?.status === "running" ? "Generating schedule…" : capabilities?.can_schedule ? `Generate scenario ${scenario}` : `Prepare scenario ${scenario}`}<Icon name="arrow" size={17} />
        </button>
      </div>}
      {activeRun && <div className="run-result" aria-live="polite">
        <h3>Scenario {activeRun.scenario}: {activeRun.status.replace(/_/g, " ")}</h3>
        <p>{activeRun.message || "Waiting for a scheduling worker. Start the worker if this remains queued."}</p>
        {["completed", "needs_validation"].includes(activeRun.status) && <div className={`download-card ${activeRun.status === "needs_validation" ? "review-required" : ""}`}>
          <span className="download-icon"><Icon name="download" size={25} /></span><div><span className="step-label">STEP 3 · {activeRun.status === "needs_validation" ? "REVIEW REQUIRED" : "SUBMISSION READY"}</span><h3>Download your submission</h3><p>One ZIP containing <code>SCHEDULE_ACCESS.csv</code>, <code>SCHEDULE_OCCUPANCY.csv</code> and <code>RESULTS.csv</code>.</p>{activeRun.status === "needs_validation" && <p>Review the validation findings below before submitting.</p>}</div>
          <button className="primary-button download-button" disabled={busy} onClick={downloadSubmission}><Icon name="download" size={18} />{operation === "download" ? "Preparing ZIP…" : "Download submission ZIP"}</button>
        </div>}
        {downloadNotice && <p className="download-notice" role="status">{downloadNotice}</p>}
        {activeRun.report && <>
          <p className="note">{activeRun.report.notice}</p>
          {activeRun.report.solution && <div className="metrics" aria-label="Schedule summary">
            <span><strong>{activeRun.report.solution.objective_score}</strong> objective</span>
            <span><strong>{activeRun.report.solution.nights_scheduled}</strong> access rows</span>
            <span><strong>{activeRun.report.solution.overrun_days_total}</strong> overrun days</span>
            <span><strong>{activeRun.report.solution.excess_access_nights_total}</strong> extra possessions</span>
            <span><strong>{activeRun.report.solution.eclo_nights_total}</strong> ECLO nights</span>
          </div>}
          <details><summary>Model statistics</summary><pre>{activeRun.report.model_stats}</pre></details>
          {activeRun.report.validation && <ValidationReport validation={activeRun.report.validation} />}
          {activeRun.report.explanation && <DelayExplanations explanation={activeRun.report.explanation} />}
          {activeRun.report.external_validation && <ValidationReport validation={activeRun.report.external_validation} />}
        </>}
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
      {runs.length > 0 && <><h3>Previous schedules</h3><p className="note">Select a completed schedule to review it or download its submission ZIP again.</p><div className="run-history">{runs.map(run => <button key={run.id} disabled={busy} aria-pressed={activeRun?.id === run.id} onClick={() => { setSelected(run.dataset_id); setActiveRun(run); setError(""); }}>
        Scenario {run.scenario} · {run.status.replace(/_/g, " ")} · {new Date(run.created_at).toLocaleString()}
      </button>)}</div></>}
    </>}
    {error && <p className="error multiline" role="alert">{error}</p>}
    {pollError && <p className="error multiline" role="status">{pollError}</p>}
  </section>;
}
