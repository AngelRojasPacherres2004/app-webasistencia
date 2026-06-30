import React, { useEffect, useMemo, useState } from "react";
import { download, get, patch, query } from "../api";
import { Badge, Button, Card, Empty, Field, Metric, PageHeader, Pagination, Spinner, Table } from "../ui";

const monthValue = () => new Date().toISOString().slice(0, 7);

export default function AttendancePage({ notify }) {
  const [catalog, setCatalog] = useState({ stores: [], workers: [] });
  const [filters, setFilters] = useState({
    period: "month",
    reference: `${monthValue()}-01`,
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
      const result = await get(`/api/attendance?${query(next)}`);
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

  const update = (name, value) => {
    const next = { ...filters, [name]: value };
    if (name === "store_id") next.worker_dni = "";
    setFilters(next);
  };

  const exportReport = async (kind) => {
    try {
      await download(`/api/attendance/export.${kind}?${query(filters)}`);
      notify("Reporte generado correctamente.");
    } catch (requestError) {
      notify(requestError.message, "error");
    }
  };

  const justify = async (id) => {
    try {
      await patch(`/api/attendance/${id}/justify`);
      notify("Registro justificado.");
      load();
    } catch (requestError) {
      notify(requestError.message, "error");
    }
  };

  return (
    <>
      <PageHeader
        title="Resumen de asistencias"
        subtitle="Revisa puntualidad, horarios y excepciones por periodo."
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
          <input type="month" value={filters.reference.slice(0, 7)} onChange={(event) => update("reference", `${event.target.value}-01`)} />
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
          <Card>
            <div className="card-title">
              <div><h2>{data.label}</h2><p>{data.start} — {data.end}</p></div>
              <Badge tone="blue">{data.rows.length} registros</Badge>
            </div>
            {!data.rows.length ? <Empty text="Prueba con otro periodo o cambia los filtros." /> : (
              <Table headers={["Fecha", "Trabajador", "Tienda", "Entrada", "Receso", "Salida", "Estado", "Acción"]} minWidth={980}>
                {data.rows.slice(page * 25, (page + 1) * 25).map((row) => (
                  <tr key={row.id_asistencia}>
                    <td><strong>{row.fecha}</strong></td>
                    <td><strong>{row.nombre_trabajador}</strong><small className="cell-sub">DNI {row.dni}</small></td>
                    <td>{row.nombre_tienda || "—"}</td>
                    <td>{row.hora_inicio || "—"}</td>
                    <td>{row.inicio_receso || "—"} / {row.final_receso || "—"}</td>
                    <td>{row.hora_final || "—"}</td>
                    <td>
                      {row.justificado ? <Badge tone="blue">Justificado</Badge> : row.late ? <Badge tone="warning">Tardanza</Badge> : <Badge active>Puntual</Badge>}
                    </td>
                    <td>{row.justificable ? <Button variant="ghost" onClick={() => justify(row.id_asistencia)}>Justificar</Button> : "—"}</td>
                  </tr>
                ))}
              </Table>
            )}
            <Pagination page={page} setPage={setPage} total={data.rows.length} />
          </Card>
        </>
      )}
    </>
  );
}
