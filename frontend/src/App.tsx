import { useCallback, useEffect, useState } from "react";
import AuthPanel from "./components/AuthPanel";
import PlannerPanel from "./components/PlannerPanel";
import Icon from "./components/Icon";
import RailGraphic from "./components/RailGraphic";
import TransportLogos from "./components/TransportLogos";
import type { User } from "./types/auth";

const scenarios = [
  { id: "A", title: "Stay within capacity", detail: "Use existing track access and allow flexible timelines.", label: "Fixed supply", icon: "train" },
  { id: "B", title: "Keep your deadlines", detail: "Meet planned dates with extra access where needed.", label: "Fixed deadlines", icon: "clock" },
  { id: "C", title: "Find the balance", detail: "Balance delays, extra access, and overnight extensions.", label: "Balanced planning", icon: "route" },
] as const;
const bufferReadings = [
  { id: "week", title: "Whole-week separation", detail: "Keeps conflicting work apart for the whole week.", label: "Recommended" },
  { id: "possession", title: "Separate-night planning", detail: "Assumes different possessions use different nights. Use for comparison; official acceptance is unconfirmed.", label: "Alternative" },
] as const;
const navigation = [
  { id: "workspace", label: "Schedule planner", icon: "route" },
  { id: "scenario-heading", label: "Planning approach", icon: "train" },
  { id: "buffer-heading", label: "Safety settings", icon: "route" },
] as const;

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scenario, setScenario] = useState<string>("A");
  const [granularity, setGranularity] = useState<"week" | "possession">("week");
  const [user, setUser] = useState<User | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [activeSection, setActiveSection] = useState("workspace");
  const [planVersion, setPlanVersion] = useState(0);
  const [pending, setPending] = useState(false);
  const onUserChange = useCallback((value: User | null) => {
    setUser(value);
    setSidebarOpen(false);
    setPending(false);
    setActiveSection("workspace");
    setScenario("A");
    setGranularity("week");
  }, []);
  useEffect(() => {
    if (!sidebarOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setSidebarOpen(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [sidebarOpen]);
  const openAuth = (mode: "signin" | "signup") => window.dispatchEvent(new CustomEvent("auth:open", { detail: mode }));
  const navigate = (id: string) => {
    if (!user) return;
    setActiveSection(id);
    setSidebarOpen(false);
    document.getElementById(id)?.scrollIntoView({ block: "start" });
  };
  const newPlan = () => {
    if (!user || pending) return;
    setScenario("A"); setGranularity("week"); setPlanVersion(value => value + 1);
    navigate("workspace");
  };

  return <div className="app-layout">
    {sidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
    <aside className={`sidebar ${sidebarOpen ? "is-open" : ""} ${!user ? "sidebar-locked" : ""}`} id="app-navigation">
      <div className="sidebar-brand"><span className="brand-mark"><Icon name="train" size={24} /></span>OptiTrack</div>
      <button type="button" className="new-plan" disabled={!user || pending} onClick={newPlan}><Icon name="plus" />New plan<Icon name="arrow" size={16} /></button>
      <p className="nav-label">YOUR WORKSPACE</p>
      <nav aria-label="Main navigation">{navigation.map(item => <button type="button" key={item.id}
        className="nav-link" disabled={!user} aria-current={user && activeSection === item.id ? "location" : undefined}
        onClick={() => navigate(item.id)}><Icon name={item.icon} />{item.label}</button>)}</nav>
      <div className="sidebar-context"><p>{user ? "Your planning workspace" : "Sign in to unlock"}</p><span>{user ? "Upload your files, generate a schedule and download your results." : "Your plans and scheduling tools will be available after you sign in."}</span></div>
      <div className="sidebar-bottom"><div className="metro-line"><i /><i /><i /><i /></div><strong>A clearer path ahead.</strong><p>Built for the overnight window.</p></div>
    </aside>
    <div className="main-column" id="top">
      <header className="topbar">
        <div className="topbar-title"><button type="button" className="icon-button mobile-menu" aria-label="Toggle navigation" aria-expanded={sidebarOpen} aria-controls="app-navigation" onClick={() => setSidebarOpen(value => !value)}><Icon name="menu" /></button><span>OptiTrack</span><span className="breadcrumb">/ {user ? "Workspace" : "Welcome"}</span></div>
        <AuthPanel onUserChange={onUserChange} onRestoringChange={setRestoring} />
      </header>
      <main className={`shell ${!user ? "welcome-shell" : ""}`}>
        {!user ? <>
          <section className="welcome-hero" aria-labelledby="welcome-title">
            <TransportLogos />
            <div className="welcome-layout"><div className="welcome-copy">
              <p className="eyebrow">RAIL ACCESS PLANNING</p>
              <h1 id="welcome-title">A clear plan.<br /><span>A network moving.</span></h1>
              <p className="welcome-description">Make every overnight window count with OptiTrack. Turn your railway work plans into schedules you can review, understand and share.</p>
              <div className="welcome-actions"><button type="button" className="primary-button" disabled={restoring} onClick={() => openAuth("signin")}>{restoring ? "Restoring your session…" : "Sign in to your workspace"}<Icon name="arrow" size={18} /></button><button type="button" className="secondary-button" disabled={restoring} onClick={() => openAuth("signup")}>Create account</button></div>
              <p className="welcome-caption">One place for planning, validation and submission.</p>
            </div><div className="welcome-art"><RailGraphic /><span className="rail-caption"><Icon name="clock" size={16} />Plan tonight. Keep tomorrow moving.</span></div></div>
          </section>
          <section className="welcome-features" aria-label="How OptiTrack works">
            <article><Icon name="upload" size={24} /><span>01 / UPLOAD</span><h2>Bring your network</h2><p>Start with the eight input CSV files for your railway network and planned work.</p></article>
            <article><Icon name="route" size={24} /><span>02 / PLAN</span><h2>Find your approach</h2><p>Balance track capacity, deadlines and overnight access. Review the checks and explanations.</p></article>
            <article><Icon name="download" size={24} /><span>03 / DOWNLOAD</span><h2>Take your plan forward</h2><p>Download the three submission CSVs together in one ZIP, ready to share.</p></article>
          </section>
        </> : <>
          <div className="workspace-heading"><div><p className="eyebrow">YOUR WORKSPACE</p><h1>Plan the next window.</h1><p className="note">Choose an approach, upload your files and generate your schedule.</p></div><TransportLogos /></div>
          <fieldset className="choice-section" disabled={pending}><legend id="scenario-heading">Planning approach</legend><p className="note">Choose one scenario. Selected: Scenario {scenario}.</p>
            <div className="scenarios">{scenarios.map(item => <label key={item.id} className="choice-card"><input type="radio" name="scenario" value={item.id} checked={scenario === item.id} onChange={() => setScenario(item.id)} /><span className="scenario"><span className="scenario-top"><Icon name={item.icon} /><span className="scenario-id">{item.id}</span></span><strong>{item.title}</strong><span>{item.detail}</span><span className="scenario-label">{item.label}</span></span></label>)}</div>
          </fieldset>
          <fieldset className="choice-section buffer-section" disabled={pending}><legend id="buffer-heading">Safety settings</legend><p className="note">Choose one safety setting. This is separate from your scenario choice.</p>
            <div className="scenarios buffer-readings">{bufferReadings.map(item => <label key={item.id} className="choice-card"><input type="radio" name="safety" value={item.id} checked={granularity === item.id} onChange={() => setGranularity(item.id)} /><span className="scenario"><strong>{item.title}</strong><span>{item.detail}</span><span className="scenario-label">{item.label}</span></span></label>)}</div>
          </fieldset>
          <div id="workspace"><PlannerPanel key={`${user.id}:${planVersion}`} user={user} scenario={scenario} granularity={granularity} onPendingChange={setPending} /></div>
        </>}
        <footer className="workspace-footer"><Icon name="train" size={16} /><span>Better coordination. Smoother journeys.</span></footer>
      </main>
    </div>
  </div>;
}
