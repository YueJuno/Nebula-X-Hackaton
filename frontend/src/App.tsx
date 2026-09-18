import { useEffect, useState } from "react";
import { API_BASE_URL, getHealth } from "./api/client";
import AuthPanel from "./components/AuthPanel";
import PlannerPanel from "./components/PlannerPanel";
import type { User } from "./types/auth";

type Connection = "checking" | "connected" | "unavailable";

const scenarios = [
  { id: "A", title: "Fixed supply", detail: "Minimize delays within existing track capacity. No ECLO." },
  { id: "B", title: "Fixed deadlines", detail: "Meet planned dates using extra access and ECLO when needed." },
  { id: "C", title: "Balanced planning", detail: "Balance delays, limited extra access, and ECLO." },
] as const;

export default function App() {
  const [connection, setConnection] = useState<Connection>("checking");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [scenario, setScenario] = useState<string>("A");
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timeout = window.setTimeout(() => controller.abort(), 5000);
    setConnection("checking");
    setError("");
    getHealth(controller.signal)
      .then(() => { if (active) setConnection("connected"); })
      .catch((cause: unknown) => {
        if (!active) return;
        setConnection("unavailable");
        setError(controller.signal.aborted
          ? "Connection timed out. Check that the backend is running."
          : cause instanceof Error ? cause.message : "Could not reach the backend.");
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">ALPHA / BETA · ACCESS PLANNING</p>
        <h1>Railway Track Access Scheduler</h1>
        <p className="intro">Plan overnight work across the network and compare scheduling trade-offs.</p>
      </header>

      <AuthPanel onUserChange={setUser} />

      <section className="panel" aria-labelledby="connection-heading">
        <div className="panel-heading">
          <h2 id="connection-heading">Backend connection</h2>
          <span className={`badge ${connection}`} role="status">
            {connection === "checking" ? "Checking…" : connection === "connected" ? "Connected" : "Unavailable"}
          </span>
        </div>
        <p>API: <code>{API_BASE_URL}</code></p>
        {error && <p className="error" role="alert">{error}</p>}
        <button disabled={connection === "checking"} onClick={() => setAttempt(value => value + 1)}>
          Check connection
        </button>
      </section>

      <section className="panel" aria-labelledby="scenario-heading">
        <h2 id="scenario-heading">Planning scenario</h2>
        <div className="scenarios" role="group" aria-label="Choose a scenario">
          {scenarios.map(item => (
            <button key={item.id} className="scenario" aria-pressed={scenario === item.id}
              onClick={() => setScenario(item.id)}>
              <span className="scenario-id">Scenario {item.id}</span>
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </button>
          ))}
        </div>
        <p className="note">Scenario {scenario} selected for the next run.</p>
      </section>
      <PlannerPanel user={user} scenario={scenario} />
    </main>
  );
}
