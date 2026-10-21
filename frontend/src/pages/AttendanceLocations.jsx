import React, { useEffect, useMemo, useState } from "react";
import { get, query } from "../api";
import { Badge, Button, Card, Empty, Field, Metric, PageHeader, Spinner } from "../ui";
import { coordinates, googleMapUrls } from "../location";

export default function AttendanceLocations({ catalog, today }) {
  const [filters, setFilters] = useState({ date: today, store_id: "", worker_dni: "" });
  const [applied, setApplied] = useState(filters);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [type, setType] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setRows([]);
    setSelectedId(null);
    get(`/api/marks?${query({ start: applied.date, end: applied.date, store_id: applied.store_id, worker_dni: applied.worker_dni })}`)
      .then((result) => {
        if (cancelled) return;
        const marks = result.map((row) => ({ ...row, point: coordinates(row.ubicacion) }));
        setRows(marks);
        setSelectedId((marks.find((row) => row.point) || marks[0])?.id ?? null);
      })
      .catch((requestError) => { if (!cancelled) setError(requestError.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [applied]);

  const workers = catalog.workers.filter((worker) => !filters.store_id || String(worker.id_sede) === filters.store_id);
  const types = [...new Set(rows.map((row) => row.tipo || "Marca"))];
  const visible = useMemo(() => rows.filter((row) => !type || (row.tipo || "Marca") === type), [rows, type]);
  const selected = visible.find((row) => row.id === selectedId) || visible.find((row) => row.point) || visible[0];
  const urls = selected?.point ? googleMapUrls(selected.point) : null;
  const located = visible.filter((row) => row.point).length;
  const update = (key, value) => setFilters((current) => ({ ...current, [key]: value, ...(key === "store_id" ? { worker_dni: "" } : {}) }));

  return <>
    <PageHeader title="Ubicación de las marcas" subtitle="Consulta un día y selecciona una marca para ver su ubicación registrada en Google Maps. Horas de Perú." />
    <form onSubmit={(event) => { event.preventDefault(); setType(""); setApplied({ ...filters }); }}>
      <Card className="filters">
        <Field label="Día"><input type="date" required value={filters.date} onChange={(event) => update("date", event.target.value)} /></Field>
        <Field label="Tienda"><select value={filters.store_id} onChange={(event) => update("store_id", event.target.value)}><option value="">Todas las tiendas</option>{catalog.stores.map((store) => <option key={store.id_tienda} value={store.id_tienda}>{store.nombre_tienda}</option>)}</select></Field>
        <Field label="Trabajador"><select value={filters.worker_dni} onChange={(event) => update("worker_dni", event.target.value)}><option value="">Todos los trabajadores</option>{workers.map((worker) => <option key={worker.dni} value={worker.dni}>{worker.nombre_trabajador}</option>)}</select></Field>
        <Button type="submit" disabled={loading}>Consultar día</Button>
      </Card>
    </form>
    {error && <div className="form-error" role="alert">{error}</div>}
    {loading ? <Spinner label="Consultando ubicaciones…" /> : !error && <>
      <div className="metrics-grid location-metrics">
        <Metric label="Marcas del día" value={visible.length} />
        <Metric label="Con ubicación" value={located} tone="green" />
        <Metric label="Sin ubicación" value={visible.length - located} tone="amber" />
      </div>
      <div className="location-layout">
        <Card className="location-history">
          <div className="card-title"><div><h2>Marcas del {applied.date.split("-").reverse().join("/")}</h2><p>Selecciona una marca. Se muestran de la más reciente a la más antigua.</p></div></div>
          <Field label="Tipo de marca"><select value={type} onChange={(event) => setType(event.target.value)}><option value="">Todos los tipos</option>{types.map((item) => <option key={item}>{item}</option>)}</select></Field>
          <div className="location-list" aria-label="Marcas del día">
            {!visible.length ? <Empty text="No hay marcas para este día y estos filtros." /> : visible.map((row) => <button type="button" key={row.id} className={`location-mark ${row.id === selected?.id ? "location-mark--selected" : ""}`} aria-pressed={row.id === selected?.id} onClick={() => setSelectedId(row.id)}>
              <span className="location-mark__heading"><strong>{row.nombre_trabajador || row.id_trabajador}</strong><Badge tone={row.point ? "blue" : "muted"}>{row.tipo || "Marca"}</Badge></span>
              <span>{row.hora_local} · DNI {row.id_trabajador}</span>
              <span>{row.nombre_tienda || "Sin tienda"}</span>
              <small>{row.point ? "Ver ubicación en el mapa" : "Sin ubicación registrada"}</small>
            </button>)}
          </div>
        </Card>
        <Card className="location-map">
          <div className="card-title"><div><h2>Google Maps</h2><p>{selected ? `${selected.nombre_trabajador || selected.id_trabajador} · ${selected.tipo || "Marca"} · ${selected.hora_local}` : "Ubicación de la marca seleccionada"}</p></div></div>
          {urls ? <>
            <iframe key={urls.embed} title={`Ubicación de ${selected.nombre_trabajador || selected.id_trabajador} a las ${selected.hora_local}`} src={urls.embed} allowFullScreen referrerPolicy="no-referrer-when-downgrade" />
            <div className="location-map__footer"><span>{selected.point.lat.toFixed(6)}, {selected.point.lng.toFixed(6)}</span><a className="button button--secondary" href={urls.open} target="_blank" rel="noopener noreferrer">Abrir en Google Maps ↗</a></div>
          </> : <Empty title={selected ? "Sin ubicación registrada" : "Sin marcas para mostrar"} text={selected ? "Esta marca no contiene coordenadas válidas. Selecciona otra marca para ver su ubicación." : "Consulta otro día o cambia los filtros."} />}
          <p className="location-note">Se muestra la ubicación guardada al marcar la asistencia; no es la ubicación actual del trabajador.</p>
        </Card>
      </div>
    </>}
  </>;
}
