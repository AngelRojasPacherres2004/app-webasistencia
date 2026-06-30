import React, { useEffect, useState } from "react";
import { get, post, session } from "./api";
import { Toast } from "./ui";
import AttendancePage from "./pages/AttendancePage";
import SalariesPage from "./pages/SalariesPage";
import EmailPage from "./pages/EmailPage";
import StoresPage from "./pages/StoresPage";
import WorkersPage from "./pages/WorkersPage";
import MarksPage from "./pages/MarksPage";

const PAGES = [
  ["attendance", "Asistencias", "◫"],
  ["salaries", "Salarios", "S/"],
  ["email", "Correo", "✉"],
  ["stores", "Tiendas", "⌂"],
  ["workers", "Trabajadores", "♙"],
  ["marks", "Marcas", "⌁"],
];

function Login({ onLogin }) {
  const [form, setForm] = useState({ username: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [videoReady, setVideoReady] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await post("/api/auth/login", form);
      session.set(result.token);
      onLogin(result.user);
    } catch (requestError) {
      setError(requestError.message);
      setLoading(false);
    }
  };

  return (
    <main className={`login ${loading ? "login--loading" : ""} ${videoReady ? "login--video-ready" : ""}`}>
      <video
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        onCanPlay={() => setVideoReady(true)}
        onLoadedData={() => setVideoReady(true)}
      >
        <source src="/media/fondologin.mp4" type="video/mp4" />
      </video>
      <div className="login__veil" />
      <form className="login-card" onSubmit={submit}>
        <div className="login-card__brand">
          <span className="login-mark">⬡</span>
          <h1>ADMIN</h1>
        </div>
        <p className="login-card__intro">Gestión de Asistencia y Personal</p>
        {error && <div className="form-error">{error}</div>}
        <label className="field">
          <span>USUARIO&nbsp;&nbsp;/&nbsp;&nbsp;CORREO</span>
          <input
            autoFocus
            autoComplete="username"
            value={form.username}
            onChange={(event) => setForm({ ...form, username: event.target.value })}
            placeholder="admin@empresa.com"
          />
        </label>
        <label className="field">
          <span>CONTRASEÑA</span>
          <div className="password-field">
            <input
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              placeholder="••••••••"
            />
            <button
              type="button"
              onClick={() => setShowPassword((current) => !current)}
              aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              aria-pressed={showPassword}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M2.2 12s3.5-6 9.8-6 9.8 6 9.8 6-3.5 6-9.8 6-9.8-6-9.8-6Z" />
                <circle cx="12" cy="12" r="3" />
                {showPassword && <path d="M4 4l16 16" className="password-field__slash" />}
              </svg>
            </button>
          </div>
        </label>
        <button className="button login-button" disabled={loading}>
          {loading ? <><span className="spinner" /> Abriendo panel…</> : "Entrar al panel"}
        </button>
      </form>
      {loading && (
        <div className="login-transition" role="status">
          <span className="spinner spinner--large" />
          <strong>Cargando panel…</strong>
        </div>
      )}
    </main>
  );
}

function Dashboard({ user, onLogout }) {
  const [page, setPage] = useState("attendance");
  const [menuOpen, setMenuOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const notify = (message, type = "success") => setToast({ message, type });
  const current = PAGES.find(([key]) => key === page);
  const common = { notify };

  const content = {
    attendance: <AttendancePage {...common} />,
    salaries: <SalariesPage {...common} />,
    email: <EmailPage {...common} />,
    stores: <StoresPage {...common} />,
    workers: <WorkersPage {...common} />,
    marks: <MarksPage {...common} />,
  }[page];

  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setMenuOpen(true)}>☰</button>
      {menuOpen && <button className="sidebar-scrim" onClick={() => setMenuOpen(false)} aria-label="Cerrar menú" />}
      <aside className={`sidebar ${menuOpen ? "sidebar--open" : ""}`}>
        <div className="brand">
          <span>⬡</span>
          <div><strong>Admin Asistencia</strong><small>Panel de RR. HH.</small></div>
        </div>
        <nav>
          {PAGES.map(([key, label, icon]) => (
            <button
              key={key}
              className={page === key ? "active" : ""}
              onClick={() => { setPage(key); setMenuOpen(false); }}
            >
              <span>{icon}</span>{label}
            </button>
          ))}
        </nav>
        <div className="sidebar__footer">
          <div className="user-chip"><span>{user.slice(0, 1).toUpperCase()}</span><div><small>Sesión activa</small><strong>{user}</strong></div></div>
          <button onClick={onLogout}>↪ Cerrar sesión</button>
        </div>
      </aside>
      <main className="main-content">
        <div className="topbar">
          <div><span>Panel de administración</span><small>Sistema de Asistencia</small></div>
          <span className="section-pill">{current?.[1]}</span>
        </div>
        {content}
      </main>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState({ checking: Boolean(session.get()), user: "" });

  useEffect(() => {
    if (!session.get()) return;
    get("/api/auth/me")
      .then(({ user }) => setAuth({ checking: false, user }))
      .catch(() => setAuth({ checking: false, user: "" }));
  }, []);

  useEffect(() => {
    const expire = () => setAuth({ checking: false, user: "" });
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);

  if (auth.checking) {
    return <div className="app-loading"><span className="spinner spinner--large" /><strong>Validando sesión…</strong></div>;
  }
  if (!auth.user) return <Login onLogin={(user) => setAuth({ checking: false, user })} />;
  return (
    <Dashboard
      user={auth.user}
      onLogout={() => { session.clear(); setAuth({ checking: false, user: "" }); }}
    />
  );
}
