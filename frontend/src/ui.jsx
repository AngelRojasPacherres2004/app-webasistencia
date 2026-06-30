import React, { useEffect } from "react";

export function Button({ variant = "primary", className = "", ...props }) {
  return <button className={`button button--${variant} ${className}`} {...props} />;
}

export function Field({ label, hint, children, className = "" }) {
  return (
    <label className={`field ${className}`}>
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        <p className="eyebrow">Panel de RR. HH.</p>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Card({ children, className = "" }) {
  return <section className={`card ${className}`}>{children}</section>;
}

export function Metric({ label, value, tone = "blue", detail }) {
  return (
    <div className={`metric metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}

export function Badge({ active, children, tone }) {
  const style = tone || (active ? "success" : "muted");
  return <span className={`badge badge--${style}`}>{children}</span>;
}

export function Empty({ title = "Sin resultados", text }) {
  return (
    <div className="empty">
      <span>◇</span>
      <strong>{title}</strong>
      {text && <p>{text}</p>}
    </div>
  );
}

export function Spinner({ label = "Cargando…" }) {
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function Modal({ title, children, onClose, wide = false }) {
  useEffect(() => {
    const close = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal--wide" : ""}`} role="dialog" aria-modal="true">
        <div className="modal__header">
          <div>
            <p className="eyebrow">Administración</p>
            <h2>{title}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Cerrar">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined;
    const timeout = setTimeout(onClose, 4500);
    return () => clearTimeout(timeout);
  }, [toast, onClose]);
  if (!toast) return null;
  return (
    <div className={`toast toast--${toast.type || "success"}`}>
      <span>{toast.type === "error" ? "!" : "✓"}</span>
      <p>{toast.message}</p>
      <button onClick={onClose}>×</button>
    </div>
  );
}

export function Table({ headers, children, minWidth = 760 }) {
  return (
    <div className="table-scroll">
      <table style={{ minWidth }}>
        <thead>
          <tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, setPage, total, pageSize = 25 }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const start = total ? page * pageSize + 1 : 0;
  const end = Math.min((page + 1) * pageSize, total);
  if (pages <= 1) return null;
  return (
    <div className="pagination">
      <span>Mostrando {start}–{end} de {total}</span>
      <div>
        <Button variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>← Anterior</Button>
        <strong>{page + 1} / {pages}</strong>
        <Button variant="ghost" disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Siguiente →</Button>
      </div>
    </div>
  );
}

export const money = (value) =>
  new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(Number(value || 0));

export const today = () => new Date().toISOString().slice(0, 10);

export function useAsync(task, dependencies = []) {
  const [state, setState] = React.useState({ loading: true, data: null, error: "" });
  const run = React.useCallback(async () => {
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const data = await task();
      setState({ loading: false, data, error: "" });
      return data;
    } catch (error) {
      setState({ loading: false, data: null, error: error.message });
      return null;
    }
  }, dependencies);
  React.useEffect(() => { run(); }, [run]);
  return { ...state, reload: run };
}
