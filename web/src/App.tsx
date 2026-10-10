import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import type { Health } from "./types";
import { Icon, Logo } from "./components/Icon";
import { Home } from "./pages/Home";
import { RunPage } from "./pages/RunPage";
import { ScoreboardPage } from "./pages/Scoreboard";
import { TryPage } from "./pages/Try";
import { NotFound } from "./pages/NotFound";

function useHealth(): Health | null {
  const [h, setH] = useState<Health | null>(null);
  useEffect(() => {
    api.health().then(setH).catch(() => setH(null));
  }, []);
  return h;
}

function Header({ health }: { health: Health | null }) {
  return (
    <header className="topbar">
      <div className="topbar-inner container">
        <Link to="/" className="brand" aria-label="Greenlight home">
          <Logo />
          <span className="brand-name">Greenlight</span>
        </Link>
        <nav className="nav">
          <NavLink to="/" end className="nav-link">Replays</NavLink>
          <NavLink to="/scoreboard" className="nav-link">Scoreboard</NavLink>
          <NavLink to="/try" className="nav-link">Try it</NavLink>
        </nav>
        <div className="topbar-right">
          <span className={`live-chip ${health?.live ? "is-live" : ""}`} title={health ? `executor: ${health.executor}` : "server status unknown"}>
            <span className="live-dot" />
            {health == null ? "offline" : health.live ? "live runs on" : "replays"}
          </span>
          <a className="icon-link" href="#" aria-label="GitHub">
            <Icon name="github" size={17} />
          </a>
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="footer">
      <div className="container footer-inner">
        <span className="footer-brand"><Logo size={18} /> Greenlight</span>
        <span>
          Built for the Nebius × NVIDIA Global AI Hackathon · MIT · <a href="#">GitHub</a>
        </span>
      </div>
    </footer>
  );
}

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export function App() {
  const health = useHealth();
  return (
    <div className="app">
      <ScrollToTop />
      <Header health={health} />
      <main className="main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/replay/:id" element={<RunPage mode="replay" />} />
          <Route path="/live/:runId" element={<RunPage mode="live" />} />
          <Route path="/scoreboard" element={<ScoreboardPage />} />
          <Route path="/try" element={<TryPage health={health} />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
