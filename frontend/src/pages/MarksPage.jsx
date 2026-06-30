import React, { useMemo, useState } from "react";
import { download, get, query } from "../api";
import { Badge, Button, Card, Empty, Field, PageHeader, Pagination, Spinner, Table, today, useAsync } from "../ui";

const weekAgo = () => {
  const date = new Date();
  date.setDate(date.getDate() - 7);
  return date.toISOString().slice(0, 10);
};

export default function MarksPage({ notify }) {
  const catalog = useAsync(() => get("/api/workers"), []);
  const [filters, setFilters] = useState({ start: weekAgo(), end: today(), store_id: "", worker_dni: "" });
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const set = (key, value) => setFilters({ ...filters, [key]: value, ...(key === "store_id" ? { worker_dni: "" } : {}) });
  const workers = useMemo(() => (catalog.data?.workers || []).filter((worker) => worker.estado && (!filters.store_id || worker.id_sede === filters.store_id)), [catalog.data, filters.store_id]);
  const search = async () => {
    setLoading(true);
    try { setRows(await get(`/api/marks?${query(filters)}`)); setPage(0); }
    catch (error) { notify(error.message, "error"); }
    finally { setLoading(false); }
  };
  const exportFile = async () => {
    try { await download(`/api/marks/export.xlsx?${query(filters)}`, "marcas_asistencia.xlsx"); }
    catch (error) { notify(error.message, "error"); }
  };
  return (
    <>
      <PageHeader title="Marcas de asistencia" subtitle="Consulta el historial capturado por trabajador y tienda." actions={rows?.length ? <Button variant="secondary" onClick={exportFile}>↓ Exportar Excel</Button> : null} />
      <Card className="filters">
        <Field label="Tienda"><select value={filters.store_id} onChange={(event) => set("store_id", event.target.value)}><option value="">Todas</option>{(catalog.data?.stores || []).map((store) => <option key={store.id_tienda} value={store.id_tienda}>{store.nombre_tienda}</option>)}</select></Field>
        <Field label="Persona"><select value={filters.worker_dni} onChange={(event) => set("worker_dni", event.target.value)}><option value="">Todas</option>{workers.map((worker) => <option key={worker.dni} value={worker.dni}>{worker.nombre_trabajador}</option>)}</select></Field>
        <Field label="Desde"><input type="date" value={filters.start} onChange={(event) => set("start", event.target.value)} /></Field>
        <Field label="Hasta"><input type="date" value={filters.end} onChange={(event) => set("end", event.target.value)} /></Field>
        <Button onClick={search}>Buscar marcas</Button>
      </Card>
      {catalog.error && <div className="form-error">{catalog.error}</div>}
      {loading ? <Spinner label="Buscando marcas…" /> : rows === null ? <Card><Empty title="Elige los filtros" text="Presiona “Buscar marcas” para consultar el historial." /></Card> : !rows.length ? <Card><Empty text="No se encontraron marcas para el rango indicado." /></Card> : (
        <Card>
          <div className="card-title"><div><h2>Resultados</h2><p>{filters.start} — {filters.end}</p></div><Badge tone="blue">{rows.length} marcas</Badge></div>
          <Table headers={["#", "Trabajador", "DNI", "Tienda", "Fecha", "Hora", "Tipo", "Ubicación"]} minWidth={920}>
            {rows.slice(page * 25, (page + 1) * 25).map((row, index) => <tr key={row.id}><td>{page * 25 + index + 1}</td><td><strong>{row.nombre_trabajador || "—"}</strong></td><td>{row.id_trabajador || "—"}</td><td>{row.nombre_tienda || "—"}</td><td>{row.fecha_local}</td><td>{row.hora_local}</td><td><Badge tone="blue">{row.tipo || "Marca"}</Badge></td><td className="truncate">{typeof row.ubicacion === "object" ? JSON.stringify(row.ubicacion) : row.ubicacion || "—"}</td></tr>)}
          </Table>
          <Pagination page={page} setPage={setPage} total={rows.length} />
        </Card>
      )}
    </>
  );
}
