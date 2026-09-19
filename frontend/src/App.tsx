import { useState } from "react";
import AuthPanel from "./components/AuthPanel";
import PlannerPanel from "./components/PlannerPanel";
import Icon from "./components/Icon";
import RailGraphic from "./components/RailGraphic";
import type { User } from "./types/auth";

const scenarios = [
  { id: "A", title: "Stay within capacity", detail: "Use existing track access and allow flexible timelines.", label: "Fixed supply", icon: "train" },
  { id: "B", title: "Keep your deadlines", detail: "Meet planned dates with extra access where needed.", label: "Fixed deadlines", icon: "clock" },
  { id: "C", title: "Find the balance", detail: "Balance delays, extra access, and overnight extensions.", label: "Balanced planning", icon: "route" },
] as const;

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scenario, setScenario] = useState<string>("A");
  const [user, setUser] = useState<User | null>(null);

  const openAuth = () => window.dispatchEvent(new Event("auth:open"));

  return (
    <div className="app-layout">
      {sidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`} id="app-navigation">
        <a className="sidebar-brand" href="#top" onClick={() => setSidebarOpen(false)}><span className="brand-mark"><Icon name="train" size={24} /></span>OptiTrack</a>
        <button className="new-plan" onClick={() => { setScenario("A"); setSidebarOpen(false); if (!user) openAuth(); else document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth" }); }}><Icon name="plus" />New plan<Icon name="arrow" size={16} /></button>
        <p className="nav-label">YOUR WORKSPACE</p>
        <nav aria-label="Main navigation"><a className="nav-link active" href="#workspace" onClick={() => setSidebarOpen(false)}><Icon name="route" />Access planner</a><a className="nav-link" href="#scenario-heading" onClick={() => setSidebarOpen(false)}><Icon name="train" />Planning scenarios</a></nav>
        <div className="sidebar-context"><p>{user ? "Ready for your next run" : "Your network, in sync"}</p><span>{user ? "Upload a network or pick a saved dataset to start planning." : "Sign in to save datasets and manage your scheduling runs."}</span></div>
        <div className="sidebar-bottom"><div className="metro-line"><i /><i /><i /><i /></div><strong>A clearer path ahead.</strong><p>Built for the overnight window.</p></div>
      </aside>
      <div className="main-column" id="top">
        <header className="topbar"><div className="topbar-title"><button className="icon-button mobile-menu" aria-label="Toggle navigation" aria-expanded={sidebarOpen} aria-controls="app-navigation" onClick={() => setSidebarOpen(!sidebarOpen)}><Icon name="menu" /></button><span>OptiTrack</span><span className="breadcrumb">/ Workspace</span></div><AuthPanel onUserChange={setUser} /></header>
        <main className="shell">
          <section className="hero" aria-labelledby="hero-title"><RailGraphic /><p className="eyebrow">SMARTER RAIL ACCESS PLANNING</p><h1 id="hero-title">OptiTrack<span>.</span></h1><h2>Make every night count.</h2><p className="intro">Less time coordinating. More time on track.<br />Plan overnight work across your network, all in one place.</p></section>
          <section className="scenario-section" aria-labelledby="scenario-heading"><div className="section-heading"><h2 id="scenario-heading">How would you like to plan?</h2><span>Choose your approach</span></div><div className="scenarios" role="group" aria-label="Choose a scenario">{scenarios.map(item => <button key={item.id} className="scenario" aria-pressed={scenario === item.id} onClick={() => setScenario(item.id)}><div className="scenario-top"><Icon name={item.icon} /><span className="scenario-id">{item.id}</span></div><strong>{item.title}</strong><span>{item.detail}</span><span className="scenario-label">{item.label}</span></button>)}</div></section>
          <div id="workspace"><PlannerPanel user={user} scenario={scenario} /></div>
          <footer className="workspace-footer"><Icon name="train" size={16} /><span>Better coordination. Smoother journeys.</span></footer>
        </main>
      </div>
    </div>
  );
}
