import React, { useEffect, useMemo, useState } from "react";
import { download, get, query } from "../api";
import { Badge, Button, Card, Empty, Field, Metric, PageHeader, Pagination, Spinner } from "../ui";

const PAGE_SIZE = 12;
const WEEK_DAYS = [
  ["lunes", "Lunes"],
  ["martes", "Martes"],
  ["miercoles", "Miércoles"],
  ["jueves", "Jueves"],
  ["viernes", "Viernes"],
  ["sabado", "Sábado"],
];

const toIsoDate = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

const fromIsoDate = (value) => new Date(`${value}T12:00:00`);

const todayInLima = () => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date()).reduce((result, part) => ({ ...result, [part.type]: part.value }), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
};

const shortDate = (value) => {
  const [, month, day] = value.split("-");
  return `${day}/${month}`;
};

const longDate = (value) => {
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
};

const weeksForMonth = (reference) => {
  const [year, month] = reference.split("-").map(Number);
  const firstDay = new Date(year, month - 1, 1, 12);
  const lastDay = new Date(year, month, 0, 12);
  const firstMonday = new Date(firstDay);
  firstMonday.setDate(firstDay.getDate() - ((firstDay.getDay() + 6) % 7));
  const weeks = [];

  for (let monday = firstMonday; monday <= lastDay; monday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 7, 12)) {
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    weeks.push({
      value: toIsoDate(monday),
      label: `Semana ${weeks.length + 1} · ${longDate(toIsoDate(monday))} → ${longDate(toIsoDate(sunday))}`,
    });
  }
  return weeks;
};

const effectiveFilters = (values) => {
  const { week_reference: weekReference, ...base } = values;
  return weekReference
    ? { ...base, period: "week", reference: weekReference }
    : base;
};

const buildWeeks = (startValue, endValue) => {
  const start = fromIsoDate(startValue);
  const end = fromIsoDate(endValue);
  const firstMonday = new Date(start);
  firstMonday.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  const weeks = [];

  for (let monday = firstMonday; monday <= end; monday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 7, 12)) {
    const days = WEEK_DAYS.map(([key, label], index) => {
      const date = new Date(monday);
      date.setDate(monday.getDate() + index);
      const iso = toIsoDate(date);
      return { key, label, iso, outside: date < start || date > end };
    });
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    weeks.push({
      key: toIsoDate(monday),
      label: `${longDate(toIsoDate(monday))} → ${longDate(toIsoDate(sunday))}`,
      days,
    });
  }
  return weeks;
};

function AttendanceCell({ day, row, worker, today }) {
  if (day.outside) return <div className="attendance-cell attendance-cell--outside">—</div>;

  const scheduled = Boolean(worker.horario?.[day.key]);
  let status = "pending";
  let label = "Pendiente";

  if (row?.justificado) {
    status = "justified";
    label = "Justificado";
  } else if (row && !row.hora_inicio && !row.hora_final) {
    status = "missing";
    label = "Sin marca";
  } else if (row?.late) {
    status = "late";
    label = "Tardanza";
  } else if (row) {
    status = "on-time";
    label = "Puntual";
  } else if (!scheduled) {
    status = "off";
    label = "No viene";
  } else if (day.iso <= today) {
    status = "absent";
    label = "Falta";
  }

  const title = `${worker.nombre_trabajador} · ${day.label} ${longDate(day.iso)} · ${label}`;
  return (
    <div className={`attendance-cell attendance-cell--${status}`} title={title}>
      {row ? (
        <>
          <span>{row.hora_inicio || "—"}</span>
          <span>{row.hora_final || "—"}</span>
        </>
      ) : (
        <strong>{label}</strong>
      )}
    </div>
  );
}

export default function AttendancePage({ notify }) {
  const today = useMemo(todayInLima, []);
  const [catalog, setCatalog] = useState({ stores: [], workers: [] });
  const [filters, setFilters] = useState({
    period: "month",
    reference: `${today.slice(0, 7)}-01`,
    week_reference: "",
    store_id: "",
    worker_dni: "",
    q: "",
  });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);

  const load = async (next = filters) => {
    setLoading(true);
    setError("");
    try {
      const result = await get(`/api/attendance?${query(effectiveFilters(next))}`);
      setData(result);
      setPage(0);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    get("/api/workers")
      .then((result) => setCatalog(result))
      .catch((requestError) => setError(requestError.message));
    load();
  }, []);

  const availableWorkers = useMemo(
    () => catalog.workers.filter((worker) => !filters.store_id || worker.id_sede === filters.store_id),
    [catalog.workers, filters.store_id],
  );

  const monthWeeks = useMemo(
    () => weeksForMonth(filters.reference),
    [filters.reference],
  );

  const weeks = useMemo(
    () => data ? buildWeeks(data.start, data.end) : [],
    [data],
  );

  const attendanceByWorkerAndDate = useMemo(
    () => new Map((data?.rows || []).map((row) => [`${row.dni}-${row.fecha}`, row])),
    [data],
  );

  const visibleWorkers = useMemo(
    () => (data?.workers || []).slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE),
    [data, page],
  );

  const update = (name, value) => {
    const next = { ...filters, [name]: value };
    if (name === "store_id") next.worker_dni = "";
    if (name === "reference") next.week_reference = "";
    setFilters(next);
  };

  const exportReport = async (kind) => {
    try {
      await download(`/api/attendance/export.${kind}?${query(effectiveFilters(filters))}`);
      notify("Reporte generado correctamente.");
    } catch (requestError) {
      notify(requestError.message, "error");
    }
  };

  return (
    <>
      <PageHeader
        title="Resumen de asistencias"
        subtitle="Revisa la semana de cada trabajador de un vistazo."
        actions={<><Button variant="secondary" onClick={() => exportReport("xlsx")}>↓ Excel</Button><Button variant="secondary" onClick={() => exportReport("pdf")}>↓ PDF</Button></>}
      />
      <Card className="filters">
        <Field label="Periodo">
          <select value={filters.period} onChange={(event) => update("period", event.target.value)}>
            <option value="month">Mes</option>
            <option value="fortnight">Quincena</option>
          </select>
        </Field>
        <Field label="Mes de referencia">
          <input
            type="month"
            value={filters.reference.slice(0, 7)}
            onChange={(event) => update("reference", `${event.target.value}-01`)}
          />
        </Field>
        <Field label="Semana">
          <select value={filters.week_reference} onChange={(event) => update("week_reference", event.target.value)}>
            <option value="">Todo el periodo</option>
            {monthWeeks.map((week) => <option key={week.value} value={week.value}>{week.label}</option>)}
          </select>
        </Field>
        <Field label="Tienda">
          <select value={filters.store_id} onChange={(event) => update("store_id", event.target.value)}>
            <option value="">Todas las tiendas</option>
            {catalog.stores.map((store) => <option key={store.id_tienda} value={store.id_tienda}>{store.nombre_tienda}</option>)}
          </select>
        </Field>
        <Field label="Persona">
          <select value={filters.worker_dni} onChange={(event) => update("worker_dni", event.target.value)}>
            <option value="">Todas</option>
            {availableWorkers.map((worker) => <option key={worker.dni} value={worker.dni}>{worker.nombre_trabajador}</option>)}
          </select>
        </Field>
        <Field label="Buscar">
          <input value={filters.q} onChange={(event) => update("q", event.target.value)} placeholder="Nombre o DNI" />
        </Field>
        <Button onClick={() => load()}>Aplicar filtros</Button>
      </Card>

      {error && <div className="form-error">{error}</div>}
      {loading ? <Spinner label="Consultando asistencias…" /> : data && (
        <>
          <div className="metrics-grid">
            <Metric label="Trabajadores" value={data.metrics.workers} />
            <Metric label="Registros" value={data.metrics.records} tone="slate" />
            <Metric label="A tiempo" value={data.metrics.on_time} tone="green" />
            <Metric label="Tardanzas" value={data.metrics.late} tone="amber" />
            <Metric label="Por justificar" value={data.metrics.pending_justifications} tone="violet" />
          </div>

          <Card className="attendance-board">
            <div className="card-title attendance-board__title">
              <div><h2>{data.label}</h2><p>{longDate(data.start)} — {longDate(data.end)}</p></div>
              <Badge tone="blue">{data.rows.length} registros</Badge>
            </div>
            <div className="attendance-legend" aria-label="Estados de asistencia">
              <span className="attendance-legend__item attendance-legend__item--on-time">Puntual</span>
              <span className="attendance-legend__item attendance-legend__item--late">Tardanza</span>
              <span className="attendance-legend__item attendance-legend__item--justified">Justificado</span>
              <span className="attendance-legend__item attendance-legend__item--absent">Falta</span>
              <span className="attendance-legend__item attendance-legend__item--missing">Sin marca</span>
              <span className="attendance-legend__item attendance-legend__item--off">No viene</span>
            </div>

            {!data.workers.length ? <Empty text="Prueba con otro periodo o cambia los filtros." /> : (
              <>
                {weeks.map((week) => (
                  <section className="attendance-week" key={week.key}>
                    <p className="attendance-week__range"><strong>Semana:</strong> {week.label}</p>
                    <div className="attendance-matrix-scroll">
                      <table className="attendance-matrix">
                        <thead>
                          <tr>
                            <th>Trabajador</th>
                            {week.days.map((day) => (
                              <th key={day.iso}>
                                <span>{day.label}</span>
                                <small>{shortDate(day.iso)}</small>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {visibleWorkers.map((worker) => (
                            <tr key={worker.dni}>
                              <td>
                                <strong>{worker.nombre_trabajador}</strong>
                                <small>DNI {worker.dni} · {worker.area || worker.nombre_sede || "Sin cargo"}</small>
                              </td>
                              {week.days.map((day) => (
                                <td key={day.iso}>
                                  <AttendanceCell
                                    day={day}
                                    row={attendanceByWorkerAndDate.get(`${worker.dni}-${day.iso}`)}
                                    worker={worker}
                                    today={today}
                                  />
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                ))}
                <Pagination
                  page={page}
                  setPage={setPage}
                  total={data.workers.length}
                  pageSize={PAGE_SIZE}
                />
              </>
            )}
          </Card>
        </>
      )}
    </>
  );
}
